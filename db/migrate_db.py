from sqlalchemy import create_engine, text

# Use the same DATABASE_URL as your database.py
DATABASE_URL = "sqlite:///../db/fixgo.db"   # adjust if needed

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

with engine.connect() as conn:
    # Add created_at to users
    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        print("✓ Added created_at to users")
    except Exception as e:
        print("users.created_at already exists or error:", e)

    # Add created_at to bookings
    try:
        conn.execute(text("ALTER TABLE bookings ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        print("✓ Added created_at to bookings")
    except Exception as e:
        print("bookings.created_at already exists or error:", e)

    # Add indexes on email columns (for faster login)
    try:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workers_email ON workers(email)"))
        print("✓ Added indexes on email columns")
    except Exception as e:
        print("Index error:", e)

    conn.commit()

print("Migration done.")