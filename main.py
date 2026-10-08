from fastapi import FastAPI, Depends, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import database as db_mod
import security
import datetime
import re
import traceback
import os
import asyncio
import sys
import logging
import secrets

# تحديد المسار الصحيح سواء كان البرنامج مجمّعاً (exe) أو يعمل كسكريبت عادي
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import requests
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import textwrap
import platform
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# إعداد المسجل (Logger)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── إدارة SECRET_KEY بشكل آمن ──
def _load_or_create_secret_key() -> str:
    """يحاول قراءة SECRET_KEY من البيئة أو ملف .env.
    إذا لم يوجد، يولد مفتاحاً عشوائياً آمناً ويحفظه في .env لإعادة الاستخدام."""
    # 1. من متغيرات البيئة (أولوية قصوى — مناسب للإنتاج)
    env_key = os.getenv("SECRET_KEY")
    if env_key:
        return env_key

    # 2. تحديد مسار ملف .env بشكل دائم (سواء كان في مجلد exe للبرنامج المجمّع أو مجلد العمل العادي)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = BASE_DIR
    env_file = os.path.join(exe_dir, ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("SECRET_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val

    # 3. توليد مفتاح جديد وحفظه في .env
    new_key = secrets.token_hex(32)
    try:
        with open(env_file, "a", encoding="utf-8") as f:
            f.write(f"\nSECRET_KEY={new_key}\n")
        logger.info("تم توليد SECRET_KEY جديد وحفظه في ملف .env")
    except Exception as e:
        logger.warning(f"تعذر حفظ SECRET_KEY في .env: {e}")
    return new_key

secret_key = _load_or_create_secret_key()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """إدارة دورة حياة التطبيق: بدء المهام الخلفية عند التشغيل وإيقافها عند الإغلاق"""
    # بدء مهمة تنظيف المشتركين المنتهية صلاحيتهم
    cleanup_task = asyncio.create_task(cleanup_expired_pending_subscribers())
    logger.info("✅ تم تشغيل مهمة التنظيف التلقائي للمشتركين المنتهية صلاحيتهم")
    yield
    # إيقاف المهمة عند إغلاق التطبيق
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("🛑 تم إيقاف مهمة التنظيف التلقائي")

app = FastAPI(title="هكبة المليون - Million Hakbah", lifespan=lifespan)

# Add Session Middleware for secure user tracking without showing IDs in URL
app.add_middleware(
    SessionMiddleware,
    secret_key=secret_key,
    https_only=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    same_site=os.getenv("SESSION_COOKIE_SAMESITE", "lax")
)

# Initialize database
db_mod.init_db()

# Mount static files and templates
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

try:
    if os.path.exists(STATIC_DIR):
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
except Exception as e:
    print(f"تنبيه: فشل تحميل المجلدات الثابتة: {e}")

@app.get('/service-worker.js')
async def service_worker():
    return FileResponse(os.path.join(STATIC_DIR, 'service-worker.js'))

# Route for offline fallback when service worker cannot fetch pages
@app.get('/offline', response_class=HTMLResponse)
async def offline_page():
    return FileResponse(os.path.join(TEMPLATES_DIR, 'offline.html'))

# Dependency
def get_db():
    db = db_mod.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def is_registration_open(db: Session) -> bool:
    reg_setting = db.query(db_mod.Setting).filter(db_mod.Setting.key == "registration_open").first()
    return reg_setting.value == "true" if reg_setting else False

# مدير اتصالات WebSocket لإرسال التحديثات الفورية
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}

    async def connect(self, websocket: WebSocket, subscriber_id: int):
        await websocket.accept()
        if subscriber_id not in self.active_connections:
            self.active_connections[subscriber_id] = []
        self.active_connections[subscriber_id].append(websocket)

    def disconnect(self, websocket: WebSocket, subscriber_id: int):
        if subscriber_id in self.active_connections:
            if websocket in self.active_connections[subscriber_id]:
                self.active_connections[subscriber_id].remove(websocket)

    async def notify_subscriber(self, subscriber_id: int, message: str):
        if subscriber_id in self.active_connections:
            for connection in self.active_connections[subscriber_id]:
                try:
                    await connection.send_text(message)
                except: pass

manager = ConnectionManager()

async def cleanup_expired_pending_subscribers():
    while True:
        db = None
        try:
            db = db_mod.SessionLocal()
            threshold = datetime.datetime.now() - datetime.timedelta(hours=48)
            
            expired_subs = db.query(db_mod.Subscriber).filter(
                db_mod.Subscriber.status == 'pending',
                db_mod.Subscriber.created_at <= threshold
            ).all()
            
            for sub in expired_subs:
                # تحرير الرقم
                if sub.selected_number_id:
                    num = db.query(db_mod.SubscriberNumber).filter(db_mod.SubscriberNumber.id == sub.selected_number_id).first()
                    if num:
                        num.is_reserved = False
                        num.subscriber_id = None
                
                # حذف الأقساط
                db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sub.id).delete()
                
                # حذف المشترك
                db.delete(sub)
                
            db.commit()
        except Exception as e:
            print(f"Cleanup error: {e}")
        finally:
            if db:
                db.close()
            
        await asyncio.sleep(3600) # فحص كل ساعة

# تمت إزالة @app.on_event("startup") المهجور واستبداله بـ lifespan أعلاه

@app.get("/", response_class=HTMLResponse)
async def read_registration(request: Request, db: Session = Depends(get_db)):
    is_open = is_registration_open(db)
    categories = db.query(db_mod.Category).filter(db_mod.Category.is_active == True).all()
    return templates.TemplateResponse(request=request, name="registration.html", context={
        "request": request, 
        "is_open": is_open,
        "categories": categories
    })

@app.get("/api/numbers/{cat_id}")
async def get_available_numbers(cat_id: int, db: Session = Depends(get_db)):
    # Optimized query to find numbers not yet assigned to any active subscriber
    numbers = db.query(db_mod.SubscriberNumber).filter(
        db_mod.SubscriberNumber.category_id == cat_id,
        db_mod.SubscriberNumber.is_reserved == False,
        ~db_mod.SubscriberNumber.number.in_(
            db.query(db_mod.Subscriber.subscriber_number).filter(db_mod.Subscriber.subscriber_number != None)
        )
    ).all()
    return [{"id": n.id, "number": n.number} for n in numbers]

@app.post("/register")
async def register_subscriber(
    name: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    national_id: str = Form(""),
    address: str = Form(""),
    email: str = Form(""),
    category_id: int = Form(...),
    number_id: int = Form(...),
    db: Session = Depends(get_db)
):
    if not is_registration_open(db):
        return JSONResponse(status_code=400, content={"message": "التسجيل مغلق حالياً"})

    name = name.strip()
    phone = phone.strip()
    if not name:
        return JSONResponse(status_code=400, content={"message": "الاسم مطلوب."})
    if not re.fullmatch(r"\d{9,15}", phone):
        return JSONResponse(status_code=400, content={"message": "أدخل رقم هاتف صالح مكون من 9 إلى 15 رقماً."})
    if len(password) < 6:
        return JSONResponse(status_code=400, content={"message": "كلمة المرور يجب أن تكون 6 أحرف على الأقل."})

    existing = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.phone == phone).first()
    if existing:
        return JSONResponse(status_code=400, content={"message": "رقم الهاتف مسجل مسبقاً"})

    num_record = db.query(db_mod.SubscriberNumber).filter(
        db_mod.SubscriberNumber.id == number_id,
        db_mod.SubscriberNumber.is_reserved == False
    ).first()
    
    if not num_record:
        return JSONResponse(status_code=400, content={"message": "عذراً، هذا الرقم تم حجزه للتو."})

    cat_record = db.get(db_mod.Category, category_id)
    if not cat_record:
        return JSONResponse(status_code=400, content={"message": "الفئة المحددة غير موجودة."})
    
    try:
        new_sub = db_mod.Subscriber(
            name=name, 
            phone=phone, 
            password=security.hash_password(password),
            national_id=national_id.strip() or None,
            address=address.strip() or None,
            email=email.strip() or None,
            category=cat_record.name,
            selected_number_id=number_id,
            subscriber_number=num_record.number
        )
        db.add(new_sub)
        db.flush() 

        num_record.is_reserved = True
        num_record.subscriber_id = new_sub.id

        # توليد الأقساط المستحقة للمشترك الجديد بناءً على تاريخ بداية الفئة
        if cat_record.start_date:
            start_date = cat_record.start_date.date()
            today = datetime.date.today()
            days_passed = (today - start_date).days

            if days_passed >= 0:
                max_c = int(cat_record.max_cycles or 1)
                max_i = int(cat_record.max_installments or 1)
                total_possible = max_c * max_i

                # حساب عدد الأقساط التي يجب توليدها:
                # - يُولد قسطاً واحداً لكل يوم مضى (نظام الهكبة اليومي)
                # - لا يتجاوز الحد الأقصى الإجمالي للأقساط في هذه الفئة
                # - لا يتجاوز ما مضى من أيام فعلاً (+1 لتضمين اليوم الأول)
                count_to_gen = min(max(0, days_passed + 1), total_possible)

                for i in range(count_to_gen):
                    c_idx = (i // max_i) + 1
                    i_idx = (i % max_i) + 1

                    # تأمين: لا توليد إذا تجاوزنا حد الدورات
                    if c_idx > max_c:
                        break

                    due_dt = datetime.datetime.combine(
                        start_date + datetime.timedelta(days=i),
                        datetime.time.min
                    )

                    # تجنب التكرار: التحقق من عدم وجود قسط بنفس الدورة والرقم مسبقاً
                    already_exists = db.query(db_mod.Payment).filter(
                        db_mod.Payment.subscriber_id == new_sub.id,
                        db_mod.Payment.cycle_number == c_idx,
                        db_mod.Payment.installment_number == i_idx
                    ).first()

                    if not already_exists:
                        db.add(db_mod.Payment(
                            subscriber_id=new_sub.id,
                            amount=cat_record.amount,
                            due_date=due_dt,
                            is_paid=False,
                            cycle_number=c_idx,
                            installment_number=i_idx,
                            note=db_mod.build_installment_note(is_paid=False, due_date=due_dt)
                        ))

        db.commit()

        # Add an admin notification for new registration
        admin_notif = db_mod.AdminNotification(
            message=f"تم تسجيل مشترك جديد: {name} ({phone})",
            type="new_subscriber"
        )
        db.add(admin_notif)
        db.commit()
        return JSONResponse(content={"message": "تم حجز الرقم وتقديم طلبك بنجاح!"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"حدث خطأ أثناء الحفظ: {str(e)}"})

# مسار استقبال اتصالات الـ WebSocket من متصفح المشترك
@app.websocket("/ws/notifications/{subscriber_id}")
async def websocket_endpoint(websocket: WebSocket, subscriber_id: int):
    await manager.connect(websocket, subscriber_id)
    try:
        while True:
            await websocket.receive_text() # الحفاظ على الاتصال مفتوحاً
    except WebSocketDisconnect:
        manager.disconnect(websocket, subscriber_id)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

@app.post("/login")
async def login_auth(
    request: Request,
    subscriber_number: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # نقوم بتنظيف المدخلات مع الحفاظ على الأحرف لأن رقم الحساب قد يحتوي على أحرف (مثل A-1)
        raw_input = subscriber_number.strip()
        
        # 1. محاولة تسجيل الدخول كموظف أولاً
        staff = db.query(db_mod.Staff).filter(db_mod.Staff.staff_id_code == raw_input).first()
        if staff:
            if security.verify_password(password, staff.password):
                request.session["staff_id"] = int(staff.id)
                return JSONResponse(content={"success": True, "user_type": "staff"})

        # 2. إذا لم يكن موظفاً، ننتقل لمنطق المشتركين
        normalized_number = raw_input.lower()
        normalized_phone = re.sub(r"\D", "", raw_input)
        logger.info(f"Login attempt for: {raw_input}")
        
        if not raw_input:
            return JSONResponse(status_code=400, content={"message": "أدخل رقم المشترك أو الهاتف."})

        # Find subscriber by subscriber_number OR phone
        try:
            sub = db.query(db_mod.Subscriber).filter(
                or_(
                    func.lower(db_mod.Subscriber.subscriber_number) == normalized_number,
                    db_mod.Subscriber.phone == normalized_phone
                )
            ).first()
        except Exception as query_err:
            logger.error(f"Login query error, fallback to phone only: {query_err}")
            traceback.print_exc()
            sub = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.phone == normalized_phone).first()

        if not sub and normalized_phone:
            sub = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.phone == raw_input).first()

        if not sub:
            print(f"[login] لم يتم العثور على المشترك: {raw_input}", flush=True)
            return JSONResponse(status_code=401, content={"message": "بيانات الدخول غير صحيحة"})

        verified = security.verify_password(password, sub.password)
        # Fallback for legacy plaintext passwords: verify and upgrade to bcrypt
        if not verified:
            try:
                if sub.password and not sub.password.startswith(('$2b$', '$2a$', '$2y$')) and sub.password == password:
                    # Re-hash legacy plaintext password with bcrypt and save
                    sub.password = security.hash_password(password)
                    db.commit()
                    verified = True
            except Exception as ex:
                db.rollback()
                print(f"[login] password-upgrade-failed: {ex}", flush=True)

        if not verified:
            return JSONResponse(status_code=401, content={"message": "بيانات الدخول غير صحيحة"})

        # تخزين معرف المشترك في الجلسة
        request.session["sub_id"] = int(sub.id)

        # إرجاع حالة المشترك لتوجيهه للصفحة المناسبة
        return JSONResponse(content={"success": True, "status": sub.status or "pending"})
    except Exception as e:
        # Log server-side error for debugging; return generic message to client
        print(f"[login] exception: {str(e)}", flush=True)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"message": "حدث خطأ داخلي أثناء محاولة تسجيل الدخول"})

@app.get("/million-hakbah", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    try:
        # التحقق إذا كان المسجل موظفاً
        staff_id = request.session.get("staff_id")
        if staff_id:
            staff = db.query(db_mod.Staff).filter(db_mod.Staff.id == staff_id).first()
            if not staff:
                request.session.clear()
                return RedirectResponse(url="/login")
            
            # جلب الفئات لعرضها في القائمة المنسدلة للموظف
            categories = db.query(db_mod.Category).all()
            
            # تحميل جميع المشتركين مسبقا وتمريرهم كمتغير JSON
            subs = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted").all()
            subscribers_dict = {}
            for s in subs:
                cat = s.category or ""
                if cat not in subscribers_dict:
                    subscribers_dict[cat] = []
                subscribers_dict[cat].append({"id": s.id, "number": s.subscriber_number, "name": s.name})
            import json
            subscribers_json = json.dumps(subscribers_dict)

            return templates.TemplateResponse(request=request, name="staff_dashboard.html", context={
                "request": request,
                "staff": staff,
                "categories": categories,
                "subscribers_json": subscribers_json,
                "now": datetime.datetime.now()
            })

        # التحقق إذا كان المسجل مشتركاً
        sub_id = request.session.get("sub_id")
        if not sub_id:
            return RedirectResponse(url="/login")

        sub = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.id == sub_id).first()
        if not sub:
            request.session.clear()
            return RedirectResponse(url="/login")

        # إذا لم يتم قبول المشترك بعد، أعد توجيهه لصفحة الانتظار
        if (sub.status or "pending") == "pending":
            return RedirectResponse(url="/pending")
        # Load payments for the subscriber
        payments = db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sub_id)\
                     .order_by(db_mod.Payment.cycle_number, db_mod.Payment.installment_number).all()

        # جلب آخر 5 فائزين فقط
        winners = db.query(db_mod.Winner).order_by(db_mod.Winner.draw_date.desc()).limit(5).all()

        # جلب جوائز هذا المشترك تحديداً
        today_dt = datetime.datetime.now()
        sub_winnings = db.query(db_mod.Winner).filter(db_mod.Winner.subscriber_number == sub.subscriber_number).order_by(db_mod.Winner.draw_date.desc()).all()
        
        # الجوائز الحديثة التي تم الفوز بها خلال آخر 24 ساعة (تظهر في البانر التنبيهي المؤقت لليوم الأول فقط)
        recent_winnings = []
        for w in sub_winnings:
            if w.draw_date:
                diff_sec = (today_dt - w.draw_date).total_seconds()
                if 0 <= diff_sec <= 86400:  # 86400 ثانية = 24 ساعة
                    recent_winnings.append(w)
        
        # Fetch category info
        category_info = None
        if sub.category:
            category_info = db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
        else:
            print(f"[Dashboard] تنبيه: المشترك {sub.id} ليس لديه فئة محددة.", flush=True)

        # تصفية الأقساط ضمن حدود الفئة فقط (تجنب احتساب أقساط خارج max_cycles/max_installments)
        max_cycles_limit = category_info.max_cycles if category_info else None
        max_inst_limit   = category_info.max_installments if category_info else None

        def is_within_limits(p):
            if max_cycles_limit is not None and (p.cycle_number or 0) > max_cycles_limit:
                return False
            if max_inst_limit is not None and (p.installment_number or 0) > max_inst_limit:
                return False
            return True

        valid_payments = [p for p in payments if is_within_limits(p)]

        # Prepare safe payment display values
        today_dt = datetime.datetime.now()
        # إجمالي المسدد: جميع الأقساط المدفوعة ضمن الحدود
        total_paid = sum((p.amount or 0) for p in valid_payments if p.is_paid)
        # إجمالي المتبقي: الأقساط غير المدفوعة المستحقة حتى اليوم فقط (لا المستقبلية)
        total_due  = sum((p.amount or 0) for p in valid_payments if not p.is_paid and (p.due_date or today_dt) <= today_dt)
        # الاستبدال: payments تُستخدم لاحقاً للعرض - نستخدم valid_payments بدلاً منها
        payments = valid_payments
        for p in payments:
            if isinstance(p.due_date, datetime.datetime):
                p.due_date_str = p.due_date.strftime('%Y-%m-%d')
            else:
                p.due_date_str = str(p.due_date) if p.due_date else 'غير محدد'

            if isinstance(p.paid_date, datetime.datetime):
                p.paid_date_str = p.paid_date.strftime('%Y-%m-%d %H:%M')
            else:
                p.paid_date_str = str(p.paid_date) if p.paid_date else '-'

        # Calculate cycle and installment progress
        sorted_payments = sorted(payments, key=lambda x: (x.cycle_number or 0, x.installment_number or 0))
        
        current_cycle = 1
        current_installment = 1
        completed_cycles = 0
        max_cycles = category_info.max_cycles if category_info else 10
        max_installments = category_info.max_installments if category_info else 12

        if sorted_payments:
            unpaid = [p for p in sorted_payments if not p.is_paid]
            if unpaid:
                current_cycle = int(unpaid[0].cycle_number or 1)
                current_installment = int(unpaid[0].installment_number or 1)
            else:
                last = sorted_payments[-1]
                current_cycle = last.cycle_number or 1
                current_installment = last.installment_number or 1

            if category_info:
                cycle_groups = {}
                for p in sorted_payments:
                    c_num = p.cycle_number or 1
                    cycle_groups.setdefault(c_num, []).append(p)
                for c_num, c_payments in cycle_groups.items():
                    paid_count = sum(1 for p in c_payments if p.is_paid)
                    if paid_count >= max_installments:
                        completed_cycles += 1

        workflow_data = {
            "current_cycle": current_cycle,
            "current_installment": current_installment,
            "completed_cycles": completed_cycles,
            "max_cycles": max_cycles,
            "max_installments": max_installments,
            "payments_current_cycle": sorted(
                [p for p in sorted_payments if p.cycle_number == current_cycle],
                key=lambda x: (int(x.installment_number) if str(x.installment_number).isdigit() else 0)
            )
        }
        # Calculate financial status dynamically
        fin_status = db_mod.calculate_financial_status(sub, db)

        # ترتيب المدفوعات تنازلياً: أحدث دورة وأحدث قسط في الأعلى
        sorted_payments_desc = sorted(
            sorted_payments,
            key=lambda x: (-(x.cycle_number or 0), -(x.installment_number or 0))
        )

        # جلب الرسائل التوعوية والتعليمية والتذكيرية النشطة والغير منتهية الصلاحية
        now_time = datetime.datetime.now()
        announcements = db.query(db_mod.SubscriberMessage).filter(
            db_mod.SubscriberMessage.is_active == True,
            (db_mod.SubscriberMessage.start_date == None) | (db_mod.SubscriberMessage.start_date <= now_time),
            (db_mod.SubscriberMessage.end_date == None) | (db_mod.SubscriberMessage.end_date >= now_time),
            (db_mod.SubscriberMessage.target_category == 'all') | (db_mod.SubscriberMessage.target_category == None) | (db_mod.SubscriberMessage.target_category == sub.category)
        ).order_by(db_mod.SubscriberMessage.priority.asc(), db_mod.SubscriberMessage.id.desc()).all()

        # ─── احتساب إحصائيات الانضباط في السداد (للأيقونات التحفيزية) ───
        # أقساط الدورة الحالية فقط
        current_cycle_payments = workflow_data["payments_current_cycle"]
        on_time_count   = 0   # سُدِّد في موعده أو قبله
        late_count      = 0   # سُدِّد متأخراً (paid_date > due_date)
        unpaid_overdue  = 0   # لم يُسدَّد وتاريخه مضى
        today_date = now_time.date()

        for p in current_cycle_payments:
            p_due = p.due_date.date() if isinstance(p.due_date, datetime.datetime) else (p.due_date if isinstance(p.due_date, datetime.date) else None)
            if p.is_paid:
                p_paid = p.paid_date.date() if isinstance(p.paid_date, datetime.datetime) else (p.paid_date if isinstance(p.paid_date, datetime.date) else None)
                if p_paid and p_due and p_paid <= p_due:
                    on_time_count += 1
                    setattr(p, 'punctuality_status', 'on_time')
                else:
                    late_count += 1
                    setattr(p, 'punctuality_status', 'late')
            else:
                if p_due and p_due < today_date:
                    unpaid_overdue += 1
                    setattr(p, 'punctuality_status', 'unpaid_overdue')
                else:
                    setattr(p, 'punctuality_status', 'upcoming')

        return templates.TemplateResponse(request=request, name="dashboard.html", context={
            "request": request,
            "sub": sub,
            "payments": sorted_payments_desc,
            "winners": winners,
            "category_info": category_info,
            "workflow_data": workflow_data,
            "total_paid": total_paid,
            "total_due": total_due,
            "fin_status": fin_status,
            "sub_winnings": sub_winnings,
            "recent_winnings": recent_winnings,
            "announcements": announcements,
            "now": now_time,
            # إحصائيات الانضباط للأيقونات التحفيزية
            "on_time_count":  on_time_count,
            "late_count":     late_count,
            "unpaid_overdue": unpaid_overdue,
        })
    except Exception as e:
        print(f"[Dashboard Error]: {str(e)}", flush=True)
        traceback.print_exc()
        return HTMLResponse(content="<h2>حدث خطأ أثناء تحميل لوحة التحكم. يرجى التواصل مع الإدارة.</h2>", status_code=500)

@app.get("/pending", response_class=HTMLResponse)
async def pending_page(request: Request, db: Session = Depends(get_db)):
    """صفحة انتظار القبول من الإدارة للمشتركين الجدد"""
    sub_id = request.session.get("sub_id")
    if not sub_id:
        return RedirectResponse(url="/login")
    sub = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.id == sub_id).first()
    if not sub:
        request.session.clear()
        return RedirectResponse(url="/login")
    # إذا تم قبوله بالفعل، وجّهه للوحة التحكم
    if sub.status == "accepted":
        return RedirectResponse(url="/million-hakbah")
    # جلب بيانات الفئة لعرض مبلغ القسط
    category_info = None
    if sub.category:
        category_info = db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
    return templates.TemplateResponse(request=request, name="pending.html", context={
        "request": request,
        "sub": sub,
        "category_info": category_info
    })


# وظيفة إرسال الرسائل النصية
def send_sms_notification(phone: str, message: str):
    """
    هذه الوظيفة تعمل كقالب لربط أي بوابة رسائل (SMS Gateway).
    يجب عليك وضع رابط API الخاص بمزود الخدمة لديك هنا.
    """
    try:
        # مثال لمنطق الربط مع مزود خدمة (مثل Twilio أو مزود محلي)
        # api_url = "https://api.smsprovider.com/send"
        # params = {
        #     "apiKey": "YOUR_API_KEY",
        #     "to": phone,
        #     "message": message
        # }
        # response = requests.get(api_url, params=params)
        # return response.status_code == 200
        print(f"[SMS Simulator] إرسال إلى {phone}: {message}")
        return True
    except Exception as e:
        print(f"[SMS Error]: {str(e)}")
        return False

# مسار لجلب المشتركين التابعين لفئة معينة (يستخدمه الموظف في الواجهة)
@app.get("/api/staff/subscribers/{cat_name}")
async def get_subs_by_category(cat_name: str, db: Session = Depends(get_db)):
    subs = db.query(db_mod.Subscriber).filter(
        db_mod.Subscriber.category == cat_name,
        db_mod.Subscriber.status == "accepted"
    ).all()
    return [{"id": s.id, "number": s.subscriber_number, "name": s.name} for s in subs]

def _get_staff_id(request: Request) -> int:
    raw_staff_id = request.session.get("staff_id")
    if raw_staff_id is None:
        raise PermissionError("غير مصرح للموظفين فقط")
    return int(raw_staff_id)


def process_staff_payment(
    db: Session,
    staff_id: int,
    subscriber_id: int,
    amount: float,
    note: str,
    client_reference: str = None
):
    if amount <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")

    sub = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.id == subscriber_id).first()
    if not sub:
        raise ValueError("المشترك غير موجود")

    if client_reference:
        existing_payment = db.query(db_mod.Payment).filter(
            db_mod.Payment.subscriber_id == subscriber_id,
            db_mod.Payment.client_reference == client_reference,
            db_mod.Payment.is_paid == True
        ).first()
        if existing_payment:
            return sub

    cat = db.query(db_mod.Category).filter(func.lower(db_mod.Category.name) == func.lower(sub.category)).first()
    cat_amount = cat.amount if cat else 0
    max_i = cat.max_installments if cat else 12
    max_c = cat.max_cycles if cat else 10

    if cat_amount <= 0:
        raise ValueError("خطأ في بيانات فئة المشترك، يرجى مراجعة الإدارة")

    remaining = amount
    now = datetime.datetime.now()

    targets = db.query(db_mod.Payment).filter(
        db_mod.Payment.subscriber_id == subscriber_id,
        db_mod.Payment.is_paid == False
    ).order_by(db_mod.Payment.cycle_number.asc(), db_mod.Payment.installment_number.asc()).all()

    for p in targets:
        if remaining <= 0:
            break

        if remaining < p.amount:
            balance = p.amount - remaining
            p.amount = remaining
            p.is_paid = True
            p.paid_date = now
            p.staff_id = staff_id
            p.is_staff_settled = False
            p.client_reference = client_reference
            p.note = db_mod.build_installment_note(is_paid=True, due_date=p.due_date, paid_date=now, user_note=note, is_partial=True)

            db.add(db_mod.Payment(
                subscriber_id=subscriber_id,
                amount=balance,
                due_date=p.due_date,
                is_paid=False,
                cycle_number=p.cycle_number,
                installment_number=p.installment_number,
                note=db_mod.build_installment_note(is_paid=False, due_date=p.due_date, is_partial=True)
            ))
            remaining = 0
        else:
            p.is_paid = True
            p.paid_date = now
            p.staff_id = staff_id
            p.is_staff_settled = False
            p.client_reference = client_reference
            p.note = db_mod.build_installment_note(is_paid=True, due_date=p.due_date, paid_date=now, user_note=note)
            remaining -= p.amount

    if remaining > 0 and cat_amount > 0:
        last_p = db.query(db_mod.Payment).filter(
            db_mod.Payment.subscriber_id == subscriber_id
        ).order_by(db_mod.Payment.cycle_number.desc(), db_mod.Payment.installment_number.desc()).first()

        curr_c, curr_i = 1, 1
        if last_p:
            curr_i = (last_p.installment_number or 0) + 1
            curr_c = (last_p.cycle_number or 1)
            if curr_i > max_i:
                curr_i = 1
                curr_c += 1

        safety_counter = 0
        max_safety = max_c * max_i

        while remaining > 0 and curr_c <= max_c and safety_counter < max_safety:
            safety_counter += 1
            pay_now = min(remaining, cat_amount)

            exists = db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == subscriber_id,
                db_mod.Payment.cycle_number == curr_c,
                db_mod.Payment.installment_number == curr_i
            ).first()

            if exists:
                if not exists.is_paid:
                    exists.amount = pay_now
                    exists.is_paid = True
                    exists.paid_date = now
                    exists.staff_id = staff_id
                    exists.is_staff_settled = False
                    exists.client_reference = client_reference
                    exists.note = db_mod.build_installment_note(is_paid=True, due_date=exists.due_date, paid_date=now, user_note=note)
            else:
                db.add(db_mod.Payment(
                    subscriber_id=subscriber_id,
                    amount=pay_now,
                    due_date=now,
                    paid_date=now,
                    is_paid=True,
                    cycle_number=curr_c,
                    installment_number=curr_i,
                    staff_id=staff_id,
                    note=db_mod.build_installment_note(is_paid=True, due_date=now, paid_date=now, user_note=note),
                    is_staff_settled=False,
                    client_reference=client_reference
                ))

            remaining -= pay_now
            curr_i += 1
            if curr_i > max_i:
                curr_i = 1
                curr_c += 1

    admin_notif = db_mod.AdminNotification(
        message=f"تم استلام مبلغ {amount} ريال من المشترك {sub.name}",
        type="payment_received"
    )
    db.add(admin_notif)

    return sub


# مسار معالجة سداد الموظف للمشترك
@app.post("/staff/submit-payment")
async def staff_submit_payment(
    request: Request,
    subscriber_id: int = Form(...),
    amount: float = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db)
):
    try:
        staff_id = _get_staff_id(request)
        sub = process_staff_payment(db, staff_id, subscriber_id, amount, note)
        db.commit()
        db.refresh(sub)

        await manager.notify_subscriber(subscriber_id, "refresh_dashboard")

        sms_msg = f"عزيزي {sub.name}، تم استلام مبلغ {amount} ريال بنجاح لحسابك رقم {sub.subscriber_number}. شكراً لك."
        phone_number = sub.phone
        if phone_number and not phone_number.startswith("+"):
            phone_number = "+" + phone_number
        send_sms_notification(phone_number, sms_msg)

        return JSONResponse(content={"success": True, "message": "تم تسجيل السداد بنجاح"})
    except PermissionError as e:
        return JSONResponse(status_code=401, content={"message": str(e)})
    except ValueError as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"message": str(e)})
    except Exception as e:
        db.rollback()
        print(f"[Staff Payment Error]: {str(e)}")
        return JSONResponse(status_code=500, content={"message": "حدث خطأ أثناء معالجة العملية"})


@app.post("/staff/sync-payments")
async def staff_sync_payments(request: Request, db: Session = Depends(get_db)):
    try:
        staff_id = _get_staff_id(request)
    except PermissionError as e:
        return JSONResponse(status_code=401, content={"message": str(e)})

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"message": "طلب غير صالح"})

    payments = []
    if isinstance(payload, dict):
        payments = payload.get("payments") if isinstance(payload.get("payments"), list) else []
    elif isinstance(payload, list):
        payments = payload

    if not payments:
        return JSONResponse(status_code=400, content={"message": "لا توجد دفعات للمزامنة"})

    processed = 0
    try:
        for item in payments:
            if not isinstance(item, dict):
                continue
            subscriber_id = int(item.get("subscriber_id", 0))
            amount = float(item.get("amount", 0))
            note = item.get("note", "")
            client_reference = item.get("client_reference")
            process_staff_payment(db, staff_id, subscriber_id, amount, note, client_reference)
            processed += 1

        db.commit()
        return JSONResponse(content={"success": True, "message": f"تم مزامنة {processed} دفعة بنجاح"})
    except ValueError as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"message": str(e)})
    except Exception as e:
        db.rollback()
        print(f"[Staff Sync Payment Error]: {str(e)}")
        return JSONResponse(status_code=500, content={"message": "حدث خطأ أثناء مزامنة المدفوعات"})


def reshape_arabic(text: str) -> str:
    try:
        return get_display(reshape(text))
    except Exception:
        return text

@app.get("/download-statement")
async def download_statement(request: Request, db: Session = Depends(get_db)):
    sub_id = request.session.get("sub_id")
    if not sub_id:
        return RedirectResponse(url="/login")

    sub = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.id == sub_id).first()
    if not sub:
        request.session.clear()
        return RedirectResponse(url="/login")

    payments = db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sub_id)
    payments = payments.order_by(db_mod.Payment.cycle_number, db_mod.Payment.installment_number).all()

    # جلب بيانات الفئة للتصفية ضمن الحدود
    _cat_info = None
    if sub.category:
        _cat_info = db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()

    _max_c = _cat_info.max_cycles if _cat_info else None
    _max_i = _cat_info.max_installments if _cat_info else None

    def _in_limits(p):
        if _max_c is not None and (p.cycle_number or 0) > _max_c:
            return False
        if _max_i is not None and (p.installment_number or 0) > _max_i:
            return False
        return True

    payments = [p for p in payments if _in_limits(p)]

    _now_dt = datetime.datetime.now()
    total_paid = sum((p.amount or 0) for p in payments if p.is_paid)
    total_due  = sum((p.amount or 0) for p in payments if not p.is_paid and (p.due_date or _now_dt) <= _now_dt)
    total_all  = total_paid + total_due

    # ── جلب إعدادات الشركة ──
    def get_setting(key, default=""):
        s = db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
        return s.value if s else default

    company_name       = get_setting("company_name",             "هكبة المليون")
    company_legal_name = get_setting("company_legal_name",       "الاسبوعية")
    company_record     = get_setting("company_commercial_record", "")
    company_logo_path  = get_setting("company_logo_path",        "")

    # ── إعداد الخط ──
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    W, H = A4
    M = 36

    font_name = "ArabicFont"
    possible_font_paths = [
        os.path.join(STATIC_DIR, "tahoma.ttf"),
        os.path.join(STATIC_DIR, "arial.ttf"),
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Cache/Arial.ttf",
    ]
    font_path = next((p for p in possible_font_paths if os.path.exists(p)), None)
    if font_path and font_name not in pdfmetrics.getRegisteredFontNames():
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        except Exception:
            font_name = "Helvetica"
    elif font_name not in pdfmetrics.getRegisteredFontNames():
        font_name = "Helvetica"

    # ── الألوان ──
    from reportlab.lib.colors import HexColor, white, black
    GOLD        = HexColor("#c9a84c")
    DARK_GREEN  = HexColor("#052109")
    MID_GREEN   = HexColor("#0a3d0e")
    LIGHT_GREEN = HexColor("#e8f5e9")
    PAID_COLOR  = HexColor("#1b5e20")
    UNPAID_CLR  = HexColor("#b71c1c")
    ROW_ALT     = HexColor("#f1f8f1")
    ROW_EVEN    = HexColor("#ffffff")
    BORDER_CLR  = HexColor("#c8e6c9")
    GREY_TXT    = HexColor("#546e7a")

    # ── دالة رسم نص عربي ──
    def draw_ar(cv, x, y, text, size=10, color=black):
        cv.setFont(font_name, size)
        cv.setFillColor(color)
        cv.drawString(x, y, reshape_arabic(str(text)))

    # ── دالة رسم الترويسة ──
    def draw_header(cv, page_num=1):
        # خلفية الترويسة الخضراء الداكنة
        cv.setFillColor(DARK_GREEN)
        cv.roundRect(M, H - 132, W - 2*M, 120, 8, fill=1, stroke=0)

        # الشعار على اليسار
        static_logo = os.path.join(STATIC_DIR, "logo.png")
        logo_src = (company_logo_path if (company_logo_path and os.path.exists(company_logo_path))
                    else (static_logo if os.path.exists(static_logo) else ""))
        if logo_src:
            try:
                cv.drawImage(logo_src, M + 12, H - 122, width=68, height=68,
                             preserveAspectRatio=True, mask='auto')
            except Exception:
                pass

        # اسم الهكبة في الوسط
        cx = W / 2
        cv.setFillColor(GOLD)
        cv.setFont(font_name, 22)
        cv.drawCentredString(cx, H - 68, reshape_arabic(company_name))
        cv.setFont(font_name, 11)
        cv.setFillColor(white)
        cv.drawCentredString(cx, H - 84, reshape_arabic(company_legal_name))
        if company_record:
            cv.setFont(font_name, 8)
            cv.setFillColor(HexColor("#a5d6a7"))
            cv.drawCentredString(cx, H - 97, reshape_arabic(f"السجل التجاري: {company_record}"))

        # بيانات الكشف على اليمين
        cv.setFont(font_name, 9)
        cv.setFillColor(HexColor("#a5d6a7"))
        cv.drawRightString(W - M - 12, H - 62, reshape_arabic(f"تاريخ الإصدار: {datetime.date.today().strftime('%Y-%m-%d')}"))
        cv.setFont(font_name, 8)
        cv.setFillColor(HexColor("#69f0ae"))
        cv.drawRightString(W - M - 12, H - 76, reshape_arabic("كشف حساب المشترك"))
        cv.setFont(font_name, 8)
        cv.setFillColor(white)
        cv.drawRightString(W - M - 12, H - 90, reshape_arabic(f"صفحة {page_num}"))

        # خط ذهبي فاصل
        cv.setStrokeColor(GOLD)
        cv.setLineWidth(1.5)
        cv.line(M, H - 137, W - M, H - 137)

    # ══════════════════════ الصفحة الأولى ══════════════════════
    page_num = 1
    draw_header(c, page_num)
    y = H - 152

    # ── بطاقة ثنائية: المشترك | الهكبة ──
    BOX_H = 96
    half  = (W - 2*M) / 2

    c.setFillColor(LIGHT_GREEN)
    c.setStrokeColor(BORDER_CLR)
    c.setLineWidth(0.8)
    c.roundRect(M, y - BOX_H, W - 2*M, BOX_H, 6, fill=1, stroke=1)

    # خط فاصل عمودي
    c.setStrokeColor(HexColor("#b2dfdb"))
    c.setLineWidth(0.5)
    c.line(M + half, y - 10, M + half, y - BOX_H + 10)

    # عناوين القسمين
    c.setFillColor(DARK_GREEN)
    c.roundRect(M + 6,        y - 20, half - 12, 16, 3, fill=1, stroke=0)
    c.roundRect(M + half + 6, y - 20, half - 12, 16, 3, fill=1, stroke=0)
    draw_ar(c, M + 12,        y - 15, "بيانات المشترك", size=9, color=GOLD)
    draw_ar(c, M + half + 12, y - 15, "بيانات هكبة المليون", size=9, color=GOLD)

    # بيانات المشترك
    sub_rows = [
        ("الاسم الكامل",  sub.name or "—"),
        ("رقم المشترك",   sub.subscriber_number or "—"),
        ("رقم الهاتف",    sub.phone or "—"),
        ("الفئة",         sub.category or "—"),
    ]
    yi = y - 34
    for lbl, val in sub_rows:
        draw_ar(c, M + 12, yi, f"{lbl}:", size=8, color=GREY_TXT)
        draw_ar(c, M + 90, yi, val,        size=8, color=DARK_GREEN)
        yi -= 14

    # بيانات الهكبة
    hak_rows = [
        ("اسم المنظومة",   company_name),
        ("النوع",          company_legal_name or "منظومة ادخار"),
        ("إجمالي المسدّد", f"{total_paid:,.0f} ريال"),
        ("المتبقي",        f"{total_due:,.0f} ريال"),
    ]
    yi = y - 34
    for lbl, val in hak_rows:
        draw_ar(c, M + half + 12, yi, f"{lbl}:", size=8, color=GREY_TXT)
        draw_ar(c, M + half + 90, yi, val,        size=8, color=DARK_GREEN)
        yi -= 14

    y -= BOX_H + 12

    # ── عنوان الجدول ──
    c.setFillColor(MID_GREEN)
    c.roundRect(M, y - 18, W - 2*M, 18, 4, fill=1, stroke=0)
    draw_ar(c, M + 10, y - 13, "سجل الأقساط التفصيلي", size=10, color=GOLD)
    y -= 22

    # ── أعمدة الجدول ──
    COL_X = [M, M+52, M+120, M+200, M+290, M+375]
    HDRS  = ["الدورة/القسط", "المبلغ", "الاستحقاق", "تاريخ السداد", "الحالة", "ملاحظة"]
    ROW_H = 17

    def draw_table_header(cv, y_pos):
        cv.setFillColor(DARK_GREEN)
        cv.rect(M, y_pos - ROW_H, W - 2*M, ROW_H, fill=1, stroke=0)
        for i, h in enumerate(HDRS):
            draw_ar(cv, COL_X[i] + 3, y_pos - 12, h, size=8, color=GOLD)
        return y_pos - ROW_H

    y = draw_table_header(c, y)

    # ── صفوف الجدول ──
    for idx, p in enumerate(payments):
        if y < M + 75:
            c.showPage()
            page_num += 1
            draw_header(c, page_num)
            y = H - 158
            y = draw_table_header(c, y)

        row_color = ROW_EVEN if idx % 2 == 0 else ROW_ALT
        c.setFillColor(row_color)
        c.setStrokeColor(BORDER_CLR)
        c.setLineWidth(0.25)
        c.rect(M, y - ROW_H, W - 2*M, ROW_H, fill=1, stroke=1)

        due_date  = p.due_date.strftime('%Y-%m-%d')  if isinstance(p.due_date,  datetime.datetime) else str(p.due_date  or "—")
        paid_date = p.paid_date.strftime('%Y-%m-%d') if isinstance(p.paid_date, datetime.datetime) else "—"
        status_lbl = "مدفوع ✓" if p.is_paid else "غير مدفوع"
        status_clr = PAID_COLOR if p.is_paid else UNPAID_CLR
        note_short = (p.note or "").split("|")[0].strip()[:28]
        txt_clr    = HexColor("#1a2e1b")

        draw_ar(c, COL_X[0]+3, y-12, f"{p.cycle_number or '-'}/{p.installment_number or '-'}", size=8, color=txt_clr)
        draw_ar(c, COL_X[1]+3, y-12, f"{p.amount or 0:,.0f}", size=8, color=txt_clr)
        draw_ar(c, COL_X[2]+3, y-12, due_date,                size=7, color=txt_clr)
        draw_ar(c, COL_X[3]+3, y-12, paid_date,               size=7, color=txt_clr)
        draw_ar(c, COL_X[4]+3, y-12, status_lbl,              size=8, color=status_clr)
        draw_ar(c, COL_X[5]+3, y-12, note_short,              size=7, color=GREY_TXT)
        y -= ROW_H

    # ── ملخص نهائي ──
    if y < M + 58:
        c.showPage()
        page_num += 1
        draw_header(c, page_num)
        y = H - 160

    y -= 12
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(M, y, W - M, y)
    y -= 6

    c.setFillColor(DARK_GREEN)
    c.roundRect(M, y - 50, W - 2*M, 50, 6, fill=1, stroke=0)

    blk_w = (W - 2*M) / 3
    summary = [
        ("إجمالي الأقساط",  f"{total_all:,.0f} ريال",  white),
        ("إجمالي المسدّد",  f"{total_paid:,.0f} ريال",  HexColor("#69f0ae")),
        ("المتبقي",          f"{total_due:,.0f} ريال",   HexColor("#ff8a80")),
    ]
    for i, (lbl, val, clr) in enumerate(summary):
        bx = M + i * blk_w
        if i > 0:
            c.setStrokeColor(HexColor("#1b5e20"))
            c.setLineWidth(0.4)
            c.line(bx, y - 8, bx, y - 44)
        draw_ar(c, bx + 8, y - 18, lbl, size=8,  color=HexColor("#a5d6a7"))
        draw_ar(c, bx + 8, y - 36, val, size=13, color=clr)

    # ── تذييل الصفحة ──
    c.setFont(font_name, 7)
    c.setFillColor(GREY_TXT)
    c.drawCentredString(W / 2, M + 8,
        reshape_arabic(f"صادر تلقائياً من منظومة {company_name} — {datetime.date.today().strftime('%Y-%m-%d')}"))

    c.save()
    buffer.seek(0)

    filename = f"statement_{sub.subscriber_number or sub.id}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    })

@app.get("/million-hakbah/download-statement")
@app.get("/million-hakbah/download_statement")
async def download_statement_alias(request: Request, db: Session = Depends(get_db)):
    return await download_statement(request, db)

@app.post("/update-profile")
async def update_profile(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    password: str = Form(""),
    db: Session = Depends(get_db)
):
    sub_id = request.session.get("sub_id")
    if not sub_id:
        return JSONResponse(status_code=401, content={"message": "غير مصرح لك"})

    # Ignore submitted name changes and keep the registered name unchanged.
    name = name.strip()
    phone = phone.strip()
    password = password.strip() if password else ""
    if not re.fullmatch(r"\d{9,15}", phone):
        return JSONResponse(status_code=400, content={"message": "أدخل رقم هاتف صالح مكون من 9 إلى 15 رقماً."})
    if password and len(password) < 6:
        return JSONResponse(status_code=400, content={"message": "كلمة المرور يجب أن تكون 6 أحرف على الأقل."})
        
    sub = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.id == sub_id).first()
    if not sub:
        return JSONResponse(status_code=404, content={"message": "المشترك غير موجود"})
        
    # Check if the new phone is used by another subscriber
    if phone != sub.phone:
        existing_phone = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.phone == phone).first()
        if existing_phone:
            return JSONResponse(status_code=400, content={"message": "رقم الهاتف مسجل مسبقاً لمشترك آخر"})
            
    # Update allowed fields only: name, phone and password
    if name:
        sub.name = name
    sub.phone = phone
    
    password_changed = False
    if password and password.strip():
        sub.password = security.hash_password(password)
        password_changed = True
        
    try:
        db.commit()
        if password_changed:
            request.session.clear()
            return JSONResponse(content={"success": True, "message": "تم تحديث البيانات بنجاح. سيتم تسجيل خروجك.", "logout": True})
        return JSONResponse(content={"success": True, "message": "تم تحديث البيانات بنجاح."})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"حدث خطأ أثناء الحفظ: {str(e)}"})

@app.get("/api/check-status")
async def check_subscriber_status(request: Request, db: Session = Depends(get_db)):
    """فحص حالة المشترك الحالي - يستخدمه Polling في صفحة الانتظار"""
    sub_id = request.session.get("sub_id")
    if not sub_id:
        return JSONResponse(status_code=401, content={"status": "unauthenticated"})
    sub = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.id == sub_id).first()
    if not sub:
        return JSONResponse(status_code=404, content={"status": "not_found"})
    return JSONResponse(content={"status": sub.status or "pending", "name": sub.name})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")


if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
