import database as db_mod
import security
from sqlalchemy.orm import Session

s = db_mod.SessionLocal()
try:
    existing = s.query(db_mod.Subscriber).filter(db_mod.Subscriber.phone == '000000000').first()
    if existing:
        print('Test subscriber already exists:', existing.id)
    else:
        cat = s.query(db_mod.Category).first()
        sub = db_mod.Subscriber(
            name='Test User',
            phone='000000000',
            password=security.hash_password('password123'),
            category=cat.name if cat else 'الفئة الأساسية',
            subscriber_number='T-0001'
        )
        s.add(sub)
        s.flush()
        # add a few payments
        for i in range(1,7):
            p = db_mod.Payment(
                subscriber_id=sub.id,
                amount=100.0,
                due_date=None,
                is_paid=(i<=2),
                installment_number=i,
                cycle_number=1
            )
            s.add(p)
        s.commit()
        print('Created test subscriber with id', sub.id)
finally:
    s.close()
