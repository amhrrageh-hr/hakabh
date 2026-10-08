import sys
sys.path.insert(0, ".")
import datetime
import database as db_mod

d_today = datetime.datetime(2026, 8, 19, 10, 0)
d_past = datetime.datetime(2026, 8, 10, 10, 0)

# Test 1: New unpaid installment created
n1 = db_mod.build_installment_note(is_paid=False, due_date=d_today)
print("Test 1 (New Unpaid):", n1)
assert n1 == "قسط غير مسدد"

# Test 2: Paid on time (same date)
n2 = db_mod.build_installment_note(is_paid=True, due_date=d_today, paid_date=d_today)
print("Test 2 (Paid on time):", n2)
assert n2 == "شكراً، تم سداد القسط"

# Test 3: Paid late (paid_date > due_date)
n3 = db_mod.build_installment_note(is_paid=True, due_date=d_past, paid_date=d_today)
print("Test 3 (Paid late):", n3)
assert n3 == "تم سداد القسط متأخراً، يرجى الالتزام"

# Test 4: Paid late with staff name and user note
n4 = db_mod.build_installment_note(is_paid=True, due_date=d_past, paid_date=d_today, user_note="حوالة بنكية", staff_name="علي")
print("Test 4 (With staff & user note):", n4)

print("ALL TESTS PASSED!")
