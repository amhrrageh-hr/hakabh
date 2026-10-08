import sqlite3, os
# determine db path
base_dir = os.path.dirname(os.path.abspath(__file__))
# project root is parent of scratch
project_root = os.path.dirname(base_dir)
db_path = os.path.join(project_root, 'hakbah.db')
if not os.path.exists(db_path):
    print('Database not found at', db_path)
else:
    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info('staff')").fetchall()]
    print('staff columns:', cols)
    conn.close()
