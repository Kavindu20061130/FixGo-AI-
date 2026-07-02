import os
import re
import random
import string
import requests
from functools import wraps
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
from sqlalchemy import inspect

# Import all models
from db.database import engine, User, UserDetails, OTPVerification, AuditLog, Worker

# ---------------------------------
# Setup
# ---------------------------------

login_bp = Blueprint("login", __name__)
db_session = scoped_session(sessionmaker(bind=engine))
mail = Mail()

# Text.lk SMS Gateway Configuration
TEXT_LK_API_TOKEN = "5438|keNFvrwco0EopdAwjSfwNJ3Rsfaf1l76s8oDaqMMcce25401"
TEXT_LK_API_URL = "https://app.text.lk/api/v3/sms/send"

# ---------------------------------
# 🔧 DEVELOPMENT MODE SWITCH
# ---------------------------------
DEBUG_MODE = True   # Set to False for production (real SMS & email)

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

















# ---------------------------------
# User / Worker Loader
# ---------------------------------
# NOTE ON ROLES
# --------------
# FixGo has two kinds of accounts that sign in through the *same*
# login page: regular customers (the `users` table) and service
# providers (the `workers` table). Workers are the "admin"-style
# accounts referenced in the Phase 2 spec -- after login they land on
# their own Worker Dashboard instead of the customer dashboard.
#
# Flask-Login needs a single string id per session. We prefix it with
# the role ("user:<id>" / "worker:<id>") so load_user() knows which
# table to query without a second lookup.
class LoginUser(UserMixin):
    def __init__(self, obj, role):
        self.role = role  # "user" or "worker"
        self.pk = obj.worker_id if role == "worker" else obj.user_id
        self.id = f"{role}:{self.pk}"
        self.email = obj.email
        self.name = obj.full_name

    def get_id(self):
        return self.id


@login_manager.user_loader
def load_user(user_id):
    try:
        role, raw_pk = user_id.split(":", 1)
        pk = int(raw_pk)
    except (ValueError, AttributeError):
        return None

    if role == "worker":
        worker = db_session.query(Worker).filter(Worker.worker_id == pk).first()
        return LoginUser(worker, "worker") if worker else None

    user = db_session.query(User).filter(User.user_id == pk).first()
    return LoginUser(user, "user") if user else None


# ---------------------------------
# Role-based route protection
# ---------------------------------
def role_required(role):
    """Restrict a route to a single role ('user' or 'worker').
    Logged-out visitors go to the login page; logged-in accounts of
    the wrong role are bounced to *their own* dashboard instead of
    the one they tried to access."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("login.login_page"))
            if getattr(current_user, "role", None) != role:
                return redirect(dashboard_url_for(current_user.role))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def dashboard_url_for(role):
    return "/worker/dashboard" if role == "worker" else "/dashboard"

# ---------------------------------
# Helper Functions
# ---------------------------------

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def validate_phone(phone):
    if not phone:
        return False, "Phone number is required"
    phone = phone.strip()
    lk_local = re.match(r'^(07\d{8})$', phone)
    if lk_local:
        return True, '+94' + phone[1:]
    intl = re.match(r'^\+[1-9]\d{6,14}$', phone)
    if intl:
        return True, phone
    return False, "Use Sri Lankan format (07XXXXXXXX) or international format (+94XXXXXXXXX)."

def has_completed_details(user_id):
    return db_session.query(UserDetails).filter_by(user_id=user_id).first() is not None

def check_table_exists():
    inspector = inspect(engine)
    return inspector.has_table('otp_verification')

# ---------------------------------
# SMS Helper Functions
# ---------------------------------

def send_sms(phone_number, message):
    if not phone_number:
        return False, "Phone number is required"
    phone = phone_number.strip()
    phone = re.sub(r'\D', '', phone)
    if phone.startswith('0'):
        phone = phone[1:]
    if not phone.startswith('94'):
        phone = '94' + phone
    if len(phone) != 11:
        return False, f"Invalid phone number length: {phone}"
    try:
        url = "https://app.text.lk/api/v3/sms/send"
        headers = {
            'Authorization': f'Bearer {TEXT_LK_API_TOKEN}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        payload = {'recipient': phone, 'message': message}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('status') == 'success':
                    return True, "SMS sent successfully"
                else:
                    return False, f"Failed: {result.get('message', 'Unknown error')}"
            except:
                if 'success' in response.text.lower():
                    return True, "SMS sent successfully"
                else:
                    return False, f"Failed: {response.text[:100]}"
        else:
            return False, f"API error: HTTP {response.status_code}"
    except Exception as e:
        return False, f"SMS error: {str(e)}"

def send_otp_sms(phone_number, otp):
    message = f"FixGo OTP: {otp}. Valid for 10 minutes. Do not share."
    return send_sms(phone_number, message)

# ---------------------------------
# Email Helper Functions
# ---------------------------------
def send_email_otp(email, otp):
    try:
        msg = Message(
            subject="FixGo - Password Reset OTP",
            recipients=[email],
            body=f"Your OTP for password reset is: {otp}\nThis OTP is valid for 10 minutes. Do not share it with anyone."
        )
        mail.send(msg)
        return True, "Email sent successfully"
    except Exception as e:
        print(f"[ERROR] Email send error: {str(e)}")
        return False, "Network error. Please try again."

# ---------------------------------
# Routes - Pages
# ---------------------------------
@login_bp.route("/")
@login_bp.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(dashboard_url_for(current_user.role))
    return render_template("login.html")

@login_bp.route("/register", methods=["GET"])
def register_page():
    if current_user.is_authenticated:
        return redirect("/dashboard")
    return render_template("register.html")

@login_bp.route("/complete-profile", methods=["GET"])
@login_required
@role_required("user")
def complete_profile_page():
    if has_completed_details(current_user.id):
        return redirect("/dashboard")
    return render_template("complete_profile.html")

@login_bp.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    return render_template("forgot_password.html")

@login_bp.route("/reset-password", methods=["GET"])
def reset_password_page():
    if 'reset_otp_verified' not in session:
        return redirect(url_for('login.forgot_password_page'))
    return render_template("reset_password.html")

# ---------------------------------
# API Routes - OTP (Registration)
# ---------------------------------
@login_bp.route("/send-otp", methods=["POST"])
def send_otp():
    try:
        data = request.get_json(silent=True) or {}
        phone_raw = data.get("phone", "").strip()
        phone_ok, phone = validate_phone(phone_raw)
        if not phone_ok:
            return jsonify({"success": False, "field": "phone", "message": phone}), 400

        if not check_table_exists():
            from db.database import Base
            Base.metadata.create_all(engine)

        if DEBUG_MODE:
            otp = "123456"
        else:
            otp = generate_otp()

        expires = datetime.utcnow() + timedelta(minutes=10)

        db_session.query(OTPVerification).filter(
            OTPVerification.phone == phone,
            OTPVerification.is_verified == False,
            OTPVerification.purpose == 'registration'
        ).delete()

        otp_record = OTPVerification(
            phone=phone,
            otp_code=otp,
            purpose='registration',
            expires_at=expires,
            max_attempts=3
        )
        db_session.add(otp_record)
        db_session.commit()

        if DEBUG_MODE:
            return jsonify({
                "success": True,
                "message": "OTP sent successfully (DEV mode)",
                "dev_otp": "123456"
            })

        success, msg = send_otp_sms(phone, otp)
        if success:
            return jsonify({"success": True, "message": f"OTP sent to {phone}"})
        else:
            return jsonify({"success": False, "message": f"Failed to send OTP: {msg}"}), 500

    except Exception as e:
        print(f"[ERROR] send_otp: {str(e)}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@login_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    try:
        data = request.get_json(silent=True) or {}
        phone_raw = data.get("phone", "").strip()
        otp = data.get("otp", "").strip()

        phone_ok, phone = validate_phone(phone_raw)
        if not phone_ok:
            return jsonify({"success": False, "field": "phone", "message": phone}), 400

        if not otp or len(otp) != 6:
            return jsonify({"success": False, "message": "OTP must be 6 digits"}), 400

        if DEBUG_MODE:
            return jsonify({"success": True, "message": "OTP verified successfully (DEV mode)"})

        otp_record = db_session.query(OTPVerification).filter(
            OTPVerification.phone == phone,
            OTPVerification.otp_code == otp,
            OTPVerification.is_verified == False,
            OTPVerification.purpose == 'registration'
        ).first()

        if not otp_record:
            return jsonify({"success": False, "message": "Invalid OTP. Please try again."}), 400

        if datetime.utcnow() > otp_record.expires_at:
            return jsonify({"success": False, "message": "OTP has expired. Please request a new one."}), 400

        if otp_record.attempts >= otp_record.max_attempts:
            return jsonify({"success": False, "message": "Too many failed attempts. Please request a new OTP."}), 400

        otp_record.attempts += 1
        otp_record.is_verified = True
        db_session.commit()

        return jsonify({"success": True, "message": "OTP verified successfully"})

    except Exception as e:
        print(f"[ERROR] verify_otp: {str(e)}")
        return jsonify({"success": False, "message": f"Error verifying OTP: {str(e)}"}), 500

# ---------------------------------
# API Routes - Authentication
# ---------------------------------
@login_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    full_name = data.get("full_name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")
    phone_raw = data.get("phone", "").strip()
    secondary_phone_raw = data.get("secondary_phone", "").strip()
    nic = data.get("nic", "").strip()
    address = data.get("address", "").strip()
    city = data.get("city", "").strip()
    province = data.get("province", "").strip()
    terms_accepted = data.get("terms", False)
    otp_verified = data.get("otpVerified", False)

    required_fields = [full_name, email, password, confirm_password,
                       phone_raw, nic, address, city, province]
    if not all(required_fields):
        return jsonify({"success": False, "message": "All fields except secondary phone are required."}), 400

    if not terms_accepted:
        return jsonify({"success": False, "field": "terms", "message": "You must agree to the Terms & Conditions."}), 400

    if not otp_verified:
        return jsonify({"success": False, "field": "otp", "message": "Please verify your phone number with OTP first."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400

    if password != confirm_password:
        return jsonify({"success": False, "field": "confirm_password", "message": "Passwords do not match."}), 400

    phone_ok, phone = validate_phone(phone_raw)
    if not phone_ok:
        return jsonify({"success": False, "field": "phone", "message": phone}), 400

    secondary_phone = None
    if secondary_phone_raw:
        sec_ok, sec_phone = validate_phone(secondary_phone_raw)
        if not sec_ok:
            return jsonify({"success": False, "field": "secondary_phone", "message": sec_phone}), 400
        secondary_phone = sec_phone

    if db_session.query(User).filter(User.email == email).first():
        return jsonify({"success": False, "field": "email", "message": "This email is already registered."}), 400

    if db_session.query(User).filter(User.phone == phone).first():
        return jsonify({"success": False, "field": "phone", "message": "This phone number is already registered."}), 400

    try:
        hashed_pw = generate_password_hash(password)
        user = User(
            full_name=full_name,
            email=email,
            password=hashed_pw,
            phone=phone,
            secondary_phone=secondary_phone,
            phone_verified=True,
            email_verified=False,
            is_active=True
        )
        db_session.add(user)
        db_session.flush()

        details = UserDetails(
            user_id=user.user_id,
            nic=nic,
            address=address,
            city=city,
            province=province,
            phone=phone,
            secondary_phone=secondary_phone
        )
        db_session.add(details)

        audit_log = AuditLog(
            user_id=user.user_id,
            action="registration",
            details=f"User registered with email: {email}",
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db_session.add(audit_log)
        db_session.commit()

        return jsonify({"success": True, "message": "Account created successfully. Please sign in."})

    except Exception as e:
        db_session.rollback()
        return jsonify({"success": False, "message": f"Error creating account: {str(e)}"}), 500

@login_bp.route("/login", methods=["POST"])
def login():
    """
    Single login endpoint shared by customers and workers.
    We identify the account type purely by which table the email
    belongs to -- the login form itself never asks "are you an admin?".
    Customers land on /dashboard, workers land on /worker/dashboard.
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    remember = bool(data.get("remember", False))

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required."}), 400

    user = db_session.query(User).filter(User.email == email).first()
    worker = None if user else db_session.query(Worker).filter(Worker.email == email).first()

    account = user or worker
    if not account:
        return jsonify({"success": False, "field": "email", "message": "No account found with this email."}), 404

    if account.password == "GOOGLE_LOGIN":
        return jsonify({"success": False, "message": "This account uses Google Sign-In. Please click 'Sign in with Google'."}), 401

    if not check_password_hash(account.password, password):
        return jsonify({"success": False, "field": "password", "message": "Incorrect password."}), 401

    role = "worker" if worker else "user"

    if role == "user":
        if not account.is_active:
            return jsonify({"success": False, "message": "This account has been deactivated. Please contact support."}), 403
        account.last_login = datetime.utcnow()
    else:
        if not account.is_active:
            return jsonify({"success": False, "message": "This worker account has been deactivated. Please contact support."}), 403

    db_session.commit()
    login_user(LoginUser(account, role), remember=remember)

    return jsonify({
        "success": True,
        "message": "Login successful",
        "role": role,
        "redirect": dashboard_url_for(role),
        "user": {"id": account_pk(account, role), "name": account.full_name, "email": account.email, "role": role}
    })


def account_pk(account, role):
    return account.worker_id if role == "worker" else account.user_id

@login_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

@login_bp.route("/me")
def me():
    if not current_user.is_authenticated:
        return jsonify({"logged_in": False})
    return jsonify({
        "logged_in": True,
        "id": current_user.pk,
        "role": current_user.role,
        "name": current_user.name,
        "email": current_user.email
    })

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

    userinfo = token.get('userinfo')
    if not userinfo:
        try:
            resp = google.get('https://openidconnect.googleapis.com/v1/userinfo')
            userinfo = resp.json()
        except Exception as e:
            print(f"[GOOGLE userinfo fetch ERROR] {e}")
            return redirect("/login?error=google_no_userinfo")

    email = userinfo.get('email')
    name = userinfo.get('name', '')
    if not email:
        return redirect("/login?error=google_no_email")
    if not userinfo.get('email_verified', True):
        return redirect("/login?error=google_unverified")

    # Workers sign up through a separate onboarding flow (skill, NIC, etc.),
    # so Google Sign-In never *creates* a worker account -- it only logs
    # in an existing one if the Google email matches a worker on file.
    worker = db_session.query(Worker).filter(Worker.email == email).first()
    if worker:
        if not worker.is_active:
            return redirect("/login?error=account_deactivated")
        login_user(LoginUser(worker, "worker"), remember=True)
        return redirect("/worker/dashboard")

    user = db_session.query(User).filter(User.email == email).first()
    if user:
        if not user.is_active:
            return redirect("/login?error=account_deactivated")
        login_user(LoginUser(user, "user"), remember=True)
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
        login_user(LoginUser(user, "user"), remember=True)
        return redirect(url_for('login.complete_profile_page'))

@login_bp.route("/complete-profile", methods=["POST"])
@login_required
@role_required("user")
def complete_profile():
    data = request.get_json(silent=True) or {}
    nic = data.get("nic", "").strip()
    address = data.get("address", "").strip()
    phone_raw = data.get("phone", "").strip()

    if not nic or not address:
        return jsonify({"success": False, "message": "NIC and address are required."}), 400

    phone_ok, phone = validate_phone(phone_raw)
    if not phone_ok:
        return jsonify({"success": False, "field": "phone", "message": phone}), 400

    if has_completed_details(current_user.id):
        return redirect("/dashboard")

    details = UserDetails(
        user_id=current_user.id,
        nic=nic,
        address=address,
        phone=phone
    )
    try:
        db_session.add(details)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        return jsonify({"success": False, "message": f"Error saving details: {str(e)}"}), 500

    return jsonify({"success": True, "message": "Profile completed! Redirecting..."})

# ---------------------------------
# PASSWORD RESET VIA EMAIL OTP – FIXED FOR BOTH USERS AND WORKERS
# ---------------------------------

@login_bp.route("/forgot-password", methods=["POST"])
@login_bp.route("/forgot-password/send-otp", methods=["POST"])
def forgot_password():
    """
    Step 1: Request OTP for password reset.
    Always returns HTTP 200.
    Now checks both User and Worker tables.
    """
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email", "").strip().lower()

        if not email:
            return jsonify({
                "success": False,
                "field": "email",
                "message": "Email is required."
            }), 200

        # Ensure OTP table exists
        if not check_table_exists():
            from db.database import Base
            Base.metadata.create_all(engine)

        # Check both User and Worker tables
        user = db_session.query(User).filter(User.email == email).first()
        worker = db_session.query(Worker).filter(Worker.email == email).first()

        # If neither exists, still return success (don't reveal existence)
        if not user and not worker:
            return jsonify({
                "success": True,
                "message": "If that email is registered, an OTP has been sent."
            }), 200

        # Generate OTP
        if DEBUG_MODE:
            otp = "123456"
        else:
            otp = generate_otp()

        expires = datetime.utcnow() + timedelta(minutes=10)

        # Delete old unverified OTPs for this email
        db_session.query(OTPVerification).filter(
            OTPVerification.phone == email,
            OTPVerification.purpose == 'password_reset',
            OTPVerification.is_verified == False
        ).delete()

        otp_record = OTPVerification(
            phone=email,
            otp_code=otp,
            purpose='password_reset',
            expires_at=expires,
            max_attempts=3
        )
        db_session.add(otp_record)
        db_session.commit()

        if DEBUG_MODE:
            return jsonify({
                "success": True,
                "message": "OTP generated (DEV mode). Please use 123456.",
                "dev_otp": "123456"
            }), 200

        # Send real email
        success, msg = send_email_otp(email, otp)
        if success:
            return jsonify({
                "success": True,
                "message": f"OTP sent to {email}"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": msg
            }), 200

    except Exception as e:
        print(f"[ERROR] Forgot password: {str(e)}")
        return jsonify({
            "success": False,
            "message": "An unexpected error occurred. Please try again."
        }), 200

# --- ALIAS added for /forgot-password/verify-otp ---
@login_bp.route("/verify-reset-otp", methods=["POST"])
@login_bp.route("/forgot-password/verify-otp", methods=["POST"])
def verify_reset_otp():
    """
    Step 2: Verify the OTP for password reset.
    Always returns HTTP 200.
    Now checks both User and Worker tables in DEBUG mode.
    """
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email", "").strip().lower()
        otp = data.get("otp", "").strip()

        if not email or not otp:
            return jsonify({
                "success": False,
                "message": "Email and OTP are required."
            }), 200

        if len(otp) != 6:
            return jsonify({
                "success": False,
                "message": "OTP must be 6 digits."
            }), 200

        if DEBUG_MODE:
            # Accept any 6‑digit OTP, but ensure the email exists in either table
            user = db_session.query(User).filter(User.email == email).first()
            worker = db_session.query(Worker).filter(Worker.email == email).first()
            if not user and not worker:
                return jsonify({
                    "success": False,
                    "message": "No account found with that email."
                }), 200
            session['reset_otp_verified'] = email
            return jsonify({
                "success": True,
                "message": "OTP verified successfully (DEV mode)"
            }), 200

        # Production verification
        otp_record = db_session.query(OTPVerification).filter(
            OTPVerification.phone == email,
            OTPVerification.otp_code == otp,
            OTPVerification.purpose == 'password_reset',
            OTPVerification.is_verified == False
        ).first()

        if not otp_record:
            return jsonify({
                "success": False,
                "message": "Invalid OTP. Please try again."
            }), 200

        if datetime.utcnow() > otp_record.expires_at:
            return jsonify({
                "success": False,
                "message": "OTP has expired. Please request a new one."
            }), 200

        if otp_record.attempts >= otp_record.max_attempts:
            return jsonify({
                "success": False,
                "message": "Too many failed attempts. Please request a new OTP."
            }), 200

        otp_record.attempts += 1
        otp_record.is_verified = True
        db_session.commit()

        session['reset_otp_verified'] = email
        return jsonify({
            "success": True,
            "message": "OTP verified successfully. You can now reset your password."
        }), 200

    except Exception as e:
        print(f"[ERROR] Verify reset OTP: {str(e)}")
        return jsonify({
            "success": False,
            "message": "An error occurred while verifying OTP."
        }), 200

# --- ALIAS added for /forgot-password/reset-password ---
@login_bp.route("/reset-password", methods=["POST"])
@login_bp.route("/forgot-password/reset-password", methods=["POST"])
@login_bp.route("/forgot-password/reset", methods=["POST"])
def reset_password():
    """
    Step 3: Reset password after OTP verification.
    Always returns HTTP 200.
    Updates either the User or Worker table based on email.
    """
    try:
        if 'reset_otp_verified' not in session:
            return jsonify({
                "success": False,
                "message": "OTP not verified. Please go through the reset process."
            }), 200

        data = request.get_json(silent=True) or {}
        email = session['reset_otp_verified']
        new_password = data.get("new_password", "")
        confirm_password = data.get("confirm_password", "")

        if not new_password or not confirm_password:
            return jsonify({
                "success": False,
                "message": "Both password fields are required."
            }), 200

        if len(new_password) < 6:
            return jsonify({
                "success": False,
                "message": "Password must be at least 6 characters."
            }), 200

        if new_password != confirm_password:
            return jsonify({
                "success": False,
                "field": "confirm_password",
                "message": "Passwords do not match."
            }), 200

        # Look for the account in both tables
        user = db_session.query(User).filter(User.email == email).first()
        worker = db_session.query(Worker).filter(Worker.email == email).first()

        if not user and not worker:
            session.pop('reset_otp_verified', None)
            return jsonify({
                "success": False,
                "message": "Account not found."
            }), 200

        hashed = generate_password_hash(new_password)

        if user:
            user.password = hashed
        elif worker:
            worker.password = hashed

        db_session.commit()

        session.pop('reset_otp_verified', None)
        # Clean up used OTP records
        db_session.query(OTPVerification).filter(
            OTPVerification.phone == email,
            OTPVerification.purpose == 'password_reset'
        ).delete()
        db_session.commit()

        return jsonify({
            "success": True,
            "message": "Password has been reset successfully. Please log in."
        }), 200

    except Exception as e:
        db_session.rollback()
        print(f"[ERROR] Reset password: {str(e)}")
        return jsonify({
            "success": False,
            "message": "An error occurred while resetting your password."
        }), 200