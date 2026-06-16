from sqlalchemy.orm import sessionmaker
from database import engine, User, Worker, Service

# Create session
Session = sessionmaker(bind=engine)
session = Session()

try:
    # Insert sample users
    users = [
        User(
            full_name="John Doe",
            email="john@example.com",
            password="123456",
            phone="0712345678"
        ),
        User(
            full_name="Jane Smith",
            email="jane@example.com",
            password="123456",
            phone="0771234567"
        )
    ]

    # Insert sample workers
    workers = [
        Worker(
            full_name="Alex Perera",
            email="alex@example.com",
            password="123456",
            phone="0711111111",
            skill="Electrician",
            rating=4.5,
            is_verified=1
        ),
        Worker(
            full_name="Nimal Silva",
            email="nimal@example.com",
            password="123456",
            phone="0722222222",
            skill="Plumber",
            rating=4.7,
            is_verified=1
        )
    ]

    # Insert sample services
    services = [
        Service(
            name="Electrical Repair",
            category="Electrical",
            description="Electrical installation and repair services.",
            price=2500
        ),
        Service(
            name="Plumbing Service",
            category="Plumbing",
            description="General plumbing maintenance and repairs.",
            price=2000
        )
    ]

    session.add_all(users)
    session.add_all(workers)
    session.add_all(services)

    session.commit()

    print("Sample data inserted successfully!")

except Exception as e:
    session.rollback()
    print("Error inserting data:", e)

finally:
    session.close()