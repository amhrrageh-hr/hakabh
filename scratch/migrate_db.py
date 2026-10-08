import sqlite3
import os

db_path = "hakbah.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE categories ADD COLUMN start_date DATETIME")
        print("Added start_date column")
    except sqlite3.OperationalError:
        print("start_date column already exists")
        
    try:
        cursor.execute("ALTER TABLE categories ADD COLUMN end_date DATETIME")
        print("Added end_date column")
    except sqlite3.OperationalError:
        print("end_date column already exists")
        
    conn.commit()
    conn.close()
    print("Migration complete")
else:
    print("Database not found")
