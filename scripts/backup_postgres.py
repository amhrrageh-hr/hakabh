#!/usr/bin/env python3
"""
سكريبت النسخ الاحتياطي ومزامنة قاعدة بيانات PostgreSQL السحابية
إلى ملف محلي (SQLite) لاستخدامها في تطبيق سطح المكتب بدون إنترنت
"""

import os
import sys
import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ضبط المسار
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, base_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(base_dir, ".env"), override=True)

import database as db_mod
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker

def backup_postgres_to_local(custom_dest_file=None):
    print("=" * 65)
    print("بدء النسخ الاحتياطي من PostgreSQL السحابية إلى قاعدة البيانات المحلية...")
    print("=" * 65)

    pg_url = db_mod.get_server_database_url()
    if not pg_url:
        print("[-] لم يتم العثور على رابط SERVER_DATABASE_URL في ملف .env")
        return False, "لم يتم العثور على إعدادات قاعدة بيانات السيرفر في ملف .env"

    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    backup_dir = os.path.join(base_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = custom_dest_file if custom_dest_file else os.path.join(backup_dir, f"hakbah_backup_{timestamp}.db")
    local_main_db = os.path.join(base_dir, "hakbah.db")

    masked_url = pg_url.split('@')[-1] if '@' in pg_url else pg_url
    print(f"الاتصال بقاعدة بيانات السيرفر (PostgreSQL): {masked_url}")
    try:
        pg_engine = create_engine(pg_url, pool_pre_ping=True)
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[+] تم الاتصال بنجاح بقاعدة البيانات السحابية.")
    except Exception as e:
        err_msg = f"فشل الاتصال بقاعدة بيانات PostgreSQL: {e}"
        print(f"[-] {err_msg}")
        return False, err_msg

    # إذا كان الملف موجوداً مسبقاً نحذفه لإنشاء نسخة نظيفة
    if os.path.exists(backup_file):
        try:
            os.remove(backup_file)
        except Exception:
            pass

    # إنشاء قاعدة بيانات SQLite الاحتياطية
    sqlite_url = f"sqlite:///{backup_file}"
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

    # تعطيل قيود المفاتيح الأجنبية أثناء عملية النسخ لتجنب مشاكل التبعيات الدائرية
    @event.listens_for(sqlite_engine, "connect")
    def disable_fk(dbapi_conn, record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    print("[*] تجهيز الجداول في النسخة الاحتياطية...")
    db_mod.Base.metadata.create_all(bind=sqlite_engine)

    PgSession = sessionmaker(bind=pg_engine)
    SqliteSession = sessionmaker(bind=sqlite_engine)

    pg_db = PgSession()
    sqlite_db = SqliteSession()

    # ترتيب الجداول بالاعتماديات الصحيحة
    models = [
        ("إعدادات النظام (Setting)", db_mod.Setting),
        ("المواسم (Season)", db_mod.Season),
        ("الموظفين (Staff)", db_mod.Staff),
        ("المصاريف (Expense)", db_mod.Expense),
        ("الرسائل التوعوية (SubscriberMessage)", db_mod.SubscriberMessage),
        ("تنبيهات الإدارة (AdminNotification)", db_mod.AdminNotification),
        ("الفئات (Category)", db_mod.Category),
        ("المشتركين (Subscriber)", db_mod.Subscriber),
        ("أرقام المشتركين (SubscriberNumber)", db_mod.SubscriberNumber),
        ("المدفوعات (Payment)", db_mod.Payment),
        ("الفائزين بالسحب (Winner)", db_mod.Winner),
    ]

    total_records = 0
    try:
        for label, model_cls in models:
            records = pg_db.query(model_cls).all()
            count = len(records)
            print(f"[*] جاري نسخ {label}: {count} سجل...")
            for r in records:
                data = {col.name: getattr(r, col.name) for col in model_cls.__table__.columns}
                new_item = model_cls(**data)
                sqlite_db.merge(new_item)
            sqlite_db.commit()
            total_records += count

        pg_db.close()
        sqlite_db.close()
        sqlite_engine.dispose()
        pg_engine.dispose()

        # إذا لم يتم تحديد ملف مخصص، نحدث أيضاً hakbah.db الرئيسي
        if not custom_dest_file:
            import shutil
            shutil.copy2(backup_file, local_main_db)

        print("\n" + "=" * 65)
        print("[+] اكتمل النسخ الاحتياطي بنجاح تام!")
        print(f"[+] مسار ملف النسخة الاحتياطية: {backup_file}")
        if not custom_dest_file:
            print(f"[+] تم تحديث قاعدة بيانات سطح المكتب المباشرة: {local_main_db}")
        print(f"[+] إجمالي السجلات التي تم حفظها: {total_records}")
        print("=" * 65)
        print("ملاحظة: إذا توقف السيرفر أو الاستضافة، كل ما عليك هو تغيير DB_MODE=local في ملف .env")
        print("وسيعمل تطبيق سطح المكتب فورا بجميع البيانات التي تم نسخها!")
        return True, backup_file

    except Exception as e:
        err_msg = f"حدث خطأ أثناء النسخ: {e}"
        print(f"[-] {err_msg}")
        sqlite_db.rollback()
        return False, err_msg
    finally:
        try:
            pg_db.close()
            sqlite_db.close()
        except Exception:
            pass

if __name__ == "__main__":
    backup_postgres_to_local()
