from sqlalchemy import create_engine, Column, Integer, String, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()
engine = create_engine("sqlite:///db/fixgo.db", echo=True)


class User(Base):
    __tablename__ = "users"
    user_id   = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False)
    email     = Column(String, unique=True, nullable=False)
    password  = Column(String, nullable=False)   # bcrypt hash or "GOOGLE_LOGIN"
    phone     = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Worker(Base):
    __tablename__ = "workers"
    worker_id   = Column(Integer, primary_key=True, autoincrement=True)
    full_name   = Column(String, nullable=False)
    email       = Column(String, unique=True, nullable=False)
    password    = Column(String, nullable=False)
    phone       = Column(String)
    skill       = Column(String)
    rating      = Column(Float, default=0.0)
    is_verified = Column(Integer, default=0)
    created_at  = Column(DateTime, default=datetime.datetime.utcnow)


class Service(Base):
    __tablename__ = "services"
    service_id  = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String, nullable=False)
    category    = Column(String)
    description = Column(Text)
    price       = Column(Float)


class Booking(Base):
    __tablename__ = "bookings"
    booking_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.user_id"))
    worker_id  = Column(Integer, ForeignKey("workers.worker_id"))
    service_id = Column(Integer, ForeignKey("services.service_id"))
    status     = Column(String, default="requested")  # requested/accepted/in_progress/completed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user    = relationship("User")
    worker  = relationship("Worker")
    service = relationship("Service")


class UserDetails(Base):
    __tablename__ = 'user_details'
    detail_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    nic = Column(String(20), nullable=False)
    address = Column(Text, nullable=False)
    phone = Column(String(15))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)   # ✅ fixed

    user = relationship("User", backref="details")


class Review(Base):
    __tablename__ = "reviews"
    review_id  = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.booking_id"))
    rating     = Column(Integer)
    comment    = Column(Text)


def init_db():
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()
    print("Database created successfully.")