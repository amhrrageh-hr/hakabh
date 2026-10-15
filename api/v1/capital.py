import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
import database as db_mod
from api.auth import get_db, verify_admin_api_key
from api.schemas import CapitalStatsOut, CapitalCategoryItem

router = APIRouter(prefix="/capital", tags=["Capital"], dependencies=[Depends(verify_admin_api_key)])

class SubscriberStandingItem(BaseModel):
    subscriber_id: int
    name: str
    phone: str
    category: str
    fin_status: str
    paid_count: int
    total_paid: float
    unpaid_count: int
    total_unpaid: float
    arrears_count: int
    total_arrears: float

@router.get("/stats", response_model=CapitalStatsOut)
def get_capital_stats(category: Optional[str] = None, db: Session = Depends(get_db)):
    """حساب مؤشرات رأس المال والسيولة المجمعة في استعلام فائق السرعة على الخادم"""
    sel_cat = category if category and category != "الكل" else None
    now_val = datetime.datetime.now()

    base_filter = [db_mod.Subscriber.status == "accepted"]
    if sel_cat:
        base_filter.append(db_mod.Subscriber.category == sel_cat)

    stats_row = db.query(
        func.coalesce(func.sum(db_mod.Payment.amount), 0).label("expected"),
        func.coalesce(func.sum(case((db_mod.Payment.is_paid == True, db_mod.Payment.amount), else_=0)), 0).label("collected"),
        func.coalesce(func.sum(case(((db_mod.Payment.is_paid == False) & (db_mod.Payment.due_date < now_val), db_mod.Payment.amount), else_=0)), 0).label("arrears")
    ).join(db_mod.Subscriber, db_mod.Payment.subscriber_id == db_mod.Subscriber.id).filter(*base_filter).first()

    total_expected = float(stats_row.expected) if stats_row else 0.0
    total_collected = float(stats_row.collected) if stats_row else 0.0
    total_arrears = float(stats_row.arrears) if stats_row else 0.0

    # المصاريف
    exp_query = db.query(func.coalesce(func.sum(db_mod.Expense.amount), 0))
    if sel_cat:
        exp_query = exp_query.filter(db_mod.Expense.subscriber_category == sel_cat)
    total_expenses = float(exp_query.scalar() or 0.0)

    # مستحقات الفائزين المسددة
    winner_payouts_query = db.query(func.coalesce(func.sum(db_mod.Winner.payout_amount), 0)).filter(
        db_mod.Winner.is_received == True
    )
    if sel_cat:
        winner_payouts_query = winner_payouts_query.filter(
            db_mod.Winner.subscriber_number.in_(
                db.query(db_mod.Subscriber.subscriber_number).filter(db_mod.Subscriber.category == sel_cat)
            )
        )
    total_winner_payouts = float(winner_payouts_query.scalar() or 0.0)

    net_cash = total_collected - total_expenses - total_winner_payouts

    # تفصيل الفئات
    categories = db.query(db_mod.Category).all()
    cat_stats_query = db.query(
        db_mod.Subscriber.category,
        func.count(func.distinct(db_mod.Subscriber.id)).label("sub_count"),
        func.coalesce(func.sum(db_mod.Payment.amount), 0).label("expected"),
        func.coalesce(func.sum(case((db_mod.Payment.is_paid == True, db_mod.Payment.amount), else_=0)), 0).label("collected")
    ).join(db_mod.Payment, db_mod.Subscriber.id == db_mod.Payment.subscriber_id, isouter=True).filter(
        db_mod.Subscriber.status == "accepted"
    ).group_by(db_mod.Subscriber.category)

    if sel_cat:
        cat_stats_query = cat_stats_query.filter(db_mod.Subscriber.category == sel_cat)

    cat_stats_map = {row[0]: row for row in cat_stats_query.all()}

    cat_breakdown = []
    for cat in categories:
        if sel_cat and cat.name != sel_cat:
            continue
        stats = cat_stats_map.get(cat.name)
        sub_count = stats.sub_count if stats else 0
        expected = float(stats.expected) if stats else 0.0
        collected = float(stats.collected) if stats else 0.0
        remaining = expected - collected
        ratio = (collected / expected * 100) if expected > 0 else 0.0

        cat_breakdown.append(
            CapitalCategoryItem(
                name=cat.name,
                amount=cat.amount,
                sub_count=sub_count,
                expected=expected,
                collected=collected,
                remaining=remaining,
                ratio=round(ratio, 2)
            )
        )

    return CapitalStatsOut(
        total_expected=total_expected,
        total_collected=total_collected,
        total_winner_payouts=total_winner_payouts,
        total_expenses=total_expenses,
        total_arrears=total_arrears,
        net_cash=net_cash,
        categories_breakdown=cat_breakdown
    )

@router.get("/standing", response_model=List[SubscriberStandingItem])
def get_subscribers_standing(
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """جلب الموقف المالي للمشتركين مجمعاً ومحسوباً على الخادم"""
    now_val = datetime.datetime.now()
    query = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted")

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

    subs = query.order_by(db_mod.Subscriber.id.desc()).offset(skip).limit(limit).all()
    if not subs:
        return []

    fin_status_map = db_mod.calculate_financial_status_batch(subs, db)
    sub_ids = [s.id for s in subs]

    # جلب إحصائيات الدفع في استعلام تجميعي واحد
    payment_stats = dict(
        (r[0], {
            "paid_count": int(r[1] or 0),
            "total_paid": float(r[2] or 0.0),
            "unpaid_count": int(r[3] or 0),
            "total_unpaid": float(r[4] or 0.0),
            "arrears_count": int(r[5] or 0),
            "total_arrears": float(r[6] or 0.0),
        }) for r in db.query(
            db_mod.Payment.subscriber_id,
            func.coalesce(func.sum(case((db_mod.Payment.is_paid == True, 1), else_=0)), 0),
            func.coalesce(func.sum(case((db_mod.Payment.is_paid == True, db_mod.Payment.amount), else_=0)), 0),
            func.coalesce(func.sum(case((db_mod.Payment.is_paid == False, 1), else_=0)), 0),
            func.coalesce(func.sum(case((db_mod.Payment.is_paid == False, db_mod.Payment.amount), else_=0)), 0),
            func.coalesce(func.sum(case(((db_mod.Payment.is_paid == False) & (db_mod.Payment.due_date < now_val), 1), else_=0)), 0),
            func.coalesce(func.sum(case(((db_mod.Payment.is_paid == False) & (db_mod.Payment.due_date < now_val), db_mod.Payment.amount), else_=0)), 0)
        ).filter(db_mod.Payment.subscriber_id.in_(sub_ids)).group_by(db_mod.Payment.subscriber_id).all()
    )

    items = []
    for s in subs:
        st = payment_stats.get(s.id, {
            "paid_count": 0, "total_paid": 0.0,
            "unpaid_count": 0, "total_unpaid": 0.0,
            "arrears_count": 0, "total_arrears": 0.0
        })
        items.append(
            SubscriberStandingItem(
                subscriber_id=s.id,
                name=s.name,
                phone=s.phone,
                category=s.category or "-",
                fin_status=fin_status_map.get(s.id, s.status),
                paid_count=st["paid_count"],
                total_paid=st["total_paid"],
                unpaid_count=st["unpaid_count"],
                total_unpaid=st["total_unpaid"],
                arrears_count=st["arrears_count"],
                total_arrears=st["total_arrears"]
            )
        )

    return items
