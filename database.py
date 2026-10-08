from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, create_engine, text, inspect, event, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
import sys
import os
import datetime

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

def get_local_database_url():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.abspath(os.path.dirname(__file__))
    return f"sqlite:///{os.path.join(base_dir, 'hakbah.db')}"

def get_server_database_url():
    url = os.getenv("SERVER_DATABASE_URL") or ""
    if not url:
        env_url = os.getenv("DATABASE_URL", "")
        if "postgres" in env_url:
            url = env_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def get_database_url():
    # الوضع الافتراضي لتشغيل التطبيق هو قاعدة البيانات المحلية دائماً
    # يتم التحويل للسيرفر عند تحديد DB_MODE=server صراحة
    db_mode = os.getenv("DB_MODE", "local").lower().strip()
    if db_mode == "server":
        url = get_server_database_url()
        if url:
            return url
    
    return get_local_database_url()

DATABASE_URL = get_database_url()
print(f"[Database] Initialized with: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

def create_configured_engine(url):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if url.startswith("sqlite"):
        return create_engine(url, connect_args=connect_args)
    else:
        # إعدادات التوصيل للشبكات والـ Remote PostgreSQL
        return create_engine(url, connect_args=connect_args, pool_pre_ping=True, pool_recycle=300)

engine = create_configured_engine(DATABASE_URL)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """تحسين أداء SQLite وتفعيل القراءة والكتابة المتزامنة عند استخدام محرك SQLite"""
    try:
        if hasattr(dbapi_connection, "cursor"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
    except Exception:
        pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def reconnect_engine(new_url=None):
    """إعادة تهيئة اتصال قاعدة البيانات في حال تغيير الإعدادات"""
    global DATABASE_URL, engine, SessionLocal
    if new_url:
        DATABASE_URL = new_url
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

Base = declarative_base()

class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String, unique=True, index=True)
    national_id = Column(String, nullable=True)   # رقم الهوية أو البطاقة
    address = Column(String, nullable=True)        # العنوان
    email = Column(String, nullable=True)          # البريد الإلكتروني
    category = Column(String)
    selected_number_id = Column(Integer, ForeignKey("subscriber_numbers.id"), nullable=True)
    status = Column(String, default="pending")  # pending, accepted, rejected, excluded
    subscriber_number = Column(String, index=True, nullable=True)
    password = Column(String, nullable=True)
    exclusion_reason = Column(String, nullable=True)   # سبب الاستبعاد
    excluded_at = Column(DateTime, nullable=True)       # تاريخ الاستبعاد
    created_at = Column(DateTime, server_default=func.now())

    selected_number = relationship(
        "SubscriberNumber",
        foreign_keys=[selected_number_id],
        uselist=False,
    )

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    subscriber_id = Column(Integer, ForeignKey("subscribers.id"))
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    amount = Column(Float)
    due_date = Column(DateTime)
    paid_date = Column(DateTime, nullable=True)
    is_paid = Column(Boolean, default=False)
    installment_number = Column(Integer, nullable=True)
    cycle_number = Column(Integer, nullable=True)
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
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

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

@event.listens_for(Session, "before_flush")
def accept_subscriber_on_payment(session, flush_context, instances):
    for obj in session.new.union(session.dirty):
        if isinstance(obj, Payment) and getattr(obj, "is_paid", False):
            sub = session.get(Subscriber, obj.subscriber_id)
            if sub and sub.status != "accepted":
                sub.status = "accepted"

def init_db():
    db = SessionLocal()
    try:
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
        
        # إضافة حقل فئة المشتركين لجدول المصاريف
        exp_columns = [c['name'] for c in inspector.get_columns('expenses')]
        if 'subscriber_category' not in exp_columns:
            db.execute(text("ALTER TABLE expenses ADD COLUMN subscriber_category TEXT"))

        # إضافة الحقول الجديدة لجدول المشتركين (رقم الهوية، العنوان، البريد الإلكتروني)
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
        except Exception as e:
            print(f"Error migrating winners table: {e}")

        db.commit()

        # Add default settings if not exists
        reg_setting = db.query(Setting).filter(Setting.key == "registration_open").first()
        if not reg_setting:
            db.add(Setting(key="registration_open", value="true"))

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

def calculate_financial_status(subscriber, db):
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

    # جلب الحدود المخصصة للتأخر والإيقاف من جدول الإعدادات
    late_setting = db.query(Setting).filter(Setting.key == "discipline_late_threshold").first()
    suspended_setting = db.query(Setting).filter(Setting.key == "discipline_suspended_threshold").first()
    
    late_threshold = int(late_setting.value) if (late_setting and late_setting.value.isdigit()) else 1
    suspended_threshold = int(suspended_setting.value) if (suspended_setting and suspended_setting.value.isdigit()) else 3

    if overdue_count >= suspended_threshold:
        return "suspended"
    elif overdue_count >= late_threshold:
        return "late"
    elif due_today_unpaid:
        return "pending_payment"
    else:
        return "committed"
