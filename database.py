from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, create_engine, text, inspect, event, func, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
import sys
import os
import datetime
import threading
import time as _time

try:
    from dotenv import load_dotenv
    if getattr(sys, 'frozen', False):
        _base_dir = os.path.dirname(sys.executable)
    else:
        _base_dir = os.path.abspath(os.path.dirname(__file__))
    _env_file = os.path.join(_base_dir, ".env")
    if os.path.exists(_env_file):
        load_dotenv(_env_file, override=True)
    else:
        load_dotenv(override=True)
except ImportError:
    pass

from sqlalchemy.engine import Engine

# =====================================================================
#  نظام قاعدة بيانات هجين (Hybrid) - أونلاين/أوفلاين
#  - عند توفر الإنترنت: يتصل بـ PostgreSQL على Railway
#  - عند انقطاع الإنترنت: يعمل بـ SQLite المحلي مؤقتاً
#  - عند عودة الإنترنت: يُزامن البيانات المحلية مع السيرفر
# =====================================================================

# الحالة الحالية لوضع قاعدة البيانات
_db_mode_online = False          # هل نعمل الآن أونلاين؟
_sync_lock = threading.Lock()    # قفل لمنع التزامن المتزامن

def get_utc_now() -> datetime.datetime:
    """إرجاع التوقيت العالمي الموحد UTC (بدون منطقة زمنية للتوافق التام مع قواعد البيانات)"""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

def get_local_db_path():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_dir, 'hakbah.db')

def verify_and_repair_sqlite_db(db_path: str):
    """التحقق من سلامة ملف SQLite وإصلاحه تلقائياً في حال وجود تلف (malformed)"""
    if not os.path.exists(db_path):
        return
    import sqlite3
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        res = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        if res and res[0] == "ok":
            return
        print(f"[DB-Repair] ⚠️ Database integrity check failed: {res}")
    except Exception as e:
        print(f"[DB-Repair] ⚠️ Error inspecting database integrity: {e}")

    # في حال فشل الفحص، يتم أخذ نسخة احتياطية من الملف التالف وإنشاء قاعدة سليمة
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        corrupted_backup = f"{db_path}.corrupted_{timestamp}"
        import shutil
        shutil.copy2(db_path, corrupted_backup)
        print(f"[DB-Repair] Corrupted DB backed up to: {corrupted_backup}")

        # محاولة استخراج الجداول السليمة وتفريغها أو إفراغ الملف المعطوب
        os.remove(db_path)
        print("[DB-Repair] Removed corrupted DB file, will rebuild fresh schema...")
    except Exception as e:
        print(f"[DB-Repair] [ERROR] Could not replace corrupted database: {e}")

def get_local_database_url():
    db_path = get_local_db_path()
    verify_and_repair_sqlite_db(db_path)
    return f"sqlite:///{db_path}"

def get_server_database_url():
    url = os.getenv("SERVER_DATABASE_URL") or ""
    if not url:
        env_url = os.getenv("DATABASE_URL", "")
        if "postgres" in env_url:
            url = env_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def check_server_connection(server_url: str, timeout=3) -> bool:
    """فحص سريع للغاية لإمكانية الوصول إلى خادم PostgreSQL عبر socket مباشر"""
    if not server_url:
        return False
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(server_url)
        host = parsed.hostname
        port = parsed.port or 5432
        if not host:
            return False
        import socket
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except Exception as e:
        print(f"[DB-Hybrid] Server reachability check failed: {e}")
        return False

def get_database_url():
    """
    تحديد URL قاعدة البيانات بشكل ذكي:
    - إذا كان في بيئة Railway/Render: استخدم PostgreSQL مباشرة
    - إذا كان على الجهاز المحلي: فحص الاتصال أولاً
      - متصل بالسيرفر Railway -> PostgreSQL
      - غير متصل -> SQLite المحلي
    """
    global _db_mode_online

    # البيئات السحابية: استخدم PostgreSQL دائماً بدون فحص
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER"):
        url = get_server_database_url()
        if url:
            _db_mode_online = True
            print("[DB-Hybrid] Mode: CLOUD (Railway/Render) -> PostgreSQL")
            return url

    server_url = get_server_database_url()

    # إذا لا يوجد سيرفر مُعرَّف أصلاً، استخدم المحلي مباشرة
    if not server_url:
        _db_mode_online = False
        print("[DB-Hybrid] Mode: LOCAL (no server URL configured) -> SQLite")
        return get_local_database_url()

    # فحص الاتصال الفعلي بالسيرفر بسرعة فائقة
    print("[DB-Hybrid] Checking Railway server reachability...")
    if check_server_connection(server_url, timeout=3):
        _db_mode_online = True
        print("[DB-Hybrid] Mode: ONLINE -> PostgreSQL (Railway)")
        return server_url
    else:
        print("[DB-Hybrid] Server unreachable. Falling back to local SQLite.")

    _db_mode_online = False
    print("[DB-Hybrid] Mode: OFFLINE -> SQLite (local)")
    return get_local_database_url()

def is_online_mode() -> bool:
    """إرجاع الوضع الحالي: True = أونلاين (PostgreSQL), False = أوفلاين (SQLite)"""
    return _db_mode_online

DATABASE_URL = get_database_url()
print(f"[Database] Initialized with: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

def create_configured_engine(url):
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 30.0}
        return create_engine(url, connect_args=connect_args)
    else:
        # إعدادات التوصيل للشبكات والـ Remote PostgreSQL
        return create_engine(
            url,
            connect_args={"connect_timeout": 10},
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_timeout=15
        )

engine = create_configured_engine(DATABASE_URL)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """تحسين أداء SQLite وتفعيل القراءة والكتابة المتزامنة عند استخدام محرك SQLite فقط"""
    try:
        # التأكد من أن الاتصال هو فعلاً SQLite وليس PostgreSQL
        if type(dbapi_connection).__module__.startswith("sqlite3"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
    except Exception:
        pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def reconnect_engine(new_url=None):
    """إعادة تهيئة اتصال قاعدة البيانات في حال تغيير الإعدادات"""
    global DATABASE_URL, engine, SessionLocal, _db_mode_online
    if new_url:
        DATABASE_URL = new_url
        _db_mode_online = not new_url.startswith("sqlite")
    else:
        DATABASE_URL = get_database_url()

    if engine:
        try:
            engine.dispose()
        except Exception:
            pass
    engine = create_configured_engine(DATABASE_URL)
    SessionLocal.configure(bind=engine)
    return engine

# =====================================================================
#  مزامنة البيانات: SQLite → PostgreSQL عند عودة الإنترنت
# =====================================================================

# الجداول التي يتم مزامنتها (مرتبة حسب الاعتمادية)
SYNC_TABLES_ORDER = [
    "seasons", "categories", "subscriber_numbers",
    "subscribers", "staff", "payments", "winners",
    "expenses", "settings", "admin_notifications",
    "subscriber_messages", "visit_logs"
]

def sync_local_to_server():
    """
    مزامنة بيانات SQLite المحلي إلى PostgreSQL على Railway.
    يُستدعى تلقائياً عند الانتقال من أوفلاين إلى أونلاين.
    يستخدم INSERT ... ON CONFLICT DO UPDATE (upsert) لتجنب التكرار.
    """
    with _sync_lock:
        server_url = get_server_database_url()
        local_url = get_local_database_url()

        if not server_url:
            print("[Sync] No server URL. Skipping sync.")
            return False

        print("[Sync] Starting local → server sync...")
        try:
            local_engine = create_configured_engine(local_url)
            server_engine = create_configured_engine(server_url)

            # فحص أن السيرفر متاح
            with server_engine.connect() as _conn:
                _conn.execute(text("SELECT 1"))

            LocalSession = sessionmaker(bind=local_engine)
            ServerSession = sessionmaker(bind=server_engine)

            local_db = LocalSession()
            server_db = ServerSession()

            try:
                synced_tables = 0
                for table_name in SYNC_TABLES_ORDER:
                    try:
                        rows = local_db.execute(text(f"SELECT * FROM {table_name}")).fetchall()
                        if not rows:
                            continue

                        keys = local_db.execute(
                            text(f"PRAGMA table_info({table_name})")
                        ).fetchall() if local_url.startswith("sqlite") else []

                        col_names = [r[1] for r in keys] if keys else list(rows[0]._mapping.keys())

                        for row in rows:
                            row_dict = dict(zip(col_names, row))
                            # upsert: أدخل أو حدّث إذا كان id موجوداً
                            cols = ", ".join(col_names)
                            placeholders = ", ".join([f":{c}" for c in col_names])
                            update_set = ", ".join([
                                f"{c} = EXCLUDED.{c}"
                                for c in col_names if c != "id"
                            ])
                            upsert_sql = text(f"""
                                INSERT INTO {table_name} ({cols})
                                VALUES ({placeholders})
                                ON CONFLICT (id) DO UPDATE SET {update_set}
                            """)
                            server_db.execute(upsert_sql, row_dict)

                        server_db.commit()
                        synced_tables += 1
                        print(f"[Sync] [OK] {table_name}: {len(rows)} records synced")
                    except Exception as e:
                        server_db.rollback()
                        print(f"[Sync] [WARN] Error syncing {table_name}: {e}")

                print(f"[Sync] Sync complete: {synced_tables}/{len(SYNC_TABLES_ORDER)} tables")
                return synced_tables > 0

            finally:
                local_db.close()
                server_db.close()
                local_engine.dispose()
                server_engine.dispose()

        except Exception as e:
            print(f"[Sync] [ERROR] Sync failed: {e}")
            return False


def try_switch_to_online():
    """
    محاولة التبديل إلى الوضع الأونلاين إذا عاد الاتصال بالسيرفر.
    يُستدعى دورياً من الـ background thread.
    يُرجع True إذا تم التبديل بنجاح.
    """
    global _db_mode_online
    if _db_mode_online:
        return False  # نحن أصلاً أونلاين

    server_url = get_server_database_url()
    if not server_url:
        return False

    if not check_server_connection(server_url, timeout=3):
        return False

    print("[DB-Hybrid] Server reachable! Switching to online mode...")

    # مزامنة البيانات المحلية أولاً قبل التبديل
    sync_local_to_server()

    # التبديل إلى PostgreSQL
    reconnect_engine(server_url)
    _db_mode_online = True
    print("[DB-Hybrid] [OK] Switched to ONLINE mode (PostgreSQL)")
    return True


def start_connectivity_monitor(check_interval=60, on_mode_change=None):
    """
    تشغيل خيط خلفي يراقب الاتصال بالإنترنت كل check_interval ثانية.
    عند استعادة الاتصال يتحول تلقائياً للأونلاين ويُزامن البيانات.
    on_mode_change: دالة اختيارية تُستدعى عند تغيير الوضع (True=أونلاين, False=أوفلاين)
    """
    def _monitor():
        global _db_mode_online
        while True:
            _time.sleep(check_interval)
            try:
                if _db_mode_online:
                    # فحص أن الاتصال لا يزال شغالاً
                    server_url = get_server_database_url()
                    if server_url and not check_server_connection(server_url, timeout=5):
                        print("[DB-Hybrid] [WARN] Lost server connection. Switching to offline mode...")
                        reconnect_engine(get_local_database_url())
                        _db_mode_online = False
                        if on_mode_change:
                            on_mode_change(False)
                else:
                    # محاولة العودة للأونلاين
                    switched = try_switch_to_online()
                    if switched and on_mode_change:
                        on_mode_change(True)
            except Exception as e:
                print(f"[DB-Monitor] Error: {e}")

    t = threading.Thread(target=_monitor, daemon=True, name="DB-ConnectivityMonitor")
    t.start()
    print(f"[DB-Monitor] Started (checking every {check_interval}s)")
    return t

Base = declarative_base()

class Subscriber(Base):
    __tablename__ = "subscribers"
    __table_args__ = (
        Index("idx_subs_cat_status", "category", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String, unique=True, index=True)
    national_id = Column(String, nullable=True)   # رقم الهوية أو البطاقة
    address = Column(String, nullable=True)        # العنوان
    email = Column(String, nullable=True)          # البريد الإلكتروني
    category = Column(String, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=True, index=True)
    selected_number_id = Column(Integer, ForeignKey("subscriber_numbers.id"), nullable=True)
    status = Column(String, default="pending", index=True)  # pending, accepted, rejected, excluded
    subscriber_number = Column(String, index=True, nullable=True)
    password = Column(String, nullable=True)
    exclusion_reason = Column(String, nullable=True)   # سبب الاستبعاد
    excluded_at = Column(DateTime, nullable=True)       # تاريخ الاستبعاد
    visit_count = Column(Integer, default=0)           # عدد زيارات المشترك للوحة التحكم
    last_seen = Column(DateTime, nullable=True)        # وقت آخر ظهور / نشاط للمشترك
    created_at = Column(DateTime, server_default=func.now())

    season = relationship("Season", foreign_keys=[season_id], uselist=False)
    selected_number = relationship(
        "SubscriberNumber",
        foreign_keys=[selected_number_id],
        uselist=False,
    )

class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("idx_payments_sub_paid", "subscriber_id", "is_paid"),
        Index("idx_payments_sub_cycle", "subscriber_id", "cycle_number"),
        Index("idx_payments_due_paid", "due_date", "is_paid"),
        Index("idx_payments_sub_cycle_due", "subscriber_id", "cycle_number", "due_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    subscriber_id = Column(Integer, ForeignKey("subscribers.id"), index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True, index=True)
    amount = Column(Float)
    due_date = Column(DateTime, index=True)
    paid_date = Column(DateTime, nullable=True)
    is_paid = Column(Boolean, default=False, index=True)
    installment_number = Column(Integer, nullable=True)
    cycle_number = Column(Integer, nullable=True, index=True)
    note = Column(String, nullable=True)
    is_staff_settled = Column(Boolean, default=False)
    client_reference = Column(String, nullable=True, index=True)

def build_installment_note(is_paid, due_date, paid_date=None, user_note=None, staff_name=None, is_partial=False):
    """
    توليد ملاحظة القسط المحددة تلقائياً حسب الحالة:
    - عند الإنشاء وقبل السداد: "قسط غير مسدد" (أو "متبقي من سداد جزئي" إن كان جزء متبقي)
    - عند السداد في نفس تاريخ الاستحقاق (أو قبله): "شكراً، تم سداد القسط"
    - عند السداد بعد تاريخ الاستحقاق: "تم سداد القسط متأخراً، يرجى الالتزام"
    """
    if not is_paid:
        base_msg = "متبقي من سداد جزئي" if is_partial else "قسط غير مسدد"
    else:
        d_due = due_date.date() if isinstance(due_date, datetime.datetime) else (due_date if isinstance(due_date, datetime.date) else None)
        d_paid = paid_date.date() if isinstance(paid_date, datetime.datetime) else (paid_date if isinstance(paid_date, datetime.date) else None)

        if d_due and d_paid and d_paid > d_due:
            base_msg = "تم سداد القسط متأخراً، يرجى الالتزام"
        else:
            base_msg = "شكراً، تم سداد القسط"

        if is_partial:
            base_msg = f"سداد جزئي - {base_msg}"

    extra = []
    if user_note and str(user_note).strip():
        u = str(user_note).strip()
        if u not in ("قسط غير مسدد", "شكراً، تم سداد القسط", "تم سداد القسط متأخراً، يرجى الالتزام", "متبقي من سداد جزئي"):
            extra.append(u)

    if staff_name and str(staff_name).strip():
        extra.append(f"الموظف: {staff_name}")

    if extra:
        return f"{base_msg} ({' | '.join(extra)})"
    return base_msg

class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)                     # e.g., "الموسم الأول 2026"
    season_number = Column(Integer, default=1)             # رقم تسلسلي للموسم
    code = Column(String, nullable=True)                  # كود مختصر اختياري
    status = Column(String, default="active", index=True) # active, upcoming, completed, archived
    is_current = Column(Boolean, default=True, index=True)# هل هو الموسم النشط الحالي
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    categories = relationship("Category", back_populates="season", cascade="all, delete-orphan")

class Winner(Base):
    __tablename__ = "winners"

    id = Column(Integer, primary_key=True, index=True)
    subscriber_number = Column(String)
    draw_type = Column(String, nullable=True)
    draw_date = Column(DateTime, server_default=func.now())
    cycle_number = Column(Integer, nullable=True)
    is_received = Column(Boolean, default=False)
    payout_amount = Column(Float, default=0.0)
    received_date = Column(DateTime, nullable=True)
    payout_note = Column(String, nullable=True)
    is_notif_seen = Column(Boolean, default=False)  # هل رأى المشترك هذا الإشعار
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=True, index=True)

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    amount = Column(Float)
    prize_amount = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    max_cycles = Column(Integer, default=10)
    max_installments = Column(Integer, default=12)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=True, index=True)

    season = relationship("Season", back_populates="categories")
    available_numbers = relationship("SubscriberNumber", back_populates="category")

class SubscriberNumber(Base):
    __tablename__ = "subscriber_numbers"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    is_reserved = Column(Boolean, default=False)
    subscriber_id = Column(Integer, ForeignKey("subscribers.id"), nullable=True)
    
    category = relationship("Category", back_populates="available_numbers")
    subscriber = relationship(
        "Subscriber",
        backref="subscriber_numbers",
        foreign_keys=[subscriber_id],
    )

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    amount = Column(Float)
    date = Column(DateTime, server_default=func.now())
    category = Column(String, nullable=True)  # رواتب، سيرفرات، رسائل، أخرى
    subscriber_category = Column(String, nullable=True) # الفئة المالية المستهدفة (نخبة، متوسط...)
    note = Column(String, nullable=True)

class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String, index=True)
    staff_id_code = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String, default="موظف")
    created_at = Column(DateTime, server_default=func.now())

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String)

class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(String)
    type = Column(String, default="info") # e.g., "new_subscriber", "payment_received"
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

class SubscriberMessage(Base):
    __tablename__ = "subscriber_messages"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)                                  # عنوان الرسالة
    content = Column(String)                                # نص ومحتوى الرسالة
    msg_type = Column(String, default="awareness")          # awareness (توعوية), educational (تعليمية), reminder (تذكيرية), urgent (تنبيه هام), general (عامة)
    is_active = Column(Boolean, default=True)               # مفعلة / معطلة
    priority = Column(Integer, default=1)                   # ترتيب الأولوية
    display_duration = Column(Integer, default=7)           # مدة الظهور بالثواني
    start_date = Column(DateTime, nullable=True)           # تاريخ بدء العرض
    end_date = Column(DateTime, nullable=True)             # تاريخ ووقت انتهاء وانقطاع الرسالة
    target_category = Column(String, default="all")         # الفئة المستهدفة ("all" أو فئة محددة)
    created_at = Column(DateTime, server_default=func.now())

class VisitLog(Base):
    __tablename__ = "visit_logs"

    id = Column(Integer, primary_key=True, index=True)
    subscriber_id = Column(Integer, ForeignKey("subscribers.id"), nullable=True, index=True)
    ip_address = Column(String, nullable=True)
    page = Column(String, default="/")
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

@event.listens_for(Session, "before_flush")
def accept_subscriber_on_payment(session, flush_context, instances):
    for obj in session.new.union(session.dirty):
        if isinstance(obj, Payment) and getattr(obj, "is_paid", False):
            sub = session.get(Subscriber, obj.subscriber_id)
            if sub and sub.status != "accepted":
                sub.status = "accepted"

def init_db(force_migration=False):
    db = SessionLocal()
    try:
        # إذا تم التحقق من الجداول مسبقاً، تخطي الفحص البطيء لتسريع فتح البرنامج
        if not force_migration:
            try:
                mig_setting = db.query(Setting).filter(Setting.key == "schema_migrated_v4_visits").first()
                if mig_setting and mig_setting.value == "true":
                    return
            except Exception:
                pass

        # Create all tables defined in the models. This is the most reliable way.
        Base.metadata.create_all(bind=engine)
        db.commit()

        inspector = inspect(engine)
        is_postgres = engine.dialect.name == 'postgresql'
        bool_false = "FALSE" if is_postgres else "0"
        bool_true = "TRUE" if is_postgres else "1"
        datetime_type = "TIMESTAMP" if is_postgres else "DATETIME"

        # التحقق من وجود الأعمدة وإضافتها إذا لزم الأمر (Simple Migrations)

        columns = [c['name'] for c in inspector.get_columns('payments')]
        if 'staff_id' not in columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل معرف الموظف...")
            db.execute(text("ALTER TABLE payments ADD COLUMN staff_id INTEGER REFERENCES staff(id)"))
        if 'is_staff_settled' not in columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل تسوية عهدة الموظف...")
            db.execute(text(f"ALTER TABLE payments ADD COLUMN is_staff_settled BOOLEAN DEFAULT {bool_false}"))
        if 'client_reference' not in columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل مرجع العميل للمدفوعات...")
            db.execute(text("ALTER TABLE payments ADD COLUMN client_reference TEXT"))
        
        cat_columns = [c['name'] for c in inspector.get_columns('categories')]
        if 'amount' not in cat_columns:
            db.execute(text("ALTER TABLE categories ADD COLUMN amount FLOAT DEFAULT 0.0"))
        if 'prize_amount' not in cat_columns:
            db.execute(text("ALTER TABLE categories ADD COLUMN prize_amount FLOAT DEFAULT 0.0"))
        if 'is_active' not in cat_columns:
            db.execute(text(f"ALTER TABLE categories ADD COLUMN is_active BOOLEAN DEFAULT {bool_true}"))
        if 'max_cycles' not in cat_columns:
            db.execute(text("ALTER TABLE categories ADD COLUMN max_cycles INTEGER DEFAULT 10"))
        if 'max_installments' not in cat_columns:
            db.execute(text("ALTER TABLE categories ADD COLUMN max_installments INTEGER DEFAULT 12"))
        if 'start_date' not in cat_columns:
            db.execute(text(f"ALTER TABLE categories ADD COLUMN start_date {datetime_type}"))
        if 'end_date' not in cat_columns:
            db.execute(text(f"ALTER TABLE categories ADD COLUMN end_date {datetime_type}"))
        if 'season_id' not in cat_columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل معرف الموسم في جدول الفئات...")
            db.execute(text("ALTER TABLE categories ADD COLUMN season_id INTEGER REFERENCES seasons(id)"))
        
        # إضافة حقل فئة المشتركين لجدول المصاريف
        exp_columns = [c['name'] for c in inspector.get_columns('expenses')]
        if 'subscriber_category' not in exp_columns:
            db.execute(text("ALTER TABLE expenses ADD COLUMN subscriber_category TEXT"))

        # إضافة الحقول الجديدة لجدول المشتركين (رقم الهوية، العنوان، البريد الإلكتروني، معرف الموسم)
        sub_columns = [c['name'] for c in inspector.get_columns('subscribers')]
        if 'national_id' not in sub_columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل رقم الهوية...")
            db.execute(text("ALTER TABLE subscribers ADD COLUMN national_id TEXT"))
        if 'address' not in sub_columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل العنوان...")
            db.execute(text("ALTER TABLE subscribers ADD COLUMN address TEXT"))
        if 'email' not in sub_columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل البريد الإلكتروني...")
            db.execute(text("ALTER TABLE subscribers ADD COLUMN email TEXT"))
        if 'exclusion_reason' not in sub_columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل سبب الاستبعاد...")
            db.execute(text("ALTER TABLE subscribers ADD COLUMN exclusion_reason TEXT"))
        if 'excluded_at' not in sub_columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل تاريخ الاستبعاد...")
            db.execute(text(f"ALTER TABLE subscribers ADD COLUMN excluded_at {datetime_type}"))
        if 'season_id' not in sub_columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل معرف الموسم في جدول المشتركين...")
            db.execute(text("ALTER TABLE subscribers ADD COLUMN season_id INTEGER REFERENCES seasons(id)"))
        if 'visit_count' not in sub_columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل عدد الزيارات للمشتركين...")
            db.execute(text("ALTER TABLE subscribers ADD COLUMN visit_count INTEGER DEFAULT 0"))
        if 'last_seen' not in sub_columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل آخر ظهور للمشتركين...")
            db.execute(text(f"ALTER TABLE subscribers ADD COLUMN last_seen {datetime_type}"))

        # Ensure `role` exists on staff table regardless of payments changes
        try:
            staff_columns = [c['name'] for c in inspector.get_columns('staff')]
            if 'role' not in staff_columns:
                print("جاري تحديث قاعدة البيانات لإضافة حقل صلاحية الموظف...")
                # Use TEXT type for SQLite compatibility
                db.execute(text("ALTER TABLE staff ADD COLUMN role TEXT DEFAULT 'موظف'"))
        except Exception:
            # If staff table doesn't exist yet or inspection fails, skip (create_all will handle)
            pass

        # إضافة حقل رقم الدورة وحقول تسليم المستحقات لجدول الفائزين
        try:
            winner_columns = [c['name'] for c in inspector.get_columns('winners')]
            if 'cycle_number' not in winner_columns:
                print("جاري تحديث قاعدة البيانات لإضافة حقل رقم الدورة للفائزين...")
                db.execute(text("ALTER TABLE winners ADD COLUMN cycle_number INTEGER"))
            if 'is_received' not in winner_columns:
                print("جاري تحديث قاعدة البيانات لإضافة حقل حالة استلام مستحقات الفائزين...")
                db.execute(text(f"ALTER TABLE winners ADD COLUMN is_received BOOLEAN DEFAULT {bool_false}"))
            if 'payout_amount' not in winner_columns:
                print("جاري تحديث قاعدة البيانات لإضافة حقل المبلغ المستحق للفائزين...")
                db.execute(text("ALTER TABLE winners ADD COLUMN payout_amount FLOAT DEFAULT 0.0"))
            if 'received_date' not in winner_columns:
                print("جاري تحديث قاعدة البيانات لإضافة حقل تاريخ استلام الفائز...")
                db.execute(text(f"ALTER TABLE winners ADD COLUMN received_date {datetime_type}"))
            if 'payout_note' not in winner_columns:
                print("جاري تحديث قاعدة البيانات لإضافة حقل ملاحظات تسليم الفائز...")
                db.execute(text("ALTER TABLE winners ADD COLUMN payout_note TEXT"))
            if 'is_notif_seen' not in winner_columns:
                print("جاري تحديث قاعدة البيانات لإضافة حقل حالة مشاهدة الإشعار...")
                db.execute(text(f"ALTER TABLE winners ADD COLUMN is_notif_seen BOOLEAN DEFAULT {bool_false}"))
            if 'season_id' not in winner_columns:
                print("جاري تحديث قاعدة البيانات لإضافة حقل معرف الموسم لجدول الفائزين...")
                db.execute(text("ALTER TABLE winners ADD COLUMN season_id INTEGER REFERENCES seasons(id)"))
        except Exception as e:
            print(f"Error migrating winners table: {e}")

        # فحص وترحيل البيانات إلى الموسم الأول الافتراضي
        try:
            season_count = db.query(Season).count()
            if season_count == 0:
                print("جاري إنشاء الموسم الأول الافتراضي وترحيل البيانات السابقة...")
                first_season = Season(
                    name="الموسم الأول",
                    season_number=1,
                    code="S1",
                    status="active",
                    is_current=True,
                    description="الموسم التأسيسي الأول للهكبة"
                )
                db.add(first_season)
                db.commit()
                db.refresh(first_season)

                # تحديث الفئات السابقة
                db.execute(text(f"UPDATE categories SET season_id = {first_season.id} WHERE season_id IS NULL"))
                # تحديث المشتركين السابقين
                db.execute(text(f"UPDATE subscribers SET season_id = {first_season.id} WHERE season_id IS NULL"))
                # تحديث الفائزين السابقين
                db.execute(text(f"UPDATE winners SET season_id = {first_season.id} WHERE season_id IS NULL"))
                db.commit()
                print(f"تم ربط جميع البيانات السابقة بـ '{first_season.name}' بنجاح.")
            else:
                # التأكد من وجود موسم حالي نشط
                curr = db.query(Season).filter(Season.is_current == True).first()
                if not curr:
                    latest = db.query(Season).order_by(Season.id.desc()).first()
                    if latest:
                        latest.is_current = True
                        db.commit()
                # ربط أي فئات أو مشتركين ليس لديهم موسم بالموسم الحالي
                curr = db.query(Season).filter(Season.is_current == True).first()
                if curr:
                    db.execute(text(f"UPDATE categories SET season_id = {curr.id} WHERE season_id IS NULL"))
                    db.execute(text(f"UPDATE subscribers SET season_id = {curr.id} WHERE season_id IS NULL"))
                    db.commit()
        except Exception as e:
            print(f"Error migrating seasons data: {e}")
            db.rollback()

        # إنشاء الفهارس الهامة لتحسين سرعة الاستعلامات ومنع الفحص الكامل (Full Table Scan)
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_payments_sub_id ON payments (subscriber_id)",
            "CREATE INDEX IF NOT EXISTS idx_payments_sub_paid ON payments (subscriber_id, is_paid)",
            "CREATE INDEX IF NOT EXISTS idx_payments_sub_cycle ON payments (subscriber_id, cycle_number)",
            "CREATE INDEX IF NOT EXISTS idx_payments_due_paid ON payments (due_date, is_paid)",
            "CREATE INDEX IF NOT EXISTS idx_payments_due_date ON payments (due_date)",
            "CREATE INDEX IF NOT EXISTS idx_payments_is_paid ON payments (is_paid)",
            "CREATE INDEX IF NOT EXISTS idx_subscribers_category ON subscribers (category)",
            "CREATE INDEX IF NOT EXISTS idx_subscribers_status ON subscribers (status)",
            "CREATE INDEX IF NOT EXISTS idx_subscribers_cat_status ON subscribers (category, status)",
            "CREATE INDEX IF NOT EXISTS idx_sub_numbers_cat_res ON subscriber_numbers (category_id, is_reserved)",
            "CREATE INDEX IF NOT EXISTS idx_winners_sub_num ON winners (subscriber_number)",
            "CREATE INDEX IF NOT EXISTS idx_categories_season ON categories (season_id)",
            "CREATE INDEX IF NOT EXISTS idx_subscribers_season ON subscribers (season_id)",
            "CREATE INDEX IF NOT EXISTS idx_subscribers_last_seen ON subscribers (last_seen)",
            "CREATE INDEX IF NOT EXISTS idx_visit_log_sub_id ON visit_logs (subscriber_id)",
            "CREATE INDEX IF NOT EXISTS idx_visit_log_created_at ON visit_logs (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_winners_season ON winners (season_id)"
        ]
        for iq in index_queries:
            try:
                db.execute(text(iq))
            except Exception:
                pass
        db.commit()

        # Add default settings if not exists
        reg_setting = db.query(Setting).filter(Setting.key == "registration_open").first()
        if not reg_setting:
            db.add(Setting(key="registration_open", value="true"))

        # حفظ علامة اكتمال تهيئة الجداول لتسريع الفتح اللاحق
        mig_setting = db.query(Setting).filter(Setting.key == "schema_migrated_v4_visits").first()
        if not mig_setting:
            db.add(Setting(key="schema_migrated_v4_visits", value="true"))
        else:
            mig_setting.value = "true"

        db.commit()
    except Exception as e:
        print(f"An error occurred during DB initialization: {e}")
        db.rollback()
    finally:
        db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_daily_payments(db: Session, sub) -> int:
    """
    توليد الأقساط اليومية المفقودة للمشترك حتى تاريخ اليوم دون أي تكرار نهائياً.
    تعتمد على الفئة وتاريخ بدايتها، وتتحقق بدقة من عدم وجود (cycle_number, installment_number) مسبقاً.
    """
    if not sub or not sub.category or getattr(sub, "status", None) != "accepted":
        return 0

    cat = db.query(Category).filter(Category.name == sub.category).first()
    if not cat or not cat.start_date:
        return 0

    start_date = cat.start_date.date() if hasattr(cat.start_date, 'date') else cat.start_date
    today = datetime.date.today()
    days_passed = (today - start_date).days
    if days_passed < 0:
        return 0

    max_c = int(cat.max_cycles or 1)
    max_i = int(cat.max_installments or 1)
    total_possible = max_c * max_i
    count_to_gen = min(days_passed + 1, total_possible)
    if count_to_gen <= 0:
        return 0

    # جلب جميع أزواج (cycle_number, installment_number) الموجودة مسبقاً لهذا المشترك
    existing_pairs = set(
        db.query(Payment.cycle_number, Payment.installment_number)
        .filter(Payment.subscriber_id == sub.id)
        .all()
    )

    added = 0
    for i in range(count_to_gen):
        c_idx = (i // max_i) + 1
        i_idx = (i % max_i) + 1
        if c_idx > max_c:
            break

        if (c_idx, i_idx) not in existing_pairs:
            due_dt = datetime.datetime.combine(
                start_date + datetime.timedelta(days=i),
                datetime.time.min
            )
            db.add(Payment(
                subscriber_id=sub.id,
                amount=cat.amount,
                due_date=due_dt,
                is_paid=False,
                cycle_number=c_idx,
                installment_number=i_idx,
                note=build_installment_note(is_paid=False, due_date=due_dt)
            ))
            existing_pairs.add((c_idx, i_idx))
            added += 1

    if added > 0:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    return added

_thresholds_cache = {"time": 0.0, "value": (1, 3)}

def invalidate_discipline_cache():
    global _thresholds_cache
    _thresholds_cache["time"] = 0.0

def get_discipline_thresholds(db):
    """جلب حدود التأخر والإيقاف مع تخزين مؤقت لتفادي الاستعلام المتكرر"""
    global _thresholds_cache
    import time
    now = time.time()
    if now - _thresholds_cache["time"] < 60.0:
        return _thresholds_cache["value"]

    try:
        late_setting = db.query(Setting).filter(Setting.key == "discipline_late_threshold").first()
        suspended_setting = db.query(Setting).filter(Setting.key == "discipline_suspended_threshold").first()
        late_th = int(late_setting.value) if (late_setting and late_setting.value and str(late_setting.value).isdigit()) else 1
        susp_th = int(suspended_setting.value) if (suspended_setting and suspended_setting.value and str(suspended_setting.value).isdigit()) else 3
        _thresholds_cache["value"] = (late_th, susp_th)
        _thresholds_cache["time"] = now
    except Exception:
        pass
    return _thresholds_cache["value"]

def calculate_financial_status(subscriber, db, settings_cache=None):
    """
    حساب حالة الانضباط المالي للمشترك ديناميكياً:
    - committed: ملتزم (🟢)
    - pending_payment: بانتظار الدفع (🟡)
    - late: متأخر (🔴)
    - suspended: موقوف (⚫)
    """
    import datetime
    
    # إذا لم يكن مقبولاً بعد، فإن حالته هي حالته الإدارية
    if subscriber.status != "accepted":
        return subscriber.status or "pending"

    # جلب جميع أقساط الدورة الحالية للمشترك
    today = datetime.datetime.now()
    active_p = db.query(Payment).filter(
        Payment.subscriber_id == subscriber.id,
        Payment.due_date <= today
    ).order_by(Payment.due_date.desc()).first()
    
    sub_current_cycle = active_p.cycle_number if active_p else 1

    # جلب الدفعات الخاصة بهذه الدورة
    payments = db.query(Payment).filter(
        Payment.subscriber_id == subscriber.id,
        Payment.cycle_number == sub_current_cycle
    ).order_by(Payment.due_date.asc()).all()

    if not payments:
        return "committed"

    today_date = today.date()
    overdue_count = 0
    due_today_unpaid = False

    for p in payments:
        if not p.is_paid:
            p_date = p.due_date.date()
            if p_date < today_date:
                overdue_count += 1
            elif p_date == today_date:
                due_today_unpaid = True

    late_threshold, suspended_threshold = settings_cache if settings_cache else get_discipline_thresholds(db)

    if overdue_count >= suspended_threshold:
        return "suspended"
    elif overdue_count >= late_threshold:
        return "late"
    elif due_today_unpaid:
        return "pending_payment"
    else:
        return "committed"

def calculate_financial_status_batch(subscribers, db):
    """حساب الحالة المالية لمجموعة من المشتركين دفعة واحدة عبر استعلامين خفيفين جداً دون تحميل آلاف السجلات"""
    if not subscribers:
        return {}
    
    thresholds = get_discipline_thresholds(db)
    late_threshold, suspended_threshold = thresholds
    
    accepted_subs = [s for s in subscribers if s.status == "accepted"]
    results = {s.id: (s.status or "pending") for s in subscribers if s.status != "accepted"}
    
    if not accepted_subs:
        return results
    
    import datetime
    today = datetime.datetime.now()
    today_date = today.date()
    sub_ids = [s.id for s in accepted_subs]
    
    # 1. جلب الدورة الحالية لكل مشترك عبر استعلام تجميعي خفيف وسريع جداً
    try:
        active_cycles = dict(
            db.query(Payment.subscriber_id, func.max(Payment.cycle_number))
            .filter(Payment.subscriber_id.in_(sub_ids), Payment.due_date <= today)
            .group_by(Payment.subscriber_id)
            .all()
        )
    except Exception:
        active_cycles = {}
    
    # 2. جلب الأقساط غير المسددة فقط (تجنب تحميل 14,000 قسط مسدد بدون فائدة)
    try:
        unpaid_payments = db.query(
            Payment.subscriber_id,
            Payment.cycle_number,
            Payment.due_date
        ).filter(
            Payment.subscriber_id.in_(sub_ids),
            Payment.is_paid == False
        ).all()
    except Exception:
        unpaid_payments = []
    
    unpaid_by_sub = {}
    for p in unpaid_payments:
        unpaid_by_sub.setdefault(p[0], []).append(p)
        
    for s in accepted_subs:
        current_cycle = active_cycles.get(s.id, 1)
        s_unpaid = unpaid_by_sub.get(s.id, [])
        # تصفية الأقساط غير المسددة للدورة الحالية فقط
        cycle_unpaid = [p for p in s_unpaid if p[1] == current_cycle]
        
        overdue_count = 0
        due_today_unpaid = False
        for p in cycle_unpaid:
            if p[2]:
                p_date = p[2].date()
                if p_date < today_date:
                    overdue_count += 1
                elif p_date == today_date:
                    due_today_unpaid = True
                    
        if overdue_count >= suspended_threshold:
            results[s.id] = "suspended"
        elif overdue_count >= late_threshold:
            results[s.id] = "late"
        elif due_today_unpaid:
            results[s.id] = "pending_payment"
        else:
            results[s.id] = "committed"
            
    return results

def get_current_season(db):
    """جلب الموسم النشط الحالي"""
    try:
        s = db.query(Season).filter(Season.is_current == True).first()
        if not s:
            s = db.query(Season).filter(Season.status == "active").order_by(Season.id.desc()).first()
        if not s:
            s = db.query(Season).order_by(Season.id.desc()).first()
        if not s:
            s = Season(
                name="الموسم الأول",
                season_number=1,
                code="S1",
                status="active",
                is_current=True,
                start_date=datetime.datetime.now()
            )
            db.add(s)
            db.commit()
            db.refresh(s)
        return s
    except Exception as e:
        print(f"Error in get_current_season: {e}")
        return None

def set_current_season(db, season_id: int):
    """تحديد الموسم النشط الحالي"""
    try:
        db.query(Season).update({Season.is_current: False})
        target = db.get(Season, season_id)
        if target:
            target.is_current = True
            db.commit()
            return target
        db.rollback()
        return None
    except Exception as e:
        print(f"Error in set_current_season: {e}")
        db.rollback()
        return None

def get_all_seasons(db):
    """جلب جميع المواسم مرتبة"""
    try:
        return db.query(Season).order_by(Season.season_number.asc(), Season.id.asc()).all()
    except Exception as e:
        print(f"Error in get_all_seasons: {e}")
        return []
