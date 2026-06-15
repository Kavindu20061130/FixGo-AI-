import os

from flask import (
    Blueprint, request, jsonify,
    redirect, url_for, render_template
)
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user, current_user, login_required
)
from flask_bcrypt import Bcrypt
from sqlalchemy.orm import scoped_session, sessionmaker
from authlib.integrations.flask_client import OAuth

from db.database import engine, User

# ---------------------------------
# Setup
# ---------------------------------

login_bp = Blueprint("login", __name__)

bcrypt = Bcrypt()

# scoped_session gives each request/thread its own session,
# preventing shared-state issues under concurrent requests.
db_session = scoped_session(sessionmaker(bind=engine))


@login_bp.teardown_app_request
def remove_session(exception=None):
    db_session.remove()


# ---------------------------------
# Flask-Login
# ---------------------------------

login_manager = LoginManager()
login_manager.login_view = "login.login_page"


# ---------------------------------
# OAuth Google
# ---------------------------------

oauth = OAuth()

google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# ---------------------------------
# User Loader
# ---------------------------------

class LoginUser(UserMixin):
    def __init__(self, user):
        self.id    = user.user_id
        self.email = user.email
        self.name  = user.full_name


@login_manager.user_loader
def load_user(user_id):
    user = db_session.query(User).filter(User.user_id == int(user_id)).first()
    return LoginUser(user) if user else None


# ---------------------------------
# Pages (serve HTML)
# ---------------------------------

@login_bp.route("/")
@login_bp.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect("/dashboard")
    return render_template("login.html")


# ---------------------------------
# REGISTER
# ---------------------------------

@login_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name", "").strip()
    email     = data.get("email", "").strip().lower()
    password  = data.get("password", "")
    phone     = data.get("phone", "").strip()

    if not full_name or not email or not password:
        return jsonify({"success": False, "message": "All fields are required."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400

    existing = db_session.query(User).filter(User.email == email).first()
    if existing:
        return jsonify({"success": False, "message": "An account with this email already exists."}), 400

    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

    user = User(
        full_name=full_name,
        email=email,
        password=hashed_pw,
        phone=phone
    )

    try:
        db_session.add(user)
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({"success": False, "message": "Could not create account. Please try again."}), 500

    return jsonify({"success": True, "message": "Account created successfully. You can now sign in."})


# ---------------------------------
# LOGIN
# ---------------------------------

@login_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    remember = bool(data.get("remember", False))

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required."}), 400

    user = db_session.query(User).filter(User.email == email).first()

    if not user:
        return jsonify({"success": False, "message": "No account found with that email address."}), 404

    if user.password == "GOOGLE_LOGIN":
        return jsonify({
            "success": False,
            "message": "This account uses Google Sign-In. Please sign in with Google."
        }), 401

    if not bcrypt.check_password_hash(user.password, password):
        return jsonify({"success": False, "message": "Incorrect password. Please try again."}), 401

    login_user(LoginUser(user), remember=remember)

    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "id":    user.user_id,
            "name":  user.full_name,
            "email": user.email
        }
    })


# ---------------------------------
# LOGOUT
# ---------------------------------

@login_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


# ---------------------------------
# CURRENT USER
# ---------------------------------

@login_bp.route("/me")
def me():
    if not current_user.is_authenticated:
        return jsonify({"logged_in": False})

    return jsonify({
        "logged_in": True,
        "id":        current_user.id,
        "name":      current_user.name,
        "email":     current_user.email
    })


# ---------------------------------
# GOOGLE LOGIN
# ---------------------------------

@login_bp.route('/google')
def google_login():
    redirect_uri = url_for('login.google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


# ---------------------------------
# GOOGLE CALLBACK
# ---------------------------------

@login_bp.route('/google/callback')
def google_callback():
    token     = google.authorize_access_token()
    user_info = token.get('userinfo', {})

    email = user_info.get('email')
    name  = user_info.get('name', '')

    if not email:
        return jsonify({"success": False, "message": "Google account did not return an email address."}), 400

    user = db_session.query(User).filter(User.email == email).first()

    if not user:
        user = User(
            full_name=name,
            email=email,
            password="GOOGLE_LOGIN",
            phone=""
        )
        try:
            db_session.add(user)
            db_session.commit()
        except Exception:
            db_session.rollback()
            return jsonify({"success": False, "message": "Could not create account via Google."}), 500

    login_user(LoginUser(user), remember=True)
    return redirect("/dashboard")


# ---------------------------------
# FORGOT PASSWORD (stub)
# ---------------------------------

@login_bp.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    return jsonify({"message": "Forgot password endpoint – coming soon."})