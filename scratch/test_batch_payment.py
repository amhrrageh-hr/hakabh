import os
import datetime
import database as db_mod

def test_batch_payment_distribution():
    db = db_mod.SessionLocal()
    try:
        # Create test category with installment amount 1000
        cat = db.query(db_mod.Category).filter(db_mod.Category.name == "فئة تجريبية").first()
        if not cat:
            cat = db_mod.Category(name="فئة تجريبية", amount=1000.0, max_cycles=10, max_installments=12)
            db.add(cat)
            db.commit()

        # Create test subscriber
        sub = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.phone == "0500000000").first()
        if not sub:
            sub = db_mod.Subscriber(name="عميل تجريبي", phone="0500000000", category="فئة تجريبية", status="accepted")
            db.add(sub)
            db.commit()

        # Clean existing payments for this test subscriber
        db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sub.id).delete()
        db.commit()

        # Simulate batch payment of 5000 starting cycle 1, inst 1
        amount = 5000.0
        due_date = datetime.datetime.now()
        cycle = 1
        inst = 1
        note = "تسديد تجريبي 5000"

        cat_amount = cat.amount
        max_c = cat.max_cycles
        max_i = cat.max_installments

        remaining = amount
        created = 0
        updated = 0

        targets = db.query(db_mod.Payment).filter(
            db_mod.Payment.subscriber_id == sub.id,
            db_mod.Payment.is_paid == False
        ).order_by(db_mod.Payment.cycle_number.asc(), db_mod.Payment.installment_number.asc()).all()

        last_processed_c = 0
        last_processed_i = 0

        for p in targets:
            if remaining <= 0: break
            if remaining < p.amount:
                balance = p.amount - remaining
                p.amount = remaining
                p.is_paid = True
                p.paid_date = due_date
                new_unpaid = db_mod.Payment(subscriber_id=sub.id, amount=balance, due_date=p.due_date, is_paid=False, cycle_number=p.cycle_number, installment_number=p.installment_number, note="متبقي")
                db.add(new_unpaid)
                remaining = 0
                updated += 1
            else:
                p.is_paid = True
                p.paid_date = due_date
                remaining -= p.amount
                updated += 1
            last_processed_c = p.cycle_number
            last_processed_i = p.installment_number

        if remaining > 0:
            if last_processed_c > 0:
                curr_c, curr_i = last_processed_c, last_processed_i + 1
                if curr_i > max_i:
                    curr_i = 1; curr_c += 1
            else:
                curr_c, curr_i = cycle, inst

            safety_counter = 0
            max_safety = max_c * max_i

            while remaining > 0 and curr_c <= max_c and safety_counter < max_safety:
                safety_counter += 1
                p = db.query(db_mod.Payment).filter(
                    db_mod.Payment.subscriber_id == sub.id,
                    db_mod.Payment.cycle_number == curr_c,
                    db_mod.Payment.installment_number == curr_i
                ).first()

                if p and p.is_paid:
                    curr_i += 1
                    if curr_i > max_i: curr_i = 1; curr_c += 1
                    continue

                pay_now = min(remaining, cat_amount)
                if p:
                    p.amount = pay_now; p.is_paid = True; p.paid_date = due_date; p.due_date = due_date
                    updated += 1
                else:
                    new_p = db_mod.Payment(subscriber_id=sub.id, amount=pay_now, due_date=due_date, paid_date=due_date, is_paid=True, installment_number=curr_i, cycle_number=curr_c, note=note)
                    db.add(new_p)
                    created += 1

                if pay_now < cat_amount:
                    new_unpaid = db_mod.Payment(subscriber_id=sub.id, amount=cat_amount - pay_now, due_date=due_date, is_paid=False, cycle_number=curr_c, installment_number=curr_i, note="متبقي")
                    db.add(new_unpaid)
                    remaining = 0
                else:
                    remaining -= pay_now

                curr_i += 1
                if curr_i > max_i: curr_i = 1; curr_c += 1

        db.commit()

        # Query created payments
        payments = db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sub.id, db_mod.Payment.is_paid == True).all()
        print(f"Total paid payment records created: {len(payments)}")
        for p in payments:
            print(f"  - Cycle {p.cycle_number}, Inst {p.installment_number}: Amount = {p.amount}")

        assert len(payments) == 5, f"Expected 5 payments of 1000 each, got {len(payments)}"
        assert sum(p.amount for p in payments) == 5000.0, "Total sum should be 5000"
        print("TEST PASSED SUCCESSFULLY!")

        # Clean up test data
        db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sub.id).delete()
        db.query(db_mod.Subscriber).filter(db_mod.Subscriber.id == sub.id).delete()
        db.query(db_mod.Category).filter(db_mod.Category.id == cat.id).delete()
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    test_batch_payment_distribution()
