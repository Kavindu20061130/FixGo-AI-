from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash
from database import engine, User, Worker

Session = sessionmaker(bind=engine)
session = Session()

try:
    # Fix user passwords
    users = session.query(User).all()

    for user in users:
        if not user.password.startswith("scrypt:"):
            user.password = generate_password_hash(user.password)

    # Fix worker passwords
    workers = session.query(Worker).all()

    for worker in workers:
        if not worker.password.startswith("scrypt:"):
            worker.password = generate_password_hash(worker.password)

    session.commit()

    print("Passwords hashed successfully!")

except Exception as e:
    session.rollback()
    print("Error:", e)

finally:
    session.close()