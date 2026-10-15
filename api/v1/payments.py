import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_
import database as db_mod
from api.auth import get_db, verify_admin_api_key
from api.schemas import PaymentOut, QuickPayRequest

router = APIRouter(prefix="/payments", tags=["Payments"], dependencies=[Depends(verify_admin_api_key)])

class DefaulterItem(BaseModel):
    payment_id: int
    subscriber_id: int
    subscriber_name: str
    phone: str
    category: str
    cycle_number: int
    installment_number: int
    due_date: Optional[str] = None
    amount: float

class BatchPayRequest(BaseModel):
    payment_ids: Optional[List[int]] = None
    subscriber_id: Optional[int] = None
    cycle_number: Optional[int] = None
    pay_all_overdue: Optional[bool] = False
    category: Optional[str] = None
    staff_id: Optional[int] = None
    note: Optional[str] = None

class BatchPayResponse(BaseModel):
    success: bool
    paid_count: int
    total_amount: float
    message: str

@router.post("/quick-pay", response_model=PaymentOut)
def quick_pay(req: QuickPayRequest, db: Session = Depends(get_db)):
    """تسجيل سداد قسط محدد بسرعة وأمان مع التوثيق"""
    payment = db.get(db_mod.Payment, req.payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="القسط غير موجود")

    if payment.is_paid:
        return PaymentOut.model_validate(payment)

    payment.is_paid = True
    payment.paid_date = datetime.datetime.now()
    if req.staff_id:
        payment.staff_id = req.staff_id
        payment.is_staff_settled = False

    # تسجيل الملاحظة
    note_msg = req.note or "سداد سريع عبر لوحة التحكم"
    default_notes = {"قسط يومي غير مسدد", "قسط مستحق عند التسجيل"}
    existing = (payment.note or "").strip()
    if existing and not any(existing.startswith(d) for d in default_notes):
        payment.note = f"{existing} | {note_msg}"
    else:
        payment.note = note_msg

    db.commit()
    db.refresh(payment)
    return PaymentOut.model_validate(payment)

@router.post("/batch-pay", response_model=BatchPayResponse)
def batch_pay(req: BatchPayRequest, db: Session = Depends(get_db)):
    """سداد دفعة من الأقساط (سواء قائمة معرفات، أو كل متأخرات فئة/مشترك) في عملية واحدة"""
    now_val = datetime.datetime.now()
    query = db.query(db_mod.Payment).filter(db_mod.Payment.is_paid == False)

    if req.payment_ids:
        query = query.filter(db_mod.Payment.id.in_(req.payment_ids))
    elif req.subscriber_id:
        query = query.filter(db_mod.Payment.subscriber_id == req.subscriber_id)
        if req.cycle_number:
            query = query.filter(db_mod.Payment.cycle_number == req.cycle_number)
    elif req.pay_all_overdue:
        query = query.join(db_mod.Subscriber).filter(
            db_mod.Payment.due_date < now_val,
            db_mod.Subscriber.status == "accepted"
        )
        if req.category and req.category != "الكل":
            query = query.filter(db_mod.Subscriber.category == req.category)
    else:
        raise HTTPException(status_code=400, detail="يرجى تحديد الأقساط المطلوب سدادها")

    payments = query.all()
    if not payments:
        return BatchPayResponse(success=True, paid_count=0, total_amount=0.0, message="لا توجد أقساط غير مسددة مطابقة")

    paid_count = 0
    total_amount = 0.0
    for p in payments:
        p.is_paid = True
        p.paid_date = now_val
        if req.staff_id:
            p.staff_id = req.staff_id
            p.is_staff_settled = False
        if req.note:
            p.note = req.note
        paid_count += 1
        total_amount += p.amount

    db.commit()
    return BatchPayResponse(
        success=True,
        paid_count=paid_count,
        total_amount=total_amount,
        message=f"تم سداد {paid_count} قسطاً بنجاح بإجمالي {total_amount:,.2f} ر.ي"
    )

@router.get("/defaulters", response_model=List[DefaulterItem])
def list_defaulters(
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db)
):
    """جلب قائمة الأقساط المتأخرة غير المسددة مع تفاصيل المشتركين"""
    now_val = datetime.datetime.now()
    query = db.query(db_mod.Payment, db_mod.Subscriber).join(
        db_mod.Subscriber, db_mod.Payment.subscriber_id == db_mod.Subscriber.id
    ).filter(
        db_mod.Payment.is_paid == False,
        db_mod.Payment.due_date < now_val,
        db_mod.Subscriber.status == "accepted"
    )

    if category and category != "الكل":
        query = query.filter(db_mod.Subscriber.category == category)

    if search:
        s_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                db_mod.Subscriber.name.ilike(s_term),
                db_mod.Subscriber.phone.ilike(s_term),
                db_mod.Subscriber.subscriber_number.ilike(s_term)
            )
        )

    rows = query.order_by(db_mod.Payment.due_date.asc()).offset(skip).limit(limit).all()

    items = []
    for p, sub in rows:
        items.append(
            DefaulterItem(
                payment_id=p.id,
                subscriber_id=sub.id,
                subscriber_name=sub.name,
                phone=sub.phone,
                category=sub.category or "-",
                cycle_number=p.cycle_number,
                installment_number=p.installment_number,
                due_date=p.due_date.strftime("%Y-%m-%d") if p.due_date else None,
                amount=p.amount
            )
        )
    return items
