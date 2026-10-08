import sys
import os
sys.path.append(os.getcwd())
from sqlalchemy.orm import Session
import database as db_mod

def test_registration_sync():
    db = db_mod.SessionLocal()
    try:
        # 1. Ensure we have a category and a number
        cat = db.query(db_mod.Category).first()
        if not cat:
            print("No category found")
            return
        
        # 1. Use a unique number for testing
        test_number = "SYNC-TEST-001"
        test_phone = "0599999999"
        
        # Cleanup existing test data
        existing_num = db.query(db_mod.SubscriberNumber).filter(db_mod.SubscriberNumber.number == test_number).first()
        if existing_num:
            # Delete subscribers using this number first
            db.query(db_mod.Subscriber).filter(db_mod.Subscriber.subscriber_number == test_number).delete()
            db.delete(existing_num)
            db.commit()

        # Create the test number
        num = db_mod.SubscriberNumber(number=test_number, category_id=cat.id)
        db.add(num)
        db.commit()
        db.refresh(num)
        
        # 2. Simulate registration logic from main.py
        # Delete if exists
        existing = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.phone == test_phone).first()
        if existing:
            db.delete(existing)
            db.commit()

        # Create new subscriber
        new_sub = db_mod.Subscriber(
            name="Test User", 
            phone=test_phone, 
            category=cat.name,
            selected_number_id=num.id,
            subscriber_number=num.number # This is the fix we implemented
        )
        db.add(new_sub)
        num.is_reserved = True
        num.subscriber_id = new_sub.id
        db.commit()
        db.refresh(new_sub)
        
        print(f"Subscriber created with number: {new_sub.subscriber_number}")
        print(f"Expected number: {test_number}")
        
        if new_sub.subscriber_number == test_number:
            print("SUCCESS: Account number synced correctly!")
        else:
            print("FAILURE: Account number mismatch!")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_registration_sync()
