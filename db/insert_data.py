import sqlite3

# connect database
conn = sqlite3.connect("../db/fixgo.db")

cursor = conn.cursor()

# insert user
cursor.execute("""
INSERT INTO users
(full_name,email,password,phone)

VALUES
(
'Kavindu',
'kavindu@gmail.com',
'abc123',
'0771234567'
)
""")

conn.commit()

print("User inserted successfully")

conn.close()