import json
import requests
import re
from urllib.parse import urlencode

from my_secrets import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_HEADER 
from models import User, Playlist, db

SPOTIFY_AUTH_BASE_URL = 'https://accounts.spotify.com'
SPOTIFY_AUTH_URL= SPOTIFY_AUTH_BASE_URL + '/authorize'
SPOTIFY_TOKEN_URL = SPOTIFY_AUTH_BASE_URL + '/api/token'

SPOTIFY_API_URL = 'https://api.spotify.com/v1'
USER_PROFILE_ENDPOINT = SPOTIFY_API_URL + '/me'

REDIRECT_URI = 'http://localhost:5000/login' 
SCOPE = 'user-read-email playlist-modify-public playlist-modify-private' # Scope of authorization

# ------------------------- REQUEST AUTHORIZATION TO ACCESS DATA ---------------------------
auth_query_parameters = {
  "response_type": "code",
  "client_id": SPOTIFY_CLIENT_ID,
  "scope": SCOPE,
  "redirect_uri": REDIRECT_URI,
  "show_dialog": True # This enables users to switch accounts
}

AUTHORIZATION_URL = f"{SPOTIFY_AUTH_URL}?{urlencode(auth_query_parameters)}"


# -------------------------- REQUEST ACCESS AND REFRESH TOKENS ----------------------------
def get_auth_tokens(code):
  """2nd call in the Spotify Authetication process

  Pass the authorization code returned by the first call and the client 
  secret key to the Spotify Accounts Service '/api/token' endpoint. 
  
  Returns the HTTP response as a python dictionary which contains the access_token and
  refresh_token
  """
  # Encode client id and secret key


  data = {
      "code": str(code),
      "redirect_uri": REDIRECT_URI,
      "grant_type": "authorization_code"
  }

  # Pass authorization code and client secret key to the Spotify Accounts Service
  auth_response = requests.post(SPOTIFY_TOKEN_URL, headers=SPOTIFY_CLIENT_HEADER , data=data)

  # Tokens returned 
  return json.loads(auth_response.text) #.json() to convert to a python dictionary


def refresh_access_token(user):
  """Get a new access token when the old access token is expired"""

  data = {
    "grant_type": "refresh_token",
    "refresh_token": user.refresh_token
  }

  auth_response = requests.post(SPOTIFY_TOKEN_URL, headers=SPOTIFY_CLIENT_HEADER, data=data)
  auth_data = json.loads(auth_response.text)

  user.access_token = auth_data["access_token"]

  db.session.add(user)
  db.session.commit()
  return user


def make_authorized_api_call(user, endpoint, data=None, params=None):
  """Make an authorized api call with protection against expired access tokens.

  Return the responce in a python dictionary"""

  request = requests.post(endpoint, headers=user.auth_header, data=data,params=params)
  # Check for expired access token (error code 401)
  if request.status_code == 401:
    refresh_access_token(user) #refresh the owner's access_token
    request = requests.post(endpoint, headers=user.auth_header, data=data,params=params) # make the request again
  
  return json.loads(request.text) # Unpack response


# -------------------------- OTHER REQUESTS ---------------------------
def get_user_data(auth_data):
  """Make a request to the spotify API and return a User object"""

  access_token = auth_data["access_token"]
  refresh_token = auth_data["refresh_token"]

  auth_header = {"Authorization": f"Bearer {access_token}"}

  response = requests.get(USER_PROFILE_ENDPOINT, headers=auth_header)

  profile_data = response.json()

  # Get data from response
  display_name = profile_data['display_name']
  email = profile_data['email']
  url = profile_data['external_urls']['spotify']
  id = profile_data['id'] # Use same id as spotify

  user = User.query.filter_by(email=email).first() # Check if the User is already in the Database using email address

  # If the user is not in the database
  if not user:
    # Create User object
    user = User(display_name=display_name, email=email, url=url, id=id, access_token=access_token, refresh_token=refresh_token)
    db.session.add(user) # Add User to Database
    db.session.commit() 
    # flash('New Account Created!', 'success')

  # If the User already exits update the access token and refresh token 
  else:
    user.access_token = access_token # Update access_token
    user.refresh_token = refresh_token # Update access_token
    db.session.add(user) # Update User
    db.session.commit() 

  return  user # return the User object


def create_playlist(user, title):
  """Create a playlist on the users account"""

  # Data for created playlist
  data = json.dumps({
    "name": title,
    "description": "Spotify SMS Playlist",
    "public": False, # Collaborative playlists cannot be public
    "collaborative": True 
  })

  create_playlist_endpoint = SPOTIFY_API_URL + f"/users/{user.id}/playlists"

  playlist_data = make_authorized_api_call(user=user, endpoint=create_playlist_endpoint, data=data)

  id = playlist_data['id'] # Use the same id as spotify
  url = playlist_data['external_urls']['spotify'] # Used for links in user interface
  playlist_endpoint = playlist_data['href'] # Used for adding tracks
  owner_id = playlist_data['owner']['id'] # Use the same owner id as spotify

  new_playlist = Playlist(id=id, title=title, url=url, endpoint=playlist_endpoint, owner_id=owner_id)
  db.session.add(new_playlist)
  user.active_playlist_id = id
  db.session.add(user)
  db.session.commit() # commit to database
  
  return new_playlist


def get_track_ids_from_message(message):
  """Returns a list of Spotify track URLs in a string"""

  track_ids = [] # List of track_ids to return

  urls = re.findall('https:\/\/open.spotify.com\/track\/+[^? ]*', message) # Regex for finding track urls
  
  # Iterate over found urls
  for url in urls:
    track_id = url.replace('https://open.spotify.com/track/', '') # replace the begining to get the track id
    track_ids.append(track_id) # Append track_id to our list to return

  return track_ids


def add_tracks_to_playlist(playlist, track_ids):
  """Make a post request to add the track_ids to the Spotify playlist"""

  auth_header = playlist.owner.auth_header # get auth_header of the playlist's owner
  add_tracks_endpoint = playlist.endpoint + "/tracks"
  
  # Pass the track_ids to spotify in the query string with the key "uris"
  uris_string = 'spotify:track:' + track_ids[0] # Format the first track track_ids[0]

  # For all track_ids after the first (track_ids[1:]) add them with a comma seperator
  for track_id in track_ids[1:]:
    uris_string = uris_string + ',' + 'spotify:track:' + track_id

  # Make the post request to add the tracks to the playlist
  make_authorized_api_call(user=playlist.owner, endpoint=add_tracks_endpoint, params={"uris": uris_string})