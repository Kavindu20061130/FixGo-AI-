from sqlalchemy import create_engine, Column, Integer, String, Float, Text, ForeignKey, DateTime, Boolean
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
    phone     = Column(String, nullable=False)   # Now mandatory
    secondary_phone = Column(String, nullable=True)  # NEW - optional secondary phone
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)

    # Relationships - FIXED: Use back_populates instead of backref to avoid conflicts
    details = relationship("UserDetails", back_populates="user", uselist=False, cascade="all, delete-orphan")
    otps = relationship("OTPVerification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


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
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)


class Service(Base):
    __tablename__ = "services"
    service_id  = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String, nullable=False)
    category    = Column(String)
    description = Column(Text)
    price       = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)


class Booking(Base):
    __tablename__ = "bookings"
    booking_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.user_id"))
    worker_id  = Column(Integer, ForeignKey("workers.worker_id"))
    service_id = Column(Integer, ForeignKey("services.service_id"))
    status     = Column(String, default="requested")  # requested/accepted/in_progress/completed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    scheduled_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    user    = relationship("User")
    worker  = relationship("Worker")
    service = relationship("Service")


class UserDetails(Base):
    __tablename__ = 'user_details'
    detail_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    nic = Column(String(20), nullable=False)
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)  # NEW - City (mandatory)
    province = Column(String(50), nullable=False)  # NEW - Sri Lankan province (mandatory)
    phone = Column(String(15), nullable=False)  # Now mandatory
    secondary_phone = Column(String(15), nullable=True)  # NEW - optional secondary phone
    postal_code = Column(String(10), nullable=True)  # NEW - optional postal code
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationship - FIXED: Use back_populates instead of backref
    user = relationship("User", back_populates="details")


class Review(Base):
    __tablename__ = "reviews"
    review_id  = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.booking_id"))
    rating     = Column(Integer)
    comment    = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# ============================================================
# NEW TABLE: OTP Verification
# ============================================================
class OTPVerification(Base):
    __tablename__ = 'otp_verification'
    otp_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    otp_code = Column(String(10), nullable=False)
    purpose = Column(String(50), nullable=False)  # registration, login, password_reset, phone_verification
    is_verified = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)

    # Relationship - FIXED
    user = relationship("User", back_populates="otps")


# ============================================================
# NEW TABLE: Audit Log (for tracking)
# ============================================================
class AuditLog(Base):
    __tablename__ = 'audit_log'
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    action = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationship - FIXED
    user = relationship("User", back_populates="audit_logs")


def init_db():
    Base.metadata.create_all(engine)
    print("Database tables created successfully!")


if __name__ == "__main__":
    init_db()