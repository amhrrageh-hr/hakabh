from database import SessionLocal, Setting

def main():
    db = SessionLocal()
    keys = ["admin_login_enabled", "admin_username", "admin_password_hash"]
    removed = []
    try:
        for k in keys:
            s = db.query(Setting).filter(Setting.key == k).first()
            if s:
                db.delete(s)
                removed.append(k)
        db.commit()
        if removed:
            print("Removed settings:", removed)
        else:
            print("No matching settings found.")
    except Exception as e:
        print("Error:", e)
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    main()
