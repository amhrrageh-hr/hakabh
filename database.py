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
        if not res or res[0] != "ok":
            conn.close()
            raise sqlite3.DatabaseError(f"integrity_check failed: {res}")
        # التحقق الفعلي من سلامة مخطط الجداول الحرجة مثل _sync_meta و settings
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for check_tbl in ("_sync_meta", "settings", "staff"):
            if check_tbl in tables:
                conn.execute(f"SELECT 1 FROM {check_tbl} LIMIT 1").fetchall()
        conn.close()
        return
    except Exception as e:
        print(f"[DB-Repair] ⚠️ Error inspecting database integrity: {e}")

    # في حال فشل الفحص، يتم أخذ نسخة احتياطية من الملف التالف وإنشاء قاعدة سليمة
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        corrupted_backup = f"{db_path}.corrupted_{timestamp}"
        import shutil
        shutil.copy2(db_path, corrupted_backup)
        print(f"[DB-Repair] Corrupted DB backed up to: {corrupted_backup}")

        for suffix in ("", "-wal", "-shm"):
            p = f"{db_path}{suffix}"
            if os.path.exists(p):
                os.remove(p)
        print("[DB-Repair] Removed corrupted DB file, will rebuild fresh schema...")
    except Exception as e:
        print(f"[DB-Repair] [ERROR] Could not replace corrupted database: {e}")

def get_local_database_url():
    db_path = get_local_db_path()
    verify_and_repair_sqlite_db(db_path)
    return f"sqlite:///{db_path}"

# الرابط الافتراضي للاتصال بقاعدة بيانات السيرفر (Railway PostgreSQL) في حال عدم توفر ملف .env
DEFAULT_SERVER_DATABASE_URL = "postgresql://postgres:RQUnDoGWAynftxOKdmpJYROHXYafsBnB@thomas.proxy.rlwy.net:11982/railway"

def get_server_database_url():
    url = os.getenv("SERVER_DATABASE_URL") or ""
    if not url:
        env_url = os.getenv("DATABASE_URL", "")
        if "postgres" in env_url:
            url = env_url
    if not url:
        url = DEFAULT_SERVER_DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def check_server_connection(server_url: str, timeout=2) -> bool:
    """فحص سريع لإمكانية الوصول لخادم PostgreSQL"""
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
        sock = socket.create_connection((host, port), timeout=min(timeout, 2))
        sock.close()
        return True
    except Exception:
        return False

def get_database_url():
    """
    تحديد URL قاعدة البيانات:
    - في بيئة السيرفر السحابي (Railway/Render): يستخدم PostgreSQL مباشرة.
    - في تطبيق سطح المكتب: يستخدم دائماً قاعدة البيانات المحلية السريعة (Local-First SQLite)
      لضمان سرعة استجابة فورية (0ms) بدون أي تعليق، بينما يتولى محرك المزامنة الخلفي
      مزامنة كافة التعديلات مع سيرفر PostgreSQL على Railway لحظياً في الخلفية.
    """
    global _db_mode_online

    # البيئات السحابية (الويب على Railway/Render): استخدم PostgreSQL مباشرة
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER"):
        url = get_server_database_url()
        if url:
            _db_mode_online = True
            print("[DB-Hybrid] Mode: CLOUD (Railway/Render) -> PostgreSQL")
            return url

    server_url = get_server_database_url()
    if server_url and check_server_connection(server_url, timeout=2):
        _db_mode_online = True
        print("[DB-Hybrid] Mode: LOCAL-FIRST + ONLINE CLOUD SYNC (Railway reachable)")
    else:
        _db_mode_online = False
        print("[DB-Hybrid] Mode: LOCAL-FIRST OFFLINE (Server unreachable)")

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
        # إعدادات التوصيل للشبكات والـ Remote PostgreSQL مع تفعيل TCP Keepalives لمنع انقطاع البروكسي
        return create_engine(
            url,
            connect_args={
                "connect_timeout": 10,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            },
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=180,
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
#  مزامنة البيانات ثنائية الاتجاه: SQLite (محلي) ↔ PostgreSQL (السيرفر)
# =====================================================================

# الجداول التي يتم مزامنتها (مرتبة حسب الاعتمادية للإدراج والتحديث)
SYNC_TABLES_ORDER = [
    "seasons", "categories", "subscriber_numbers",
    "subscribers", "staff", "payments", "winners",
    "expenses", "settings", "admin_notifications",
    "subscriber_messages", "visit_logs"
]

# الأعمدة المنطقية (Boolean) في كل جدول لتحويلها من 0/1 في SQLite إلى True/False في PostgreSQL
BOOLEAN_COLUMNS_MAP = {
    "seasons": {"is_current"},
    "categories": {"is_active"},
    "subscriber_numbers": {"is_reserved"},
    "payments": {"is_paid", "is_staff_settled"},
    "winners": {"is_received", "is_notif_seen"},
    "admin_notifications": {"is_read"},
    "subscriber_messages": {"is_active"},
}


def _get_pk_col(table_name: str) -> str:
    return "key" if table_name == "settings" else "id"


def ensure_local_sync_tracking(local_engine=None):
    """
    إنشاء جداول و Triggers التتبع التلقائي في SQLite المحلي (hakbah.db).
    يسجل تلقائياً أي إضافة أو تعديل أو حذف يحدث أثناء العمل أوفلاين.
    """
    dispose_after = False
    if local_engine is None:
        local_engine = create_configured_engine(get_local_database_url())
        dispose_after = True

    try:
        # التأكد من أن جميع جداول النظام منشأة في القاعدة المحلية أولاً
        if "Base" in globals():
            try:
                Base.metadata.create_all(bind=local_engine)
            except Exception:
                pass

        with local_engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS _sync_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """))
            conn.execute(text("""
                INSERT OR IGNORE INTO _sync_meta (key, value) VALUES ('syncing_from_server', '0')
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS _sync_changes (
                    table_name TEXT NOT NULL,
                    pk_val TEXT NOT NULL,
                    op TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (table_name, pk_val)
                )
            """))

            # إنشاء Triggers لكل جدول لمراقبة الإضافة والتعديل والحذف في الوضع المحلي
            existing_tables = {
                r[0] for r in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).fetchall()
            }

            for tbl in SYNC_TABLES_ORDER:
                if tbl not in existing_tables:
                    continue
                pk = _get_pk_col(tbl)

                conn.execute(text(f"""
                    CREATE TRIGGER IF NOT EXISTS trg_sync_ins_{tbl}
                    AFTER INSERT ON {tbl}
                    WHEN COALESCE((SELECT value FROM _sync_meta WHERE key = 'syncing_from_server'), '0') = '0'
                    BEGIN
                        INSERT OR REPLACE INTO _sync_changes (table_name, pk_val, op, updated_at)
                        VALUES ('{tbl}', CAST(NEW.{pk} AS TEXT), 'UPSERT', CURRENT_TIMESTAMP);
                    END;
                """))

                conn.execute(text(f"""
                    CREATE TRIGGER IF NOT EXISTS trg_sync_upd_{tbl}
                    AFTER UPDATE ON {tbl}
                    WHEN COALESCE((SELECT value FROM _sync_meta WHERE key = 'syncing_from_server'), '0') = '0'
                    BEGIN
                        INSERT OR REPLACE INTO _sync_changes (table_name, pk_val, op, updated_at)
                        VALUES ('{tbl}', CAST(NEW.{pk} AS TEXT), 'UPSERT', CURRENT_TIMESTAMP);
                    END;
                """))

                conn.execute(text(f"""
                    CREATE TRIGGER IF NOT EXISTS trg_sync_del_{tbl}
                    AFTER DELETE ON {tbl}
                    WHEN COALESCE((SELECT value FROM _sync_meta WHERE key = 'syncing_from_server'), '0') = '0'
                    BEGIN
                        INSERT OR REPLACE INTO _sync_changes (table_name, pk_val, op, updated_at)
                        VALUES ('{tbl}', CAST(OLD.{pk} AS TEXT), 'DELETE', CURRENT_TIMESTAMP);
                    END;
                """))
    except Exception as e:
        print(f"[Sync-Track] Warning setting up local triggers: {e}")
    finally:
        if dispose_after:
            local_engine.dispose()


def has_pending_local_changes() -> int:
    """إرجاع عدد التعديلات المحلية المعلقة التي لم تُرحّل بعد إلى السيرفر"""
    db_path = get_local_db_path()
    if not os.path.exists(db_path):
        return 0
    import sqlite3
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_sync_changes'")
        if not cur.fetchone():
            conn.close()
            return 0
        cur.execute("SELECT COUNT(*) FROM _sync_changes")
        cnt = cur.fetchone()[0] or 0
        conn.close()
        return cnt
    except Exception:
        return 0


def _normalize_row_for_postgres(table_name: str, row_dict: dict) -> dict:
    """تحويل قيم SQLite (مثل 0/1 للأعمدة المنطقية) لتتوافق تماماً مع PostgreSQL"""
    bool_cols = BOOLEAN_COLUMNS_MAP.get(table_name, set())
    cleaned = {}
    for k, v in row_dict.items():
        if k in bool_cols and v is not None:
            cleaned[k] = bool(int(v)) if isinstance(v, (int, float, str)) and str(v).isdigit() else bool(v)
        elif isinstance(v, str) and v.strip() == "" and ("date" in k or k.endswith("_at") or k == "last_seen"):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def sync_local_to_server() -> int:
    """
    ترحيل التعديلات التي تمت في SQLite المحلي أثناء انقطاع الإنترنت إلى PostgreSQL على السيرفر.
    يرحل الإضافات والتعديلات والحذف بدقة، ويحدث عدادات الترقيم (Sequences) في السيرفر.
    يُرجع إجمالي عدد السجلات التي تمت مزامنتها.
    """
    with _sync_lock:
        server_url = get_server_database_url()
        local_url = get_local_database_url()

        if not server_url:
            print("[Sync] No server URL. Skipping sync.")
            return 0

        pending_count = has_pending_local_changes()
        if pending_count == 0:
            print("[Sync] No pending local changes to push.")
            return 0

        print(f"[Sync] Starting local → server sync ({pending_count} pending changes)...")
        try:
            local_engine = create_configured_engine(local_url)
            server_engine = create_configured_engine(server_url)

            # التأكد من أن السيرفر متاح
            with server_engine.connect() as _conn:
                _conn.execute(text("SELECT 1"))
            global _db_mode_online
            _db_mode_online = True

            ensure_local_sync_tracking(local_engine)

            LocalSession = sessionmaker(bind=local_engine)
            ServerSession = sessionmaker(bind=server_engine)

            local_db = LocalSession()
            server_db = ServerSession()

            total_synced = 0
            try:
                changes = local_db.execute(
                    text("SELECT table_name, pk_val, op FROM _sync_changes")
                ).fetchall()

                if not changes:
                    return 0

                upserts_by_table = {}
                deletes_by_table = {}
                for tbl, pk_val, op in changes:
                    if op == "DELETE":
                        deletes_by_table.setdefault(tbl, []).append(pk_val)
                    else:
                        upserts_by_table.setdefault(tbl, []).append(pk_val)

                # إذا كان هناك مشتركين للترحيل، نتأكد من إزالة قيد التفرد القديم على الهاتف إن وجد
                if upserts_by_table.get("subscribers"):
                    try:
                        has_uq = server_db.execute(text(
                            "SELECT 1 FROM pg_indexes WHERE tablename = 'subscribers' AND indexname IN ('ix_subscribers_phone', 'subscribers_phone_key')"
                        )).fetchone()
                        if has_uq:
                            server_db.execute(text("SET lock_timeout = '3s'"))
                            server_db.execute(text("ALTER TABLE subscribers DROP CONSTRAINT IF EXISTS subscribers_phone_key"))
                            server_db.execute(text("DROP INDEX IF EXISTS ix_subscribers_phone"))
                            server_db.execute(text("CREATE INDEX IF NOT EXISTS idx_subscribers_phone ON subscribers (phone)"))
                            server_db.commit()
                    except Exception:
                        server_db.rollback()

                # 1. تطبيق عمليات الحذف أولاً بالترتيب العكسي للاعتمادية (الأبناء قبل الآباء)
                for table_name in reversed(SYNC_TABLES_ORDER):
                    del_pks = deletes_by_table.get(table_name, [])
                    if not del_pks:
                        continue
                    pk_col = _get_pk_col(table_name)
                    try:
                        for pk_v in del_pks:
                            cast_val = pk_v if pk_col == "key" else int(pk_v)
                            if table_name == "subscribers":
                                # فك الارتباط قبل حذف المشترك على السيرفر
                                server_db.execute(
                                    text("DELETE FROM visit_logs WHERE subscriber_id = :sid"),
                                    {"sid": cast_val}
                                )
                                server_db.execute(
                                    text("DELETE FROM payments WHERE subscriber_id = :sid"),
                                    {"sid": cast_val}
                                )
                                server_db.execute(
                                    text("UPDATE subscriber_numbers SET is_reserved = FALSE, subscriber_id = NULL WHERE subscriber_id = :sid"),
                                    {"sid": cast_val}
                                )
                            server_db.execute(
                                text(f"DELETE FROM {table_name} WHERE {pk_col} = :pk"),
                                {"pk": cast_val}
                            )
                            local_db.execute(
                                text("DELETE FROM _sync_changes WHERE table_name = :t AND pk_val = :p"),
                                {"t": table_name, "p": str(pk_v)}
                            )
                            total_synced += 1
                        server_db.commit()
                        local_db.commit()
                        print(f"[Sync] [DELETE] {table_name}: {len(del_pks)} records deleted on server")
                    except Exception as e:
                        server_db.rollback()
                        print(f"[Sync] [WARN] Error deleting from {table_name}: {e}")

                # 2. تطبيق عمليات الإضافة والتعديل (UPSERT) بالترتيب الاعتمادي الصحيح
                deferred_sub_number_links = []  # (number_id, subscriber_id) لفك الاعتمادية الدائرية

                for table_name in SYNC_TABLES_ORDER:
                    ups_pks = upserts_by_table.get(table_name, [])
                    if not ups_pks:
                        continue

                    pk_col = _get_pk_col(table_name)
                    try:
                        keys = local_db.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
                        col_names = [r[1] for r in keys]

                        # جلب أعمدة الجدول في السيرفر للتأكد من التطابق
                        srv_cols_res = server_db.execute(text(
                            "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
                        ), {"t": table_name}).fetchall()
                        srv_col_set = {r[0] for r in srv_cols_res} if srv_cols_res else set(col_names)
                        valid_cols = [c for c in col_names if c in srv_col_set]

                        cols_sql = ", ".join(valid_cols)
                        placeholders = ", ".join([f":{c}" for c in valid_cols])
                        update_set = ", ".join([
                            f"{c} = EXCLUDED.{c}"
                            for c in valid_cols if c != pk_col
                        ])
                        upsert_sql = text(f"""
                            INSERT INTO {table_name} ({cols_sql})
                            VALUES ({placeholders})
                            ON CONFLICT ({pk_col}) DO UPDATE SET {update_set}
                        """)

                        existing_srv_subs = None
                        if table_name == "subscriber_numbers":
                            existing_srv_subs = {
                                r[0] for r in server_db.execute(text("SELECT id FROM subscribers")).fetchall()
                            }

                        synced_in_table = 0
                        batch_rows = []
                        batch_pks = []

                        for pk_v in ups_pks:
                            cast_val = pk_v if pk_col == "key" else int(pk_v)
                            row = local_db.execute(
                                text(f"SELECT * FROM {table_name} WHERE {pk_col} = :pk"),
                                {"pk": cast_val}
                            ).fetchone()

                            if not row:
                                local_db.execute(
                                    text("DELETE FROM _sync_changes WHERE table_name = :t AND pk_val = :p"),
                                    {"t": table_name, "p": str(pk_v)}
                                )
                                continue

                            raw_dict = dict(zip(col_names, row))
                            row_dict = _normalize_row_for_postgres(
                                table_name,
                                {k: raw_dict[k] for k in valid_cols}
                            )

                            # فك الاعتمادية الدائرية بين subscriber_numbers و subscribers
                            if table_name == "subscriber_numbers" and row_dict.get("subscriber_id"):
                                sub_id_val = row_dict["subscriber_id"]
                                if existing_srv_subs is not None and sub_id_val not in existing_srv_subs:
                                    deferred_sub_number_links.append((row_dict["id"], sub_id_val))
                                    row_dict["subscriber_id"] = None

                            batch_rows.append(row_dict)
                            batch_pks.append(str(pk_v))

                            if len(batch_rows) >= 150:
                                server_db.execute(upsert_sql, batch_rows)
                                server_db.commit()
                                for b_pk in batch_pks:
                                    local_db.execute(
                                        text("DELETE FROM _sync_changes WHERE table_name = :t AND pk_val = :p"),
                                        {"t": table_name, "p": b_pk}
                                    )
                                local_db.commit()
                                synced_in_table += len(batch_rows)
                                total_synced += len(batch_rows)
                                batch_rows.clear()
                                batch_pks.clear()

                        if batch_rows:
                            server_db.execute(upsert_sql, batch_rows)
                            server_db.commit()
                            for b_pk in batch_pks:
                                local_db.execute(
                                    text("DELETE FROM _sync_changes WHERE table_name = :t AND pk_val = :p"),
                                    {"t": table_name, "p": b_pk}
                                )
                            local_db.commit()
                            synced_in_table += len(batch_rows)
                            total_synced += len(batch_rows)

                        # تحديث عداد الترقيم التلقائي Sequence في PostgreSQL لمنع تعارض الـ ID مستقبلاً
                        if pk_col == "id":
                            try:
                                server_db.execute(text(f"""
                                    SELECT setval(
                                        pg_get_serial_sequence('{table_name}', 'id'),
                                        COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                                        true
                                    )
                                """))
                                server_db.commit()
                            except Exception:
                                server_db.rollback()

                        if synced_in_table > 0:
                            print(f"[Sync] [UPSERT] {table_name}: {synced_in_table} records synced to server")
                    except Exception as e:
                        server_db.rollback()
                        print(f"[Sync] [WARN] Error syncing {table_name}: {e}")

                # 3. استكمال ربط أرقام المشتركين المؤجلة بعد إدراج المشتركين
                if deferred_sub_number_links:
                    try:
                        for num_id, sub_id_val in deferred_sub_number_links:
                            server_db.execute(
                                text("UPDATE subscriber_numbers SET subscriber_id = :sid, is_reserved = TRUE WHERE id = :nid"),
                                {"sid": sub_id_val, "nid": num_id}
                            )
                        server_db.commit()
                    except Exception as e:
                        server_db.rollback()
                        print(f"[Sync] [WARN] Error linking deferred subscriber_numbers: {e}")

                print(f"[Sync] Local → Server sync complete ({total_synced} operations applied).")
                return total_synced

            finally:
                local_db.close()
                server_db.close()
                local_engine.dispose()
                server_engine.dispose()

        except Exception as e:
            _db_mode_online = False
            print(f"[Sync] [ERROR] Sync failed: {e}")
            return 0


def sync_server_to_local() -> bool:
    """
    مزامنة تزايدية آمنة (Non-Destructive Incremental Upsert) من السيرفر (PostgreSQL) إلى قاعدة البيانات المحلية (SQLite).
    لا تمسح الجداول أثناء عمل البرنامج، ولا تمس أي سجل محلي قيد التعديل في _sync_changes.
    """
    global _db_mode_online
    if has_pending_local_changes() > 0:
        # إذا وجدت تغييرات محلية لم ترحل بعد، نرحلها أولاً إلى السيرفر قبل سحب أي تحديثات
        sync_local_to_server()
        if has_pending_local_changes() > 0:
            return False

    with _sync_lock:
        server_url = get_server_database_url()
        local_url = get_local_database_url()
        if not server_url:
            return False

        try:
            local_engine = create_configured_engine(local_url)
            server_engine = create_configured_engine(server_url)

            ensure_local_sync_tracking(local_engine)

            # 1. قراءة جميع الجداول من السيرفر أولاً في الذاكرة وإغلاق اتصال السيرفر فوراً
            server_data = {}
            with server_engine.connect() as s_conn:
                s_conn.execute(text("SELECT 1"))
                _db_mode_online = True
                for table_name in SYNC_TABLES_ORDER:
                    try:
                        rows = s_conn.execute(text(f"SELECT * FROM {table_name}")).fetchall()
                        if rows:
                            srv_cols = list(rows[0]._mapping.keys())
                            server_data[table_name] = (srv_cols, [dict(r._mapping) for r in rows])
                        else:
                            server_data[table_name] = ([], [])
                    except Exception as tbl_err:
                        print(f"[Sync-Pull] [WARN] Could not fetch table {table_name}: {tbl_err}")

            server_engine.dispose()

            # 2. تحديث البيانات في SQLite المحلي بدون مسح الجداول (Non-destructive Upsert)
            with local_engine.begin() as l_conn:
                # قراءة أي مفاتيح تم تعديلها محلياً أثناء الاتصال بالسيرفر لحمايتها من الكتابة فوقها
                dirty_rows = l_conn.execute(text("SELECT table_name, pk_val FROM _sync_changes")).fetchall()
                dirty_map = {}
                for t_name, p_val in dirty_rows:
                    dirty_map.setdefault(t_name, set()).add(str(p_val))

                l_conn.execute(text("UPDATE _sync_meta SET value = '1' WHERE key = 'syncing_from_server'"))
                l_conn.execute(text("PRAGMA foreign_keys = OFF"))
                try:
                    for table_name in SYNC_TABLES_ORDER:
                        if table_name not in server_data:
                            continue
                        try:
                            pk_col = _get_pk_col(table_name)
                            dirty_pks = dirty_map.get(table_name, set())
                            srv_col_names, row_dicts = server_data[table_name]
                            local_cols_info = l_conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
                            if not local_cols_info:
                                continue
                            local_col_names = [r[1] for r in local_cols_info]

                            # معرفة المفاتيح الموجودة حالياً على السيرفر
                            srv_pks_str = {str(rd[pk_col]) for rd in row_dicts if pk_col in rd}

                            # حذف السجلات التي حُذفت من السيرفر (بشرط ألا تكون معدلة محلياً)
                            existing_local_pks = l_conn.execute(text(f"SELECT {pk_col} FROM {table_name}")).fetchall()
                            for (l_pk,) in existing_local_pks:
                                if str(l_pk) not in srv_pks_str and str(l_pk) not in dirty_pks:
                                    l_conn.execute(
                                        text(f"DELETE FROM {table_name} WHERE {pk_col} = :pk"),
                                        {"pk": l_pk}
                                    )

                            if not row_dicts:
                                continue

                            common_cols = [c for c in local_col_names if c in srv_col_names]
                            cols_sql = ", ".join(common_cols)
                            placeholders = ", ".join([f":{c}" for c in common_cols])
                            non_pk_cols = [c for c in common_cols if c != pk_col]
                            if non_pk_cols:
                                update_set = ", ".join([f"{c} = excluded.{c}" for c in non_pk_cols])
                                upsert_sql = text(
                                    f"INSERT INTO {table_name} ({cols_sql}) VALUES ({placeholders}) "
                                    f"ON CONFLICT ({pk_col}) DO UPDATE SET {update_set}"
                                )
                            else:
                                upsert_sql = text(
                                    f"INSERT OR IGNORE INTO {table_name} ({cols_sql}) VALUES ({placeholders})"
                                )

                            batch = [
                                {c: rd[c] for c in common_cols}
                                for rd in row_dicts
                                if str(rd.get(pk_col)) not in dirty_pks
                            ]
                            if batch:
                                l_conn.execute(upsert_sql, batch)
                        except Exception as tbl_err:
                            print(f"[Sync-Pull] [WARN] Could not mirror table {table_name}: {tbl_err}")
                finally:
                    l_conn.execute(text("PRAGMA foreign_keys = ON"))
                    l_conn.execute(text("UPDATE _sync_meta SET value = '0' WHERE key = 'syncing_from_server'"))

            local_engine.dispose()
            print("[Sync-Pull] [OK] Local SQLite cache updated non-destructively from Railway server.")
            return True
        except Exception as e:
            _db_mode_online = False
            print(f"[Sync-Pull] [WARN] Server → Local mirror skipped: {e}")
            return False


def try_switch_to_online():
    """
    فحص عودة الاتصال بالسيرفر ومزامنة التعديلات المحلية فوراً في الخلفية
    مع إبقاء الواجهة متصلة بقاعدة البيانات المحلية السريعة (Local-First).
    """
    global _db_mode_online
    server_url = get_server_database_url()
    if not server_url:
        return False

    if not check_server_connection(server_url, timeout=3):
        return False

    # 1. ترحيل جميع التعديلات المحلية المعلقة إلى السيرفر أولاً
    synced_count = 0
    if has_pending_local_changes() > 0:
        synced_count = sync_local_to_server()

    # 2. تحديث النسخة المحلية من السيرفر بشكل غير مدمّر
    pulled = sync_server_to_local()
    if pulled or synced_count > 0:
        _db_mode_online = True
        print(f"[DB-Hybrid] [OK] Cloud sync active (pushed {synced_count} local changes).")
        return True
    return False


def start_connectivity_monitor(check_interval=4, on_mode_change=None):
    """
    تشغيل خيط خلفي لمعمارية (Local-First + Instant Cloud Sync):
    - جميع عمليات القراءة والكتابة في الواجهة تتم محلياً بسرعة فائقة (0ms).
    - كل بضع ثوانٍ، إذا وُجد أي تعديل محلي في _sync_changes يتم ترحيله فوراً للسيرفر في الخلفية.
    - كل 60 ثانية يتم سحب أي تحديثات جديدة من السيرفر (مثل طلبات الموقع الإلكتروني) بدون تعطيل الواجهة.
    """
    def _initial_sync():
        try:
            ensure_local_sync_tracking()
            server_url = get_server_database_url()
            if server_url and check_server_connection(server_url, timeout=3):
                pushed = 0
                if has_pending_local_changes() > 0:
                    pushed = sync_local_to_server()
                pulled = sync_server_to_local()
                if (pushed > 0 or pulled) and on_mode_change:
                    on_mode_change(True)
        except Exception as e:
            print(f"[DB-Monitor] Initial sync error: {e}")

    threading.Thread(target=_initial_sync, daemon=True, name="DB-InitialSync").start()

    def _monitor():
        global _db_mode_online
        last_pull_time = _time.time()
        while True:
            _time.sleep(check_interval)
            try:
                was_online = _db_mode_online
                server_url = get_server_database_url()
                if not server_url:
                    continue

                pending = has_pending_local_changes()
                # 1. إذا كانت هناك تعديلات محلية معلقة، نحاول ترحيلها فوراً!
                if pending > 0:
                    if check_server_connection(server_url, timeout=3):
                        synced = sync_local_to_server()
                        if synced > 0 and on_mode_change:
                            on_mode_change(True)
                    else:
                        _db_mode_online = False
                        if was_online and on_mode_change:
                            on_mode_change(False)
                    continue

                # 2. فحص دوري للاتصال وسحب أي جديد من السيرفر كل 60 ثانية
                now = _time.time()
                if not _db_mode_online or (now - last_pull_time >= 60):
                    if check_server_connection(server_url, timeout=3):
                        pulled = sync_server_to_local()
                        last_pull_time = now
                        if pulled and not was_online and on_mode_change:
                            on_mode_change(True)
                    else:
                        _db_mode_online = False
                        if was_online and on_mode_change:
                            on_mode_change(False)
            except Exception as e:
                print(f"[DB-Monitor] Error: {e}")

    t = threading.Thread(target=_monitor, daemon=True, name="DB-ConnectivityMonitor")
    t.start()
    print(f"[DB-Monitor] Local-First Cloud Sync started (checking every {check_interval}s)")
    return t

Base = declarative_base()

class Subscriber(Base):
    __tablename__ = "subscribers"
    __table_args__ = (
        Index("idx_subs_cat_status", "category", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String, index=True)
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
    staff_settled_amount = Column(Float, default=0.0)
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
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=True, index=True)

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
    # ضمان تفعيل تتبع التعديلات المحلية (Triggers) على القاعدة المحلية دائماً
    if not os.getenv("RAILWAY_ENVIRONMENT") and not os.getenv("RENDER"):
        try:
            ensure_local_sync_tracking()
            if _db_mode_online and has_pending_local_changes() > 0:
                sync_local_to_server()
        except Exception as _sync_init_err:
            print(f"[Sync-Init] Warning: {_sync_init_err}")

    db = SessionLocal()
    try:
        # إذا تم التحقق من الجداول مسبقاً، تخطي الفحص البطيء لتسريع فتح البرنامج
        if not force_migration:
            try:
                mig_setting = db.query(Setting).filter(Setting.key == "schema_migrated_v7_expenses_season").first()
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
        if 'staff_settled_amount' not in columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل المبلغ المسلم جزئياً من الموظف...")
            db.execute(text("ALTER TABLE payments ADD COLUMN staff_settled_amount FLOAT DEFAULT 0.0"))
            db.execute(text(f"UPDATE payments SET staff_settled_amount = amount WHERE is_staff_settled = {bool_true} AND (staff_settled_amount IS NULL OR staff_settled_amount = 0)"))
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
        
        # إضافة حقل فئة المشتركين ومعرف الموسم لجدول المصاريف
        exp_columns = [c['name'] for c in inspector.get_columns('expenses')]
        if 'subscriber_category' not in exp_columns:
            db.execute(text("ALTER TABLE expenses ADD COLUMN subscriber_category TEXT"))
        if 'season_id' not in exp_columns:
            print("جاري تحديث قاعدة البيانات لإضافة حقل معرف الموسم في جدول المصاريف...")
            db.execute(text("ALTER TABLE expenses ADD COLUMN season_id INTEGER REFERENCES seasons(id)"))

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
                # تحديث النفقات السابقة
                db.execute(text(f"UPDATE expenses SET season_id = {first_season.id} WHERE season_id IS NULL"))
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
                # ربط أي فئات أو مشتركين أو فائزين أو نفقات ليس لديهم موسم بالموسم الأول/الحالي
                first_or_curr = db.query(Season).order_by(Season.id.asc()).first() or db.query(Season).filter(Season.is_current == True).first()
                if first_or_curr:
                    db.execute(text(f"UPDATE categories SET season_id = {first_or_curr.id} WHERE season_id IS NULL"))
                    db.execute(text(f"UPDATE subscribers SET season_id = {first_or_curr.id} WHERE season_id IS NULL"))
                    db.execute(text(f"UPDATE winners SET season_id = {first_or_curr.id} WHERE season_id IS NULL"))
                    db.execute(text(f"UPDATE expenses SET season_id = {first_or_curr.id} WHERE season_id IS NULL"))
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

        # إزالة قيد التفرد القديم على رقم الهاتف في جدول المشتركين للسماح للمشترك بالاشتراك في أكثر من فئة
        try:
            if is_postgres:
                db.execute(text("ALTER TABLE subscribers DROP CONSTRAINT IF EXISTS subscribers_phone_key"))
                db.execute(text("DROP INDEX IF EXISTS ix_subscribers_phone"))
                db.execute(text("CREATE INDEX IF NOT EXISTS idx_subscribers_phone ON subscribers (phone)"))
                db.commit()
            else:
                db.execute(text("DROP INDEX IF EXISTS ix_subscribers_phone"))
                db.commit()
                # التحقق مما إذا كان جدول subscribers في SQLite يحتوي على UNIQUE مضمن على عمود phone
                tbl_sql_row = db.execute(
                    text("SELECT sql FROM sqlite_master WHERE type='table' AND name='subscribers'")
                ).fetchone()
                tbl_sql = (tbl_sql_row[0] or "") if tbl_sql_row else ""
                if "UNIQUE" in tbl_sql.upper():
                    import re as _re
                    new_tbl_sql = _re.sub(r"\bUNIQUE\b", "", tbl_sql, flags=_re.IGNORECASE)
                    new_tbl_sql = _re.sub(
                        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`'\[]?subscribers[\"`'\]]?",
                        "CREATE TABLE subscribers_new",
                        new_tbl_sql,
                        count=1,
                        flags=_re.IGNORECASE,
                    )
                    db.execute(text("PRAGMA foreign_keys=OFF"))
                    db.execute(text("DROP TABLE IF EXISTS subscribers_new"))
                    db.execute(text(new_tbl_sql))
                    db.execute(text("INSERT INTO subscribers_new SELECT * FROM subscribers"))
                    db.execute(text("DROP TABLE subscribers"))
                    db.execute(text("ALTER TABLE subscribers_new RENAME TO subscribers"))
                    db.execute(text("PRAGMA foreign_keys=ON"))
                    db.commit()
                    ensure_local_sync_tracking()
                db.execute(text("CREATE INDEX IF NOT EXISTS idx_subscribers_phone ON subscribers (phone)"))
                db.commit()
        except Exception as _uq_err:
            print(f"[DB-Migration] Phone unique index removal notice: {_uq_err}")
            db.rollback()

        # Add default settings if not exists
        reg_setting = db.query(Setting).filter(Setting.key == "registration_open").first()
        if not reg_setting:
            db.add(Setting(key="registration_open", value="true"))

        # حفظ علامة اكتمال تهيئة الجداول لتسريع الفتح اللاحق
        mig_setting = db.query(Setting).filter(Setting.key == "schema_migrated_v7_expenses_season").first()
        if not mig_setting:
            db.add(Setting(key="schema_migrated_v7_expenses_season", value="true"))
        else:
            mig_setting.value = "true"

        db.commit()
    except Exception as e:
        print(f"An error occurred during DB initialization: {e}")
        db.rollback()
    finally:
        db.close()


def get_linked_subscriber_accounts(db: Session, sub_or_id) -> list:
    """
    جلب جميع حسابات المشترك في الفئات المختلفة المرتبطة بنفس المشترك (عبر رقم الهاتف أو الاسم).
    مرتبة حسب المعرف (الأقدم فالأحدث).
    """
    if not sub_or_id:
        return []
    sub = sub_or_id if isinstance(sub_or_id, Subscriber) else db.get(Subscriber, int(sub_or_id))
    if not sub:
        return []

    phone_clean = (sub.phone or "").strip()
    name_clean = (sub.name or "").strip()

    if phone_clean:
        accounts = (
            db.query(Subscriber)
            .filter(Subscriber.phone == phone_clean)
            .order_by(Subscriber.id.asc())
            .all()
        )
    elif name_clean:
        accounts = (
            db.query(Subscriber)
            .filter(Subscriber.name == name_clean)
            .order_by(Subscriber.id.asc())
            .all()
        )
    else:
        accounts = [sub]

    if not accounts:
        return [sub]
    return accounts

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
