import os
import secrets
from fastapi import HTTPException, Security, status, Request, Depends
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
import database as db_mod

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_configured_api_key() -> str:
    key = os.getenv("ADMIN_API_KEY", "")
    if not key:
        key = "hakbah_api_sec_994a3bc1e8204d88e07a216f49b"
    return key

def get_db():
    """Dependency لتوفير جلسة قاعدة بيانات مع الإغلاق التلقائي الآمن"""
    db = db_mod.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_admin_api_key(
    request: Request,
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db)
):
    """التحقق من صحة الوصول: إما عبر مفتاح الـ API (تطبيق الإدارة المكتبي) أو عبر جلسة الويب لمدير النظام"""
    # 1. التحقق من مفتاح الـ API (تطبيق الإدارة المكتبي)
    expected = get_configured_api_key()
    if api_key and secrets.compare_digest(api_key, expected):
        return True

    # 2. التحقق من جلسة الويب (Web Session) لحساب برتبة "مدير"
    try:
        staff_id = request.session.get("staff_id")
        if staff_id:
            staff = db.query(db_mod.Staff).filter(db_mod.Staff.id == staff_id).first()
            if staff and staff.role == "مدير":
                return True
    except Exception:
        pass

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="غير مصرح: هذا القسم والإجراءات متاحة فقط لحساب المدير العام."
    )
