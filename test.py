from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)

# SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///fixgo.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "your-secret-key"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
bcrypt = Bcrypt(app)
oauth = OAuth(app)

print("All packages loaded successfully!")