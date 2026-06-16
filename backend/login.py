import os
import re
import random
import string
from datetime import datetime, timedelta

from flask import (
    Blueprint, request, jsonify,
    redirect, url_for, render_template, session
)
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user, current_user, login_required
)
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from sqlalchemy.orm import scoped_session, sessionmaker

from db.database import engine, User, UserDetails

# ---------------------------------
# Setup
# ---------------------------------

login_bp = Blueprint("login", __name__)
db_session = scoped_session(sessionmaker(bind=engine))
mail = Mail()

@login_bp.teardown_app_request
def remove_session(exception=None):
    db_session.remove()

# ---------------------------------
# Flask-Login
# ---------------------------------
login_manager = LoginManager()
login_manager.login_view = "login.login_page"

# ---------------------------------
# OAuth Google – CREDENTIALS EMBEDDED
# ---------------------------------
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
        self.id = user.user_id
        self.email = user.email
        self.name = user.full_name

@login_manager.user_loader
def load_user(user_id):
    user = db_session.query(User).filter(User.user_id == int(user_id)).first()
    return LoginUser(user) if user else None

# ---------------------------------
# Helpers
# ---------------------------------
def has_completed_details(user_id):
    return db_session.query(UserDetails).filter_by(user_id=user_id).first() is not None


def validate_phone(phone):
    """
    Accepts:
      - Sri Lankan: +94XXXXXXXXX or 07XXXXXXXX (10 digits starting with 07)
      - International: +[country_code][number] (E.164 format)
    Returns (True, normalized) or (False, error_message)
    """
    if not phone:
        return True, ""   # phone is optional

    phone = phone.strip()

    # Sri Lankan local format: 07XXXXXXXX → convert to +947XXXXXXXX
    lk_local = re.match(r'^(07\d{8})$', phone)
    if lk_local:
        return True, "+94" + phone[1:]

    # E.164 international: +[1-3 digit country code][number]
    intl = re.match(r'^\+[1-9]\d{6,14}$', phone)
    if intl:
        return True, phone

    return False, (
        "Please enter a valid phone number. "
        "Use Sri Lankan format (07XXXXXXXX) or international format (+94XXXXXXXXX)."
    )


def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))


def send_otp_email(to_email, otp):
    """Send OTP via Flask-Mail. Falls back gracefully if mail not configured."""
    try:
        msg = Message(
            subject="FixGo – Password Reset OTP",
            sender=os.environ.get("MAIL_DEFAULT_SENDER", "noreply@fixgo.lk"),
            recipients=[to_email]
        )
        msg.body = (
            f"Hi,\n\n"
            f"Your FixGo password reset OTP is: {otp}\n\n"
            f"This OTP is valid for 10 minutes. Do not share it with anyone.\n\n"
            f"If you did not request this, ignore this email.\n\n"
            f"– FixGo Team"
        )
        msg.html = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:24px;">
            <h2 style="color:#E8431A;">FixGo – Password Reset</h2>
            <p>Your one-time password (OTP) is:</p>
            <div style="font-size:2rem;font-weight:700;letter-spacing:.3em;
                        background:#fff3f0;border-radius:8px;padding:16px 24px;
                        color:#E8431A;text-align:center;margin:16px 0;">
                {otp}
            </div>
            <p style="color:#666;">Valid for <strong>10 minutes</strong>. 
            Do not share this with anyone.</p>
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
            <p style="font-size:.8rem;color:#aaa;">FixGo – Fix it fast. Fix it right.</p>
        </div>
        """
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[MAIL ERROR] {e}")
        return False

# ---------------------------------
# Pages
# ---------------------------------
@login_bp.route("/")
@login_bp.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect("/dashboard")
    return render_template("login.html")


@login_bp.route("/register", methods=["GET"])
def register_page():
    if current_user.is_authenticated:
        return redirect("/dashboard")
    return render_template("register.html")


@login_bp.route("/complete-profile", methods=["GET"])
@login_required
def complete_profile_page():
    if has_completed_details(current_user.id):
        return redirect("/dashboard")
    return render_template("complete_profile.html")


@login_bp.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    return render_template("forgot_password.html")


@login_bp.route("/reset-password", methods=["GET"])
def reset_password_page():
    return render_template("reset_password.html")

# ---------------------------------
# REGISTER (POST)
# ---------------------------------
@login_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    full_name       = data.get("full_name", "").strip()
    email           = data.get("email", "").strip().lower()
    password        = data.get("password", "")
    confirm_password = data.get("confirm_password", "")
    phone_raw       = data.get("phone", "").strip()
    nic             = data.get("nic", "").strip()
    address         = data.get("address", "").strip()

    # Required field check
    if not all([full_name, email, password, confirm_password, nic, address]):
        return jsonify({
            "success": False,
            "message": "All fields except phone are required."
        }), 400

    # Password length
    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must be at least 6 characters."
        }), 400

    # Password match
    if password != confirm_password:
        return jsonify({
            "success": False,
            "field": "confirm_password",
            "message": "Passwords do not match. Please re-enter."
        }), 400

    # Phone validation
    phone_ok, phone_result = validate_phone(phone_raw)
    if not phone_ok:
        return jsonify({
            "success": False,
            "field": "phone",
            "message": phone_result
        }), 400
    phone = phone_result  # normalized

    # Duplicate email check
    existing = db_session.query(User).filter(User.email == email).first()
    if existing:
        return jsonify({
            "success": False,
            "field": "email",
            "message": "This email is already registered. Please sign in instead."
        }), 400

    hashed_pw = generate_password_hash(password)
    user = User(full_name=full_name, email=email, password=hashed_pw, phone=phone)

    try:
        db_session.add(user)
        db_session.flush()

        details = UserDetails(user_id=user.user_id, nic=nic, address=address, phone=phone)
        db_session.add(details)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        return jsonify({
            "success": False,
            "message": f"Error creating account: {str(e)}"
        }), 500

    return jsonify({"success": True, "message": "Account created successfully. Please sign in."})

# ---------------------------------
# LOGIN (POST)
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
        return jsonify({
            "success": False,
            "field": "email",
            "message": "No account found with this email."
        }), 404

    if user.password == "GOOGLE_LOGIN":
        return jsonify({
            "success": False,
            "message": "This account uses Google Sign-In. Please click 'Sign in with Google'."
        }), 401

    if not check_password_hash(user.password, password):
        return jsonify({
            "success": False,
            "field": "password",
            "message": "Incorrect password."
        }), 401

    login_user(LoginUser(user), remember=remember)
    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {"id": user.user_id, "name": user.full_name, "email": user.email}
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
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email
    })

# ---------------------------------
# GOOGLE LOGIN
# ---------------------------------
@login_bp.route('/google')
def google_login():
    redirect_uri = url_for('login.google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@login_bp.route('/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
    except Exception as e:
        print(f"[GOOGLE OAuth ERROR] {e}")
        return redirect("/login?error=google_failed")

    # parse userinfo from id_token
    userinfo = token.get('userinfo')
    if not userinfo:
        try:
            resp = google.get('https://openidconnect.googleapis.com/v1/userinfo')
            userinfo = resp.json()
        except Exception as e:
            print(f"[GOOGLE userinfo fetch ERROR] {e}")
            return redirect("/login?error=google_no_userinfo")

    email = userinfo.get('email')
    name  = userinfo.get('name', '')

    if not email:
        return redirect("/login?error=google_no_email")

    if not userinfo.get('email_verified', True):
        return redirect("/login?error=google_unverified")

    user = db_session.query(User).filter(User.email == email).first()

    if user:
        login_user(LoginUser(user), remember=True)
        if not has_completed_details(user.user_id):
            return redirect(url_for('login.complete_profile_page'))
        return redirect("/dashboard")
    else:
        try:
            user = User(full_name=name, email=email, password="GOOGLE_LOGIN", phone="")
            db_session.add(user)
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            print(f"[GOOGLE user create ERROR] {e}")
            return redirect("/login?error=google_db_error")

        login_user(LoginUser(user), remember=True)
        return redirect(url_for('login.complete_profile_page'))


# ---------------------------------
# COMPLETE PROFILE (POST)
# ---------------------------------
@login_bp.route("/complete-profile", methods=["POST"])
@login_required
def complete_profile():
    data    = request.get_json(silent=True) or {}
    nic     = data.get("nic", "").strip()
    address = data.get("address", "").strip()
    phone_raw = data.get("phone", "").strip()

    if not nic or not address:
        return jsonify({"success": False, "message": "NIC and address are required."}), 400

    phone_ok, phone_result = validate_phone(phone_raw)
    if not phone_ok:
        return jsonify({"success": False, "field": "phone", "message": phone_result}), 400

    if has_completed_details(current_user.id):
        return redirect("/dashboard")

    details = UserDetails(
        user_id=current_user.id,
        nic=nic,
        address=address,
        phone=phone_result
    )
    try:
        db_session.add(details)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        return jsonify({"success": False, "message": f"Error saving details: {str(e)}"}), 500

    return jsonify({"success": True, "message": "Profile completed! Redirecting..."})


# ================================================================
# FORGOT PASSWORD – OTP Flow
# ================================================================

@login_bp.route("/forgot-password/send-otp", methods=["POST"])
def send_otp():
    """Step 1 – user submits email, we generate & email an OTP."""
    data  = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400

    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        return jsonify({
            "success": True,
            "message": "If this email is registered, an OTP has been sent."
        })

    if user.password == "GOOGLE_LOGIN":
        return jsonify({
            "success": False,
            "message": "This account uses Google Sign-In. Password reset is not available."
        }), 400

    otp     = generate_otp()
    expires = datetime.utcnow() + timedelta(minutes=10)

    session['otp_email']   = email
    session['otp_code']    = otp
    session['otp_expires'] = expires.isoformat()

    sent = send_otp_email(email, otp)

    if not sent:
        print(f"[DEV] OTP for {email}: {otp}")

    return jsonify({
        "success": True,
        "message": "If this email is registered, an OTP has been sent.",
        "dev_otp": otp if os.environ.get("FLASK_ENV") == "development" else None
    })


@login_bp.route("/forgot-password/verify-otp", methods=["POST"])
def verify_otp():
    """Step 2 – user submits the OTP they received."""
    data  = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    otp   = data.get("otp", "").strip()

    stored_email   = session.get('otp_email')
    stored_otp     = session.get('otp_code')
    stored_expires = session.get('otp_expires')

    if not stored_otp or stored_email != email:
        return jsonify({"success": False, "message": "Invalid or expired OTP. Please request a new one."}), 400

    if datetime.utcnow() > datetime.fromisoformat(stored_expires):
        session.pop('otp_code', None)
        return jsonify({"success": False, "message": "OTP has expired. Please request a new one."}), 400

    if otp != stored_otp:
        return jsonify({"success": False, "message": "Incorrect OTP. Please try again."}), 400

    session['otp_verified'] = True
    session.pop('otp_code', None)

    return jsonify({"success": True, "message": "OTP verified. You may now reset your password."})


@login_bp.route("/forgot-password/reset", methods=["POST"])
def reset_password():
    """Step 3 – user sets a new password after OTP verification."""
    data             = request.get_json(silent=True) or {}
    email            = data.get("email", "").strip().lower()
    new_password     = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not session.get('otp_verified') or session.get('otp_email') != email:
        return jsonify({
            "success": False,
            "message": "Session expired or unauthorised. Please start over."
        }), 403

    if len(new_password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400

    if new_password != confirm_password:
        return jsonify({
            "success": False,
            "field": "confirm_password",
            "message": "Passwords do not match."
        }), 400

    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        return jsonify({"success": False, "message": "Account not found."}), 404

    try:
        user.password = generate_password_hash(new_password)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        return jsonify({"success": False, "message": f"Error updating password: {str(e)}"}), 500

    for k in ('otp_email', 'otp_verified', 'otp_expires'):
        session.pop(k, None)

    return jsonify({"success": True, "message": "Password reset successfully. Please sign in."})