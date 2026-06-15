import os
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine

# Get absolute path to the project root (FixGo-AI-)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Create an 'instance' folder (standard Flask location) inside the project root
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)

# Database file path inside instance folder
DB_PATH = os.path.join(INSTANCE_DIR, 'fixgo.db')
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL)

Base = declarative_base()

# USERS
class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    full_name = Column(String)
    email = Column(String, unique=True)
    password = Column(String)
    phone = Column(String)

# WORKERS
class Worker(Base):
    __tablename__ = "workers"

    worker_id = Column(Integer, primary_key=True)
    full_name = Column(String)
    email = Column(String)
    rating = Column(Float)

# SERVICES
class Service(Base):
    __tablename__ = "services"

    service_id = Column(Integer, primary_key=True)
    service_name = Column(String)
    price = Column(Float)

# BOOKINGS
class Booking(Base):
    __tablename__ = "bookings"

    booking_id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    worker_id = Column(Integer)
    status = Column(String)

# Create tables
Base.metadata.create_all(engine)

print("Database created successfully")