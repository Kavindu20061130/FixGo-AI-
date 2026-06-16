from flask import Flask
from datetime import timedelta

from backend.login import login_bp, login_manager, oauth, mail
from backend.home import home_bp

# ---------------------------------
# Flask App Setup
# ---------------------------------
app = Flask(
    __name__,
    template_folder="frontend",
    static_folder="asset",
    static_url_path="/asset"
)

# ---------------------------------
# Security Configuration
# ---------------------------------
app.secret_key = "fixgo_super_secret_key_change_in_production"

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False   # Set True in production (HTTPS)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

# ---------------------------------
# Flask-Mail Configuration
# Use environment variables for credentials – never hard-code!
# Set these in your .env / system environment:
#   MAIL_SERVER      (e.g. smtp.gmail.com)
#   MAIL_PORT        (e.g. 587)
#   MAIL_USERNAME    (your Gmail address)
#   MAIL_PASSWORD    (Gmail App Password – NOT your login password)
#   MAIL_DEFAULT_SENDER (same as MAIL_USERNAME usually)
# ---------------------------------
import os
app.config["MAIL_SERVER"]          = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"]            = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"]         = True
app.config["MAIL_USE_SSL"]         = False
app.config["MAIL_USERNAME"]        = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"]        = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"]  = os.environ.get(
    "MAIL_DEFAULT_SENDER",
    os.environ.get("MAIL_USERNAME", "noreply@fixgo.lk")
)

# ---------------------------------
# Extension Init
# ---------------------------------
login_manager.init_app(app)
oauth.init_app(app)
mail.init_app(app)

# ---------------------------------
# Blueprints
# ---------------------------------
app.register_blueprint(login_bp)
app.register_blueprint(home_bp)

# ---------------------------------
# Root route
# ---------------------------------
@app.route("/")
def index():
    return "FixGo AI is running successfully 🚀"

# ---------------------------------
# Run Server
# ---------------------------------
if __name__ == "__main__":
    app.run(debug=True)