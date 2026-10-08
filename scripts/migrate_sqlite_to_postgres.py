#!/usr/bin/env python3
"""
سكريبت ترحيل ومزامنة البيانات من قاعدة بيانات SQLite المحلية (hakbah.db)
إلى قاعدة البيانات المركزية PostgreSQL على السيرفر الخارجي.

الاستخدام:
python scripts/migrate_sqlite_to_postgres.py [POSTGRES_URL]

أو ضبط متغير البيئة DATABASE_URL قبل تشغيل السكريبت.
"""

import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# إضافة المجلد الرئيسي للمسارات
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
import database as db_mod

def migrate():
    print("=" * 65)
    print("🚀 بدء سكريبت نقل البيانات من SQLite إلى PostgreSQL المركزية")
    print("=" * 65)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sqlite_db_path = os.path.join(base_dir, "hakbah.db")

    if not os.path.exists(sqlite_db_path):
        print(f"❌ لم يتم العثور على ملف قاعدة البيانات SQLite المحلية في: {sqlite_db_path}")
        sys.exit(1)

    sqlite_url = f"sqlite:///{sqlite_db_path}"

    # قراءة رابط PostgreSQL من المعاملات أو البيئة
    if len(sys.argv) > 1:
        pg_url = sys.argv[1]
    else:
        pg_url = db_mod.get_server_database_url()

    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    if not (pg_url.startswith("postgresql://")):
        print(f"❌ رابط PostgreSQL غير صحيح: {pg_url}")
        sys.exit(1)

    print(f"\n📂 قاعدة البيانات المصدر (SQLite): {sqlite_url}")
    print(f"🌐 قاعدة البيانات الهدف (PostgreSQL): {pg_url.split('@')[-1] if '@' in pg_url else pg_url}\n")

    try:
        # إنشاء المحركات
        sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        pg_engine = create_engine(pg_url, pool_pre_ping=True)

        # اختبار الاتصال بالهدف
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ تم التأكد من الاتصال بـ PostgreSQL بنجاح.")

        # إنهاء أي اتصالات قديمة معلقة على قاعدة البيانات
        try:
            with pg_engine.connect() as conn:
                conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'hakbah_db' AND pid <> pg_backend_pid();"))
                conn.commit()
        except Exception:
            pass

        # إعادة إنشاء الجداول في PostgreSQL بنظافة وسرعة
        print("🔨 جاري إعادة تهيئة وإنشاء الجداول في PostgreSQL...")
        with pg_engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS payments, winners, expenses, admin_notifications, settings, subscribers, subscriber_numbers, staff, categories CASCADE;"))
            conn.commit()
        db_mod.Base.metadata.create_all(bind=pg_engine)
        print("✅ تم تجهيز الجداول بنجاح.")

        # إنشاء جلسات العمل
        SqliteSession = sessionmaker(bind=sqlite_engine)
        PgSession = sessionmaker(bind=pg_engine)

        src_db = SqliteSession()
        target_db = PgSession()

        # قائمة النماذج المراد نقل بياناتها
        models = [
            ("الفئات (categories)", db_mod.Category),
            ("الموظفين (staff)", db_mod.Staff),
            ("أرقام المشتركين (subscriber_numbers)", db_mod.SubscriberNumber),
            ("المشتركين (subscribers)", db_mod.Subscriber),
            ("المدفوعات (payments)", db_mod.Payment),
            ("الفائزين بالسحب (winners)", db_mod.Winner),
            ("المصاريف (expenses)", db_mod.Expense),
            ("إعدادات النظام (settings)", db_mod.Setting),
            ("تنبيهات الإدارة (admin_notifications)", db_mod.AdminNotification),
        ]

        pending_num_sub_links = {}

        for label, model_cls in models:
            records = src_db.query(model_cls).all()
            if not records:
                print(f"ℹ️ {label}: لا يوجد سجلات لنقلها.")
                continue

            count = 0
            for record in records:
                data = {col.name: getattr(record, col.name) for col in inspect(model_cls).columns}
                
                # حل التعارض الدائري بين أرقام المشتركين والمشتركين
                if model_cls == db_mod.SubscriberNumber and data.get("subscriber_id"):
                    pk_val = data[inspect(model_cls).primary_key[0].name]
                    pending_num_sub_links[pk_val] = data["subscriber_id"]
                    data["subscriber_id"] = None

                new_obj = model_cls(**data)
                target_db.add(new_obj)
                count += 1

            target_db.commit()
            print(f"✨ {label}: تم نقل {count} سجل من أصل {len(records)} بنجاح.")

            # إعادة ربط الأرقام بالمشتركين بعد إضافة جدول المشتركين بنجاح
            if model_cls == db_mod.Subscriber and pending_num_sub_links:
                for num_id, sub_id in pending_num_sub_links.items():
                    target_db.query(db_mod.SubscriberNumber).filter(
                        db_mod.SubscriberNumber.id == num_id
                    ).update({"subscriber_id": sub_id})
                target_db.commit()
                print("🔗 تم ربط أرقام المشتركين بالمشتركين بنجاح.")

        # إعادة تفعيل قيود المفاتيح الخارجية
        try:
            with pg_engine.connect() as conn:
                conn.execute(text("SET session_replication_role = 'origin';"))
                conn.commit()
        except Exception:
            pass

        # إعادة تضبيط عدادات التسلسل المتتالي (Sequences) في PostgreSQL
        print("\n🔄 جاري ضبط العدادات المتتالية (Auto-increment Sequences)...")
        auto_seq_tables = [
            "categories", "subscribers", "subscriber_numbers", "staff", 
            "payments", "winners", "expenses", "admin_notifications"
        ]
        with pg_engine.connect() as conn:
            for tbl in auto_seq_tables:
                try:
                    query = f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), COALESCE((SELECT MAX(id) FROM {tbl}), 1));"
                    conn.execute(text(query))
                    conn.commit()
                except Exception as seq_err:
                    print(f"⚠️ يتعذر إيقاف العداد لجدول {tbl}: {seq_err}")

        print("\n" + "=" * 65)
        print("🎉 تم ترحيل واستيراد كافة البيانات إلى PostgreSQL المركزية بنجاح تام!")
        print("=" * 65)

    except Exception as e:
        print(f"\n❌ حدث خطأ غير متوقع أثناء عملية الترحيل: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    migrate()
