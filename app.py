from flask import Flask, redirect, render_template, flash, session
from flask_debugtoolbar import DebugToolbarExtension
from spotifyGroupChatSecrets import SECRET_KEY
from models import connect_db, db, User
from forms import UserForm

app = Flask(__name__) # Create Flask object
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql:///spotify_group_chat" # PSQL database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Don't track modifications
app.config['SECRET_KEY'] = SECRET_KEY # SECRET_KEY for debug toolbar


app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False # Disable intercepting redirects

toolbar = DebugToolbarExtension(app) # Create debug toolbar object

connect_db(app) # Connect database to Flask object 
db.create_all() # Create all tables

@app.route('/')
def root():
  """Show homepage"""
  return render_template("homepage.html")

@app.route('/signup', methods=["Get", "POST"])
def signup_user():
  """Regiter new user"""
  form = UserForm()
  if form.validate_on_submit():
    username = form.username.data
    password = form.password.data
    new_user = User.signup(username=username, password=password)

    db.session.add(new_user)
    db.session.commit()
    session['user_id'] = new_user.id
    flash("Welcome! Successfully create you account!", 'success')
    return redirect('/')

  return render_template("users/signup.html", form=form)

@app.route('/login', methods=["GET", "POST"])
def login_user():
  """Login for user"""
  form = UserForm()
  if form.validate_on_submit():
    username = form.username.data
    password = form.password.data
    user = User.authenticate(username=username, password=password)
    
    if user:
      flash("Logged in", 'success')
      session['user_id'] = user.id
      return redirect('/playlists')
    else:
      form.username.errors = ["Invalid username/password"]
  return render_template("users/login.html",form=form)

@app.route('/logout')
def logout_user():
  session.pop('user_id')
  return redirect('/')

@app.route('/playlists')
def show_playlists():
  """Show list of playlists"""
  if "user_id" not in session:
    flash("Please log in", 'warning')
    return redirect('/')
  return render_template("playlists.html")