import os
import secrets
from fastapi import HTTPException, Security, status
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

def verify_admin_api_key(api_key: str = Security(api_key_header)):
    """التحقق من صحة مفتاح الـ API لضمان وصول تطبيق الإدارة المكتبي فقط"""
    expected = get_configured_api_key()
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="غير مصرح بالوصول: مفتاح الـ API غير صالح أو غير موجود."
        )
    return api_key

def get_db():
    """Dependency لتوفير جلسة قاعدة بيانات مع الإغلاق التلقائي الآمن"""
    db = db_mod.SessionLocal()
    try:
        yield db
    finally:
        db.close()
