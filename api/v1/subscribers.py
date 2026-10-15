import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import database as db_mod
from api.auth import get_db, verify_admin_api_key
from api.schemas import (
    SubscriberCreate, SubscriberUpdate, SubscriberOut, 
    AccountStatementOut, AccountStatementPayment
)

router = APIRouter(prefix="/subscribers", tags=["Subscribers"], dependencies=[Depends(verify_admin_api_key)])

@router.get("", response_model=List[SubscriberOut])
def list_subscribers(
    category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    جلب قائمة المشتركين مع حساب حالتهم المالية وعدد الدفعات
    مباشرة على الخادم وإرجاع حزمة بيانات خفيفة وسريعة.
    """
    query = db.query(db_mod.Subscriber)
    
    if search:
        s_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                db_mod.Subscriber.name.ilike(s_term),
                db_mod.Subscriber.phone.ilike(s_term),
                db_mod.Subscriber.subscriber_number.ilike(s_term)
            )
        )
    
    if status:
        query = query.filter(db_mod.Subscriber.status == status)
        
    if category and category != "الكل":
        query = query.filter(db_mod.Subscriber.category == category)
        
    subs = query.order_by(db_mod.Subscriber.id.desc()).offset(skip).limit(limit).all()
    if not subs:
        return []

    # حساب الحالة المالية وإحصائيات الدفع على الخادم (سريع جداً < 0.05 ثانية)
    fin_status_map = db_mod.calculate_financial_status_batch(subs, db)
    sub_ids = [s.id for s in subs]
    
    payment_stats = dict(
        (r[0], (int(r[1]), float(r[2] or 0.0))) for r in db.query(
            db_mod.Payment.subscriber_id,
            func.count(db_mod.Payment.id),
            func.sum(db_mod.Payment.amount)
        ).filter(
            db_mod.Payment.subscriber_id.in_(sub_ids),
            db_mod.Payment.is_paid == True
        ).group_by(db_mod.Payment.subscriber_id).all()
    )

    results = []
    for s in subs:
        p_count, p_total = payment_stats.get(s.id, (0, 0.0))
        item = SubscriberOut.model_validate(s)
        item.fin_status = fin_status_map.get(s.id, s.status)
        item.paid_count = p_count
        item.total_paid = p_total
        results.append(item)

    return results

@router.get("/{sub_id}", response_model=SubscriberOut)
def get_subscriber(sub_id: int, db: Session = Depends(get_db)):
    sub = db.get(db_mod.Subscriber, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="المشترك غير موجود")
    
    item = SubscriberOut.model_validate(sub)
    item.fin_status = db_mod.calculate_financial_status(sub, db)
    return item

@router.get("/{sub_id}/statement", response_model=AccountStatementOut)
def get_subscriber_account_statement(sub_id: int, db: Session = Depends(get_db)):
    """جلب كشف حساب المشترك المالي كاملاً ومفصلاً في طلب واحد"""
    sub = db.get(db_mod.Subscriber, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="المشترك غير موجود")

    payments = db.query(db_mod.Payment).filter(
        db_mod.Payment.subscriber_id == sub_id
    ).order_by(
        db_mod.Payment.cycle_number.desc(),
        db_mod.Payment.installment_number.desc(),
        db_mod.Payment.due_date.desc(),
        db_mod.Payment.id.desc()
    ).all()

    total_paid = sum(p.amount for p in payments if p.is_paid)
    total_remaining = sum(p.amount for p in payments if not p.is_paid)
    paid_count = sum(1 for p in payments if p.is_paid)

    sub_out = SubscriberOut.model_validate(sub)
    sub_out.fin_status = db_mod.calculate_financial_status(sub, db)

    p_list = [
        AccountStatementPayment(
            id=p.id,
            cycle_number=p.cycle_number,
            installment_number=p.installment_number,
            amount=p.amount,
            due_date=p.due_date.strftime("%Y-%m-%d") if p.due_date else None,
            paid_date=p.paid_date.strftime("%Y-%m-%d %H:%M") if p.paid_date else None,
            is_paid=p.is_paid,
            note=p.note
        ) for p in payments
    ]

    return AccountStatementOut(
        subscriber=sub_out,
        total_paid=total_paid,
        total_remaining=total_remaining,
        paid_count=paid_count,
        total_count=len(payments),
        payments=p_list
    )

@router.post("", response_model=SubscriberOut, status_code=status.HTTP_201_CREATED)
def create_subscriber(data: SubscriberCreate, db: Session = Depends(get_db)):
    clean_phone = data.phone.strip()
    existing = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.phone == clean_phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً لمشترك آخر")

    new_sub = db_mod.Subscriber(
        name=data.name.strip(),
        phone=clean_phone,
        category=data.category,
        national_id=data.national_id,
        address=data.address,
        status="accepted"
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    return SubscriberOut.model_validate(new_sub)

@router.put("/{sub_id}", response_model=SubscriberOut)
def update_subscriber(sub_id: int, data: SubscriberUpdate, db: Session = Depends(get_db)):
    sub = db.get(db_mod.Subscriber, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="المشترك غير موجود")

    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(sub, field, val)

    db.commit()
    db.refresh(sub)
    return SubscriberOut.model_validate(sub)

@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscriber(sub_id: int, db: Session = Depends(get_db)):
    sub = db.get(db_mod.Subscriber, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="المشترك غير موجود")

    # حذف الأقساط المرتبطة
    db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sub_id).delete()
    db.delete(sub)
    db.commit()
    return None
