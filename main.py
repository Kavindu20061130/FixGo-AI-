from flask import Flask
from datetime import timedelta

# Change: import from backend.login instead of login
from backend.login import login_bp, login_manager, bcrypt, oauth

app = Flask(__name__, template_folder="frontend")

# ---------------------------------
# Security Configuration
# ---------------------------------

app.secret_key = "fixgo_super_secret_key_change_in_production"

# Session cookie settings
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False   # Set True in production (HTTPS)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

# ---------------------------------
# Extension Init
# ---------------------------------

bcrypt.init_app(app)
login_manager.init_app(app)
oauth.init_app(app)

# ---------------------------------
# Blueprints
# ---------------------------------

app.register_blueprint(login_bp)

# ---------------------------------
# Run
# ---------------------------------

if __name__ == "__main__":
    app.run(debug=True)