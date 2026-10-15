from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import database as db_mod
from api.auth import get_db, verify_admin_api_key
from api.schemas import DashboardStatsOut, NotificationOut, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/stats", tags=["Stats"], dependencies=[Depends(verify_admin_api_key)])

class NotificationsSummaryOut(BaseModel):
    unread_count: int
    notifications: List[NotificationOut]

@router.get("/dashboard", response_model=DashboardStatsOut)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """إحصائيات الواجهة الرئيسية الشاملة وسريعة الاستجابة"""
    # 1. إجمالي المشتركين
    total_subs = db.query(func.count(db_mod.Subscriber.id)).scalar() or 0

    # 2. أعداد المشتركين حسب الفئة
    cat_rows = db.query(
        db_mod.Subscriber.category,
        func.count(db_mod.Subscriber.id)
    ).group_by(db_mod.Subscriber.category).all()
    cat_counts = {r[0] or "غير محدد": r[1] for r in cat_rows}

    # 3. حالة التسجيل
    reg_setting = db.query(db_mod.Setting).filter(db_mod.Setting.key == "registration_open").first()
    reg_open = (reg_setting.value == "true") if reg_setting else False

    return DashboardStatsOut(
        total_subscribers=total_subs,
        category_counts=cat_counts,
        registration_open=reg_open
    )

@router.get("/notifications", response_model=NotificationsSummaryOut)
def get_admin_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """جلب إشعارات المشرفين والمدراء مع عداد غير المقروءة"""
    unread_count = db.query(func.count(db_mod.AdminNotification.id)).filter(
        db_mod.AdminNotification.is_read == False
    ).scalar() or 0

    query = db.query(db_mod.AdminNotification)
    if unread_only:
        query = query.filter(db_mod.AdminNotification.is_read == False)

    notifications = query.order_by(db_mod.AdminNotification.created_at.desc()).limit(limit).all()

    return NotificationsSummaryOut(
        unread_count=unread_count,
        notifications=[NotificationOut.model_validate(n) for n in notifications]
    )

@router.post("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int, db: Session = Depends(get_db)):
    """تحديد إشعار كمقروء"""
    notif = db.get(db_mod.AdminNotification, notif_id)
    if not notif:
        raise HTTPException(status_code=404, detail="الإشعار غير موجود")
    notif.is_read = True
    db.commit()
    return {"success": True, "id": notif_id}

@router.post("/notifications/read-all")
def mark_all_notifications_read(db: Session = Depends(get_db)):
    """تحديد جميع الإشعارات كمقروءة دفعة واحدة"""
    db.query(db_mod.AdminNotification).filter(
        db_mod.AdminNotification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"success": True}

@router.get("/categories", response_model=List[CategoryOut])
def get_categories(db: Session = Depends(get_db)):
    """جلب جميع الفئات المالية وإعداداتها"""
    categories = db.query(db_mod.Category).order_by(db_mod.Category.amount.asc()).all()
    return [CategoryOut.model_validate(c) for c in categories]

@router.put("/categories/{cat_id}", response_model=CategoryOut)
def update_category(cat_id: int, req: CategoryUpdate, db: Session = Depends(get_db)):
    """تحديث إعدادات فئة معينة"""
    cat = db.get(db_mod.Category, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="الفئة غير موجودة")

    for field, val in req.model_dump(exclude_unset=True).items():
        setattr(cat, field, val)

    db.commit()
    db.refresh(cat)
    return CategoryOut.model_validate(cat)
