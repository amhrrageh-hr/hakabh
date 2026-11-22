from sqlalchemy import func
from sqlalchemy.orm import Session
import os
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
import datetime
import math
import random
import pandas as pd
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QScrollArea, 
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QDialog, QFormLayout, QAbstractItemView, QMenu,
    QListWidget, QListWidgetItem, QDateEdit, QWidget
)
from PyQt6.QtCore import Qt, QDate, QTimer
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
import database as db_mod
import security
from gui.utils import reshape_text, get_safe_db_url, register_arabic_font, fit_dialog_to_screen, get_available_screen_geometry

class ModernDialog(QDialog):
    def __init__(self, parent, title, message, is_confirm=False, is_input=False, initial_value=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        fit_dialog_to_screen(self, 400)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        
        self.input_field = None
        if is_input:
            self.input_field = QLineEdit()
            self.input_field.setText(initial_value)
            layout.addWidget(self.input_field)
            
        btn_layout = QHBoxLayout()
        if is_confirm or is_input:
            self.btn_ok = QPushButton("تأكيد")
            self.btn_ok.setObjectName("PrimaryBtn")
            self.btn_ok.clicked.connect(self.accept)
            
            self.btn_cancel = QPushButton("إلغاء")
            self.btn_cancel.setObjectName("DangerBtn")
            self.btn_cancel.clicked.connect(self.reject)
            
            btn_layout.addWidget(self.btn_ok)
            btn_layout.addWidget(self.btn_cancel)
        else:
            self.btn_ok = QPushButton("موافق")
            self.btn_ok.setObjectName("PrimaryBtn")
            self.btn_ok.clicked.connect(self.accept)
            btn_layout.addWidget(self.btn_ok)
            
        layout.addLayout(btn_layout)


class SpinnerWidget(QWidget):
    """عنصر مرئي دائري دوار سلس وأنيق للتعبير عن التحميل"""
    def __init__(self, parent=None, size=48, color="#10b981"):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0
        self.color = QColor(color)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._rotate)
        self.timer.start(16) # ~60 FPS

    def _rotate(self):
        self.angle = (self.angle + 8) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect().adjusted(4, 4, -4, -4)
        
        # رسم حلقة الخلفية الباهتة
        bg_pen = QPen(QColor(self.color.red(), self.color.green(), self.color.blue(), 35), 4)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawEllipse(rect)
        
        # رسم القوس المتحرك
        arc_pen = QPen(self.color, 4)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(rect, -self.angle * 16, 110 * 16)
        painter.end()


class LoadingDialog(QDialog):
    """
    نافذة تحميل عصرية خفيفة وصغيرة تظهر أثناء تنفيذ العمليات أو جلب البيانات
    تمنع تجميد الشاشة أو ظهور الشاشة السوداء وتنبيه 'التطبيق لا يستجيب'
    """
    def __init__(self, parent=None, title="جاري تنفيذ العملية", message="يرجى الانتظار، جاري معالجة البيانات..."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        fit_dialog_to_screen(self, 400, 160, fixed_size=True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # بطاقة الحاوية العصرية
        self.card = QFrame(self)
        self.card.setObjectName("LoadingCard")
        self.card.setStyleSheet("""
            QFrame#LoadingCard {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #0f172a);
                border: 1.5px solid #334155;
                border-radius: 16px;
            }
        """)

        # تأثير الظل العصري
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 170))
        shadow.setOffset(0, 8)
        self.card.setGraphicsEffect(shadow)

        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(22, 18, 22, 18)
        card_layout.setSpacing(18)

        # السبينر الدوار
        self.spinner = SpinnerWidget(self.card, size=48, color="#10b981")
        card_layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)

        # النصوص وشريط التقدم
        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: bold; font-family: 'Tajawal';")
        text_layout.addWidget(self.lbl_title)

        self.lbl_message = QLabel(message)
        self.lbl_message.setStyleSheet("color: #94a3b8; font-size: 13px; font-family: 'Tajawal';")
        self.lbl_message.setWordWrap(True)
        text_layout.addWidget(self.lbl_message)

        # شريط تقدم ناعم
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #334155;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #3b82f6);
                border-radius: 2px;
            }
        """)
        text_layout.addWidget(self.progress_bar)

        card_layout.addLayout(text_layout)
        main_layout.addWidget(self.card)

    def set_message(self, message: str, title: str = None):
        if title:
            self.lbl_title.setText(title)
        self.lbl_message.setText(message)
        try:
            self.card.repaint()
        except Exception:
            pass


class BatchProgressDialog(LoadingDialog):
    """نافذة تقدم للعمليات الجماعية تعرض شريط تقدم حقيقي مع النسبة والرسالة"""
    def __init__(self, parent=None, title="جاري تنفيذ العملية", message="يرجى الانتظار...", total_steps=100):
        super().__init__(parent=parent, title=title, message=message)
        self._total = max(1, int(total_steps or 1))
        self.progress_bar.setRange(0, self._total)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)

    def update_progress(self, current_step: int, message: str = None):
        self.progress_bar.setValue(min(self._total, max(0, int(current_step))))
        if message:
            self.lbl_message.setText(message)
        try:
            self.card.repaint()
        except Exception:
            pass


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تسجيل دخول الإدارة")
        fit_dialog_to_screen(self, 420)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.staff = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        title = QLabel("تسجيل دخول الإدارة")
        title.setObjectName("SectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.lbl_error = QLabel("")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setStyleSheet("color: #ef4444; font-size: 13px;")
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)

        layout.addWidget(QLabel("اسم المستخدم أو رقم الموظف:"))
        self.ent_staff_id = QLineEdit()
        self.ent_staff_id.setPlaceholderText("أدخل اسم المستخدم أو رقم الموظف")
        layout.addWidget(self.ent_staff_id)

        layout.addWidget(QLabel("كلمة المرور:"))
        self.ent_password = QLineEdit()
        self.ent_password.setPlaceholderText("أدخل كلمة المرور")
        self.ent_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.ent_password)

        self.btn_login = QPushButton("دخول")
        self.btn_login.setObjectName("PrimaryBtn")
        self.btn_login.clicked.connect(self.on_login)
        layout.addWidget(self.btn_login)

        self.btn_cancel = QPushButton("إلغاء")
        self.btn_cancel.setObjectName("DangerBtn")
        self.btn_cancel.clicked.connect(self.reject)
        layout.addWidget(self.btn_cancel)

    def on_login(self):
        raw_id = self.ent_staff_id.text().strip()
        password = self.ent_password.text()
        if not raw_id or not password:
            return self.show_error("يرجى إدخال اسم المستخدم وكلمة المرور.")

        db = db_mod.SessionLocal()
        try:
            staff = db.query(db_mod.Staff).filter(db_mod.Staff.staff_id_code == raw_id).first()
            if not staff or not security.verify_password(password, staff.password):
                return self.show_error("بيانات الدخول غير صحيحة.")
            self.staff = staff
            self.accept()
        except Exception:
            return self.show_error("حدث خطأ أثناء التحقق من بيانات الدخول.")
        finally:
            db.close()

    def show_error(self, message):
        self.lbl_error.setText(message)
        self.lbl_error.setVisible(True)

class SetupAdminDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إنشاء حساب المدير الأول")
        fit_dialog_to_screen(self, 420, fixed_width=True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.admin_data = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        title = QLabel("إعداد حساب مدير جديد")
        title.setObjectName("SectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.lbl_error = QLabel("")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setStyleSheet("color: #ef4444; font-size: 13px;")
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)

        layout.addWidget(QLabel("اسم المدير:"))
        self.ent_name = QLineEdit()
        self.ent_name.setPlaceholderText("أدخل اسم المدير")
        layout.addWidget(self.ent_name)

        layout.addWidget(QLabel("اسم المستخدم / رقم الموظف:"))
        self.ent_staff_id = QLineEdit()
        self.ent_staff_id.setPlaceholderText("أدخل اسم المستخدم أو رقم الموظف")
        layout.addWidget(self.ent_staff_id)

        layout.addWidget(QLabel("كلمة المرور:"))
        self.ent_password = QLineEdit()
        self.ent_password.setPlaceholderText("أدخل كلمة المرور")
        self.ent_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.ent_password)

        layout.addWidget(QLabel("تأكيد كلمة المرور:"))
        self.ent_password_confirm = QLineEdit()
        self.ent_password_confirm.setPlaceholderText("أعد إدخال كلمة المرور")
        self.ent_password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.ent_password_confirm)

        self.btn_create = QPushButton("إنشاء الحساب")
        self.btn_create.setObjectName("PrimaryBtn")
        self.btn_create.clicked.connect(self.on_create)
        layout.addWidget(self.btn_create)

        self.btn_cancel = QPushButton("إلغاء")
        self.btn_cancel.setObjectName("DangerBtn")
        self.btn_cancel.clicked.connect(self.reject)
        layout.addWidget(self.btn_cancel)

    def on_create(self):
        name = self.ent_name.text().strip()
        staff_id = self.ent_staff_id.text().strip()
        password = self.ent_password.text()
        password_confirm = self.ent_password_confirm.text()

        if not name or not staff_id or not password:
            return self.show_error("يرجى ملء جميع الحقول المطلوبة.")
        if password != password_confirm:
            return self.show_error("كلمة المرور وتأكيدها غير متطابقين.")

        self.admin_data = {
            "name": name,
            "staff_id_code": staff_id,
            "password": password
        }
        self.accept()

    def show_error(self, message):
        self.lbl_error.setText(message)
        self.lbl_error.setVisible(True)

class LuxuryPrizeWheelWidget(QWidget):
    """
    عجلة القرعة الفاخرة عالية الدقة (زمردي ملكي + إطار ذهبي عريض مزخرف بالتروس والفيلجري + مؤشر مرصع بالألماس):
    - مقسمة إلى 50 قطاعاً باللون الأخضر الزمردي الداكن مع خطوط تقسيم ذهبية دقيقة.
    - مرقمة من 1 إلى 49 بأرقام ذهبية، مع ظهور الرقم 49 مرتين في الأعلى تماماً.
    - محاطة بإطار معدني ذهبي عريض ثلاثي الأبعاد يحتوي على تروس دقيقة في حافته الخارجية، وزخارف هندسية كلاسيكية وفيلجري ذهبي.
    - في أعلى المنتصف مؤشر ذهبي فاخر مرصع بالألماس يتحرك فيزيائياً مع مرور القطاعات.
    - قرص مركزي ذهبي مصقول يحمل شعار "M" وكلمة "MILLION" وتحتها نص "هكبة المليون الأسبوعية" بالذهب.
    - خلفية استوديو ناعمة بتدرج أخضر داكن وذهبي مع جزيئات إضاءة Bokeh خافتة.
    """
    def __init__(self, parent=None, size=540, db=None, hub_config=None):
        super().__init__(parent)
        self.display_size = int(size)
        self.wheel_size = 540
        self.setFixedSize(self.display_size, self.display_size)
        self.db = db

        # 50 قطاعاً: الرقم 49 يظهر مرتين في القمة، تليه الأرقام من 1 إلى 48
        self.segments = ["49", "49"] + [str(i) for i in range(1, 49)]
        self.num_segments = len(self.segments)  # 50
        self.seg_angle = 360.0 / self.num_segments  # 7.2 درجة لكل قطاع

        self.wheel_angle = 0.0          # زاوية دوران قرص العجلة بالدرجات
        self.pointer_deflection = 0.0   # زاوية ارتداد المؤشر العلوي المرصع بالألماس
        self.winning_seg_index = -1     # القطاع الفائز لتوهيجه بالذهب عند التوقف
        self.current_sub_number = "---"
        self.is_winner_state = False

        # إعدادات القرص المركزي الذهبي (تُقرأ من الإعدادات أو القيم الممررة)
        self.hub_config = self._load_hub_config(hub_config)

        # جزيئات الإضاءة الخلفية (Bokeh Studio Particles)
        rng = random.Random(49)
        self._bokeh_particles = []
        for _ in range(38):
            bx = rng.uniform(0.04, 0.96)
            by = rng.uniform(0.04, 0.96)
            dist_center = math.hypot(bx - 0.5, by - 0.5)
            if dist_center < 0.36:
                # دفع الجزيئات نحو الهالة المحيطة بالعجلة
                ang = math.atan2(by - 0.5, bx - 0.5)
                bx = 0.5 + math.cos(ang) * rng.uniform(0.38, 0.49)
                by = 0.5 + math.sin(ang) * rng.uniform(0.38, 0.49)
            br = rng.uniform(3.0, 18.0)
            b_alpha = rng.randint(18, 75)
            is_gold = rng.random() > 0.25
            self._bokeh_particles.append((bx, by, br, b_alpha, is_gold))

        self._static_bg_frame_pixmap = None
        self._wheel_disc_pixmap = None
        self._center_hub_pixmap = None
        self._build_cached_layers()

    def _load_hub_config(self, override_cfg=None) -> dict:
        cfg = {
            "mode": "text",  # "text" | "logo_with_text" | "logo_full"
            "logo_path": "",
            "symbol": "M",
            "title": "MILLION",
            "subtitle": "هكبة المليون الأسبوعية",
        }
        try:
            own_session = False
            sess = self.db
            if sess is None:
                sess = db_mod.SessionLocal()
                own_session = True
            try:
                keys = [
                    "wheel_hub_mode",
                    "wheel_hub_logo_path",
                    "wheel_hub_symbol",
                    "wheel_hub_title",
                    "wheel_hub_subtitle",
                    "company_logo_path",
                ]
                rows = sess.query(db_mod.Setting).filter(db_mod.Setting.key.in_(keys)).all()
                s_map = {r.key: (r.value or "") for r in rows}
                if s_map.get("wheel_hub_mode") in ("text", "logo_with_text", "logo_full"):
                    cfg["mode"] = s_map["wheel_hub_mode"]
                logo_p = s_map.get("wheel_hub_logo_path", "").strip()
                if logo_p == "__company_logo__":
                    logo_p = s_map.get("company_logo_path", "").strip()
                cfg["logo_path"] = logo_p
                if "wheel_hub_symbol" in s_map and s_map["wheel_hub_symbol"].strip():
                    cfg["symbol"] = s_map["wheel_hub_symbol"].strip()
                if "wheel_hub_title" in s_map:
                    cfg["title"] = s_map["wheel_hub_title"].strip()
                if "wheel_hub_subtitle" in s_map:
                    cfg["subtitle"] = s_map["wheel_hub_subtitle"].strip()
            finally:
                if own_session:
                    sess.close()
        except Exception:
            pass

        if override_cfg and isinstance(override_cfg, dict):
            cfg.update({k: v for k, v in override_cfg.items() if v is not None})
        return cfg

    def update_hub_config(self, new_cfg: dict):
        self.hub_config = self._load_hub_config(new_cfg)
        self._rebuild_center_hub_pixmap()
        self.update()

    def _make_gold_conical(self, cx, cy, angle_offset=0.0):
        grad = QConicalGradient(QPointF(cx, cy), angle_offset)
        stops = [
            (0.00, QColor("#fef08a")),
            (0.08, QColor("#ca8a04")),
            (0.16, QColor("#713f12")),
            (0.25, QColor("#facc15")),
            (0.34, QColor("#fef9c3")),
            (0.42, QColor("#b45309")),
            (0.50, QColor("#78350f")),
            (0.58, QColor("#eab308")),
            (0.67, QColor("#fef08a")),
            (0.76, QColor("#a16207")),
            (0.85, QColor("#d97706")),
            (0.93, QColor("#fde047")),
            (1.00, QColor("#fef08a")),
        ]
        for pos, col in stops:
            grad.setColorAt(pos, col)
        return grad

    def _build_cached_layers(self):
        dpr = 2.0
        px_size = int(self.wheel_size * dpr)
        cx = self.wheel_size / 2.0
        cy = self.wheel_size / 2.0

        # ═══════════════════════════════════════════════════════════════════
        # 1) الطبقة الثابتة: خلفية الاستوديو + الإطار الذهبي العريض بالتروس والفيلجري
        # ═══════════════════════════════════════════════════════════════════
        bg_pm = QPixmap(px_size, px_size)
        bg_pm.setDevicePixelRatio(dpr)
        bg_pm.fill(Qt.GlobalColor.transparent)

        p = QPainter(bg_pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # أ) خلفية الاستوديو (تدرج زمردي داكن وذهبي ناعم + جزيئات Bokeh)
        studio_grad = QRadialGradient(QPointF(cx, cy), self.wheel_size * 0.52)
        studio_grad.setColorAt(0.00, QColor(212, 175, 55, 55))
        studio_grad.setColorAt(0.55, QColor(6, 58, 34, 210))
        studio_grad.setColorAt(0.82, QColor(3, 28, 16, 245))
        studio_grad.setColorAt(1.00, QColor(2, 13, 8, 255))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(studio_grad))
        p.drawRoundedRect(QRectF(0, 0, self.wheel_size, self.wheel_size), 28, 28)

        # هالة ذهبية خلفية متوهجة خلف الإطار المعدني
        halo_grad = QRadialGradient(QPointF(cx, cy), self.wheel_size * 0.48)
        halo_grad.setColorAt(0.0, QColor(250, 204, 21, 0))
        halo_grad.setColorAt(0.72, QColor(250, 204, 21, 42))
        halo_grad.setColorAt(0.88, QColor(16, 185, 129, 28))
        halo_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(halo_grad))
        p.drawEllipse(QPointF(cx, cy), self.wheel_size * 0.49, self.wheel_size * 0.49)

        # رسم جزيئات الـ Bokeh الخافتة
        for bx, by, br, b_alpha, is_gold in self._bokeh_particles:
            px_x = bx * self.wheel_size
            px_y = by * self.wheel_size
            b_grad = QRadialGradient(QPointF(px_x, px_y), br)
            if is_gold:
                b_grad.setColorAt(0.0, QColor(254, 240, 138, b_alpha))
                b_grad.setColorAt(0.6, QColor(234, 179, 8, int(b_alpha * 0.45)))
                b_grad.setColorAt(1.0, QColor(234, 179, 8, 0))
            else:
                b_grad.setColorAt(0.0, QColor(74, 222, 128, int(b_alpha * 0.7)))
                b_grad.setColorAt(0.6, QColor(16, 185, 129, int(b_alpha * 0.3)))
                b_grad.setColorAt(1.0, QColor(16, 185, 129, 0))
            p.setBrush(QBrush(b_grad))
            p.drawEllipse(QPointF(px_x, px_y), br, br)

        # ب) منظور ثلاثي الأبعاد خفيف (حافة سفلية وظل عميق تحت الإطار المعدني)
        shadow_grad = QRadialGradient(QPointF(cx, cy + 10), self.wheel_size * 0.46)
        shadow_grad.setColorAt(0.75, QColor(0, 0, 0, 195))
        shadow_grad.setColorAt(0.92, QColor(0, 0, 0, 95))
        shadow_grad.setColorAt(1.00, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(shadow_grad))
        p.drawEllipse(QPointF(cx, cy + 10), self.wheel_size * 0.46, self.wheel_size * 0.46)

        # حافة العمق السفلي المعدنية لإعطاء منظور الارتفاع الطفيف (Slightly Elevated Perspective)
        rim_3d_grad = QLinearGradient(cx - 220, cy + 180, cx + 220, cy + 250)
        rim_3d_grad.setColorAt(0.0, QColor("#451a03"))
        rim_3d_grad.setColorAt(0.3, QColor("#92400e"))
        rim_3d_grad.setColorAt(0.5, QColor("#d97706"))
        rim_3d_grad.setColorAt(0.7, QColor("#78350f"))
        rim_3d_grad.setColorAt(1.0, QColor("#451a03"))
        p.setBrush(QBrush(rim_3d_grad))
        p.drawEllipse(QPointF(cx, cy + 5.5), 236, 236)

        # ج) التروس الدقيقة المدمجة في الحافة الخارجية للإطار الذهبي (Fine-Toothed Outer Gears)
        r_gear_outer = 238.0
        r_gear_inner = 229.5
        num_teeth = 96
        gear_path = QPainterPath()
        for i in range(num_teeth):
            a1 = math.radians(i * (360.0 / num_teeth))
            a2 = math.radians((i + 0.28) * (360.0 / num_teeth))
            a3 = math.radians((i + 0.62) * (360.0 / num_teeth))
            a4 = math.radians((i + 0.90) * (360.0 / num_teeth))
            p1 = QPointF(cx + r_gear_inner * math.cos(a1), cy + r_gear_inner * math.sin(a1))
            p2 = QPointF(cx + r_gear_outer * math.cos(a2), cy + r_gear_outer * math.sin(a2))
            p3 = QPointF(cx + r_gear_outer * math.cos(a3), cy + r_gear_outer * math.sin(a3))
            p4 = QPointF(cx + r_gear_inner * math.cos(a4), cy + r_gear_inner * math.sin(a4))
            if i == 0:
                gear_path.moveTo(p1)
            else:
                gear_path.lineTo(p1)
            gear_path.lineTo(p2)
            gear_path.lineTo(p3)
            gear_path.lineTo(p4)
        gear_path.closeSubpath()

        p.setPen(QPen(QColor("#451a03"), 1.2))
        p.setBrush(QBrush(self._make_gold_conical(cx, cy, 25.0)))
        p.drawPath(gear_path)

        # د) الإطار المعدني الذهبي المصقول المقلّص (Slim Polished Gold Frame: R=230 -> R=208 لإعطاء مساحة أكبر للأرقام)
        r_frame_outer = 230.0
        r_frame_inner = 208.0

        # الطبقة الأساسية للإطار الذهبي
        p.setPen(QPen(QColor("#fef08a"), 1.6))
        p.setBrush(QBrush(self._make_gold_conical(cx, cy, 70.0)))
        p.drawEllipse(QPointF(cx, cy), r_frame_outer, r_frame_outer)

        # تدرج دائري لإبراز انحناء المعدن ثلاثي الأبعاد
        bevel_grad = QRadialGradient(QPointF(cx, cy), r_frame_outer)
        bevel_grad.setColorAt(0.89, QColor(69, 26, 3, 180))
        bevel_grad.setColorAt(0.92, QColor(254, 240, 138, 120))
        bevel_grad.setColorAt(0.95, QColor(146, 64, 14, 70))
        bevel_grad.setColorAt(0.97, QColor(254, 249, 195, 135))
        bevel_grad.setColorAt(0.99, QColor(120, 53, 15, 160))
        bevel_grad.setColorAt(1.00, QColor(69, 26, 3, 210))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bevel_grad))
        p.drawEllipse(QPointF(cx, cy), r_frame_outer, r_frame_outer)

        # شريط الزخارف الهندسية الكلاسيكية والفيلجري الذهبي النحيف داخل الإطار (R=225 -> R=213)
        r_band_out = 225.0
        r_band_in = 213.0
        r_band_mid = (r_band_out + r_band_in) / 2.0

        # خلفية غائرة داكنة قليلاً لإبراز نقوش الفيلجري الذهبية البارزة
        recess_grad = QRadialGradient(QPointF(cx, cy), r_band_out)
        recess_grad.setColorAt(0.93, QColor("#3b1704"))
        recess_grad.setColorAt(0.97, QColor("#5c2808"))
        recess_grad.setColorAt(1.00, QColor("#2e1002"))
        band_path = QPainterPath()
        band_path.addEllipse(QPointF(cx, cy), r_band_out, r_band_out)
        inner_cut = QPainterPath()
        inner_cut.addEllipse(QPointF(cx, cy), r_band_in, r_band_in)
        band_path = band_path.subtracted(inner_cut)
        p.setBrush(QBrush(recess_grad))
        p.setPen(QPen(QColor("#facc15"), 1.0))
        p.drawPath(band_path)

        # رسم الزخارف الهندسية الكلاسيكية النحيفة (Slim Geometric Lattice & Gold Filigree)
        num_motifs = 48
        p.save()
        for i in range(num_motifs):
            ang_deg = i * (360.0 / num_motifs)
            ang_rad = math.radians(ang_deg)
            next_rad = math.radians((i + 1) * (360.0 / num_motifs))
            mid_rad = (ang_rad + next_rad) / 2.0

            p_out = QPointF(cx + (r_band_out - 1.2) * math.cos(mid_rad), cy + (r_band_out - 1.2) * math.sin(mid_rad))
            p_in = QPointF(cx + (r_band_in + 1.2) * math.cos(mid_rad), cy + (r_band_in + 1.2) * math.sin(mid_rad))
            p_left = QPointF(cx + r_band_mid * math.cos(ang_rad), cy + r_band_mid * math.sin(ang_rad))
            p_right = QPointF(cx + r_band_mid * math.cos(next_rad), cy + r_band_mid * math.sin(next_rad))

            motif_poly = QPolygonF([p_out, p_right, p_in, p_left])
            p.setPen(QPen(QColor("#fde047"), 0.9))
            p.setBrush(QBrush(QColor(234, 179, 8, 65)))
            p.drawPolygon(motif_poly)

            filigree_pt = QPointF(cx + r_band_mid * math.cos(mid_rad), cy + r_band_mid * math.sin(mid_rad))
            p.setPen(QPen(QColor("#fef08a"), 0.7))
            p.setBrush(QBrush(QColor("#facc15")))
            p.drawEllipse(filigree_pt, 1.5, 1.5)
        p.restore()

        # الحلقات الذهبية الداخلية المحيطة بقرص العجلة مع مسامير ذهبية ناعمة
        p.setPen(QPen(QColor("#fef08a"), 1.6))
        p.setBrush(QBrush(self._make_gold_conical(cx, cy, 140.0)))
        inner_rim_path = QPainterPath()
        inner_rim_path.addEllipse(QPointF(cx, cy), r_band_in, r_band_in)
        wheel_cut = QPainterPath()
        wheel_cut.addEllipse(QPointF(cx, cy), r_frame_inner, r_frame_inner)
        p.drawPath(inner_rim_path.subtracted(wheel_cut))

        # 50 مسماراً ذهبياً ناعماً على الحافة الداخلية للإطار
        r_studs = (r_band_in + r_frame_inner) / 2.0
        for i in range(50):
            s_rad = math.radians(i * (360.0 / 50.0) - 90.0)
            sx = cx + r_studs * math.cos(s_rad)
            sy = cy + r_studs * math.sin(s_rad)
            stud_grad = QRadialGradient(QPointF(sx - 0.5, sy - 0.5), 2.2)
            stud_grad.setColorAt(0.0, QColor("#ffffff"))
            stud_grad.setColorAt(0.5, QColor("#fef08a"))
            stud_grad.setColorAt(1.0, QColor("#78350f"))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(stud_grad))
            p.drawEllipse(QPointF(sx, sy), 1.8, 1.8)

        p.end()
        self._static_bg_frame_pixmap = bg_pm

        # ═══════════════════════════════════════════════════════════════════
        # 2) طبقة قرص العجلة الدوار (50 قطاعاً باللون الزمردي الداكن + أرقام ذهبية 1..49)
        # ═══════════════════════════════════════════════════════════════════
        self._rebuild_wheel_disc_pixmap()

        # ═══════════════════════════════════════════════════════════════════
        # 3) القرص المركزي الذهبي (Central Hub: "M" + "MILLION" + "هكبة المليون الأسبوعية")
        # ═══════════════════════════════════════════════════════════════════
        self._rebuild_center_hub_pixmap()

    def _rebuild_wheel_disc_pixmap(self):
        dpr = 2.0
        px_size = int(self.wheel_size * dpr)
        cx = self.wheel_size / 2.0
        cy = self.wheel_size / 2.0
        r_wheel = 208.0
        r_hub_outer = 74.0

        disc_pm = QPixmap(px_size, px_size)
        disc_pm.setDevicePixelRatio(dpr)
        disc_pm.fill(Qt.GlobalColor.transparent)

        p = QPainter(disc_pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        n_segs = max(1, len(self.segments))
        if n_segs <= 6:
            font_pt = 22
            text_offset = 36.0
        elif n_segs <= 12:
            font_pt = 18
            text_offset = 28.0
        elif n_segs <= 24:
            font_pt = 14
            text_offset = 20.0
        elif n_segs <= 36:
            font_pt = 11
            text_offset = 14.0
        else:
            font_pt = 9
            text_offset = 9.0

        for i, label_num in enumerate(self.segments):
            # زاوية بداية القطاع بالدرجات في نظام الرياضيات (حيث -90 هي الأعلى)
            start_deg_math = -90.0 + (i - 1) * self.seg_angle
            mid_deg_math = start_deg_math + (self.seg_angle / 2.0)

            # تدرج المينا الزمردي الداكن الفاخر (أو توهج ذهبي للقطاع الفائز)
            seg_grad = QRadialGradient(QPointF(cx, cy), r_wheel)
            if i == self.winning_seg_index:
                seg_grad.setColorAt(0.35, QColor("#ca8a04"))
                seg_grad.setColorAt(0.75, QColor("#eab308"))
                seg_grad.setColorAt(0.95, QColor("#fef08a"))
                seg_grad.setColorAt(1.00, QColor("#a16207"))
            else:
                if i % 2 == 0:
                    seg_grad.setColorAt(0.35, QColor("#021f13"))
                    seg_grad.setColorAt(0.72, QColor("#064e3b"))
                    seg_grad.setColorAt(0.92, QColor("#053b2a"))
                    seg_grad.setColorAt(1.00, QColor("#022417"))
                else:
                    seg_grad.setColorAt(0.35, QColor("#01170e"))
                    seg_grad.setColorAt(0.72, QColor("#043927"))
                    seg_grad.setColorAt(0.92, QColor("#032c1e"))
                    seg_grad.setColorAt(1.00, QColor("#011c11"))

            p.setPen(QPen(QColor("#eab308"), 1.3 if n_segs <= 12 else 1.05))
            p.setBrush(QBrush(seg_grad))
            if n_segs == 1:
                p.drawEllipse(QPointF(cx, cy), r_wheel, r_wheel)
            else:
                path = QPainterPath()
                path.moveTo(cx, cy)
                qt_start_deg = -start_deg_math
                qt_sweep_deg = -self.seg_angle
                path.arcTo(
                    QRectF(cx - r_wheel, cy - r_wheel, r_wheel * 2, r_wheel * 2),
                    qt_start_deg,
                    qt_sweep_deg
                )
                path.closeSubpath()
                p.drawPath(path)

            # زخرفة ذهبية داخلية ناعمة في قاعدة كل قطاع قرب المركز
            inner_arc_r = r_hub_outer + 18.0
            rad_mid = math.radians(mid_deg_math)
            dot_x = cx + inner_arc_r * math.cos(rad_mid)
            dot_y = cy + inner_arc_r * math.sin(rad_mid)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(250, 204, 21, 140)))
            p.drawEllipse(QPointF(dot_x, dot_y), 1.6 if n_segs <= 12 else 1.4, 1.6 if n_segs <= 12 else 1.4)

            # كتابة الأرقام الذهبية للمؤهلين بمحاذاة شعاعية واضحة وحجم خط ديناميكي
            p.save()
            p.translate(cx, cy)
            p.rotate(mid_deg_math + 90.0)
            num_font = QFont("Arial", font_pt, QFont.Weight.Black)
            p.setFont(num_font)

            text_rect = QRectF(-34, -r_wheel + text_offset, 68, max(18, font_pt + 10))
            p.setPen(QColor(0, 0, 0, 190))
            p.drawText(text_rect.translated(0.6, 0.8), Qt.AlignmentFlag.AlignCenter, str(label_num))

            if i == self.winning_seg_index:
                p.setPen(QColor("#1e293b"))
            else:
                p.setPen(QColor("#fde047"))
            p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, str(label_num))
            p.restore()

        # حلقة ذهبية رفيعة داخل حافة القطاعات مباشرة
        p.setPen(QPen(QColor(250, 204, 21, 165), 1.1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r_wheel - 24.0, r_wheel - 24.0)
        p.drawEllipse(QPointF(cx, cy), r_hub_outer + 12.0, r_hub_outer + 12.0)

        # ظل داخلي حول حافة الإطار لإعطاء عمق زجاجي/مينا للقرص
        inner_shadow = QRadialGradient(QPointF(cx, cy), r_wheel)
        inner_shadow.setColorAt(0.0, QColor(0, 0, 0, 0))
        inner_shadow.setColorAt(0.88, QColor(0, 0, 0, 0))
        inner_shadow.setColorAt(0.96, QColor(0, 0, 0, 80))
        inner_shadow.setColorAt(1.00, QColor(0, 0, 0, 150))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(inner_shadow))
        p.drawEllipse(QPointF(cx, cy), r_wheel, r_wheel)

        p.end()
        self._wheel_disc_pixmap = disc_pm

    def _rebuild_center_hub_pixmap(self):
        dpr = 2.0
        px_size = int(self.wheel_size * dpr)
        cx = self.wheel_size / 2.0
        cy = self.wheel_size / 2.0
        r_hub_outer = 82.0

        hub_pm = QPixmap(px_size, px_size)
        hub_pm.setDevicePixelRatio(dpr)
        hub_pm.fill(Qt.GlobalColor.transparent)

        p = QPainter(hub_pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # ظل القرص المركزي فوق العجلة
        hub_shadow = QRadialGradient(QPointF(cx, cy + 3), r_hub_outer + 10)
        hub_shadow.setColorAt(0.7, QColor(0, 0, 0, 180))
        hub_shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(hub_shadow))
        p.drawEllipse(QPointF(cx, cy + 3), r_hub_outer + 10, r_hub_outer + 10)

        # الإطار الخارجي للقرص المركزي الذهبي المزخرف
        p.setPen(QPen(QColor("#fef08a"), 2.0))
        p.setBrush(QBrush(self._make_gold_conical(cx, cy, 45.0)))
        p.drawEllipse(QPointF(cx, cy), r_hub_outer, r_hub_outer)

        # فصوص ذهبية صغيرة حول القرص المركزي
        for i in range(28):
            ang = math.radians(i * (360.0 / 28.0))
            gx = cx + (r_hub_outer - 5.0) * math.cos(ang)
            gy = cy + (r_hub_outer - 5.0) * math.sin(ang)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#fef9c3")))
            p.drawEllipse(QPointF(gx, gy), 1.7, 1.7)

        # القرص المعدني الذهبي المصقول في الوسط (Clean Metallic Gold Disc)
        r_disc = r_hub_outer - 10.0
        disc_grad = QRadialGradient(QPointF(cx - 18, cy - 22), r_disc * 1.35)
        disc_grad.setColorAt(0.00, QColor("#fffbeb"))
        disc_grad.setColorAt(0.28, QColor("#fde047"))
        disc_grad.setColorAt(0.62, QColor("#d97706"))
        disc_grad.setColorAt(0.88, QColor("#92400e"))
        disc_grad.setColorAt(1.00, QColor("#5c2808"))
        p.setPen(QPen(QColor("#78350f"), 1.8))
        p.setBrush(QBrush(disc_grad))
        p.drawEllipse(QPointF(cx, cy), r_disc, r_disc)

        # حلقة داخلية محفورة بالذهب
        p.setPen(QPen(QColor("#fef08a"), 1.1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r_disc - 4.5, r_disc - 4.5)

        cfg = getattr(self, "hub_config", None) or {}
        mode = cfg.get("mode", "text")
        logo_path = (cfg.get("logo_path") or "").strip()
        symbol_txt = cfg.get("symbol") or "M"
        title_txt = cfg.get("title") if "title" in cfg else "MILLION"
        subtitle_txt = cfg.get("subtitle") if "subtitle" in cfg else "هكبة المليون الأسبوعية"

        logo_pm = None
        if mode in ("logo_with_text", "logo_full") and logo_path and os.path.exists(logo_path):
            tmp_pm = QPixmap(logo_path)
            if not tmp_pm.isNull():
                logo_pm = tmp_pm

        if mode == "logo_full" and logo_pm is not None:
            # عرض شعار الشركة ملء القرص الذهبي المركزي داخل إطار دائري مصقول
            r_logo = r_disc - 6.5
            p.save()
            clip_path = QPainterPath()
            clip_path.addEllipse(QPointF(cx, cy), r_logo, r_logo)
            p.setClipPath(clip_path)
            scaled_logo = logo_pm.scaled(
                int(r_logo * 2 * dpr),
                int(r_logo * 2 * dpr),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled_logo.setDevicePixelRatio(dpr)
            lw = scaled_logo.width() / dpr
            lh = scaled_logo.height() / dpr
            p.drawPixmap(QPointF(cx - lw / 2.0, cy - lh / 2.0), scaled_logo)
            p.restore()

            p.setPen(QPen(QColor("#fef08a"), 1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r_logo, r_logo)

        elif mode == "logo_with_text" and logo_pm is not None:
            # عرض شعار الشركة داخل ميدالية دائرية مذهبة في النصف العلوي من القرص الذهبي مع النص الفرعي أسفله
            r_small_logo = 26.0
            logo_cy = cy - 31.0
            p.save()
            clip_path = QPainterPath()
            clip_path.addEllipse(QPointF(cx, logo_cy), r_small_logo, r_small_logo)
            p.setClipPath(clip_path)
            scaled_logo = logo_pm.scaled(
                int(r_small_logo * 2 * dpr),
                int(r_small_logo * 2 * dpr),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled_logo.setDevicePixelRatio(dpr)
            lw = scaled_logo.width() / dpr
            lh = scaled_logo.height() / dpr
            p.drawPixmap(QPointF(cx - lw / 2.0, logo_cy - lh / 2.0), scaled_logo)
            p.restore()

            p.setPen(QPen(QColor("#fef08a"), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, logo_cy), r_small_logo, r_small_logo)

            # خط فاصل ذهبي دقيق
            p.setPen(QPen(QColor("#78350f"), 1.0))
            p.drawLine(QPointF(cx - 48, cy - 2), QPointF(cx + 48, cy - 2))

            # النص العربي أسفل الشعار
            if subtitle_txt:
                ar_font = QFont("Tahoma", 8, QFont.Weight.Bold)
                p.setFont(ar_font)
                ar_rect = QRectF(cx - 68, cy + 1, 136, 20)
                p.setPen(QColor("#451a03"))
                p.drawText(ar_rect.translated(0, 1.0), Qt.AlignmentFlag.AlignCenter, subtitle_txt)
                p.setPen(QColor("#fef9c3"))
                p.drawText(ar_rect, Qt.AlignmentFlag.AlignCenter, subtitle_txt)

        else:
            # الوضع الافتراضي (أو النصي المخصص): شعار الحرف الملكي + العنوان + النص الفرعي
            m_font = QFont("Georgia", 25, QFont.Weight.Black)
            p.setFont(m_font)
            m_rect = QRectF(cx - 45, cy - 58, 90, 36)
            p.setPen(QColor(69, 26, 3, 190))
            p.drawText(m_rect.translated(0, 1.5), Qt.AlignmentFlag.AlignCenter, symbol_txt)
            p.setPen(QColor("#451a03"))
            p.drawText(m_rect, Qt.AlignmentFlag.AlignCenter, symbol_txt)

            # لمعة ذهبية فاتحة فوق الرمز
            p.setPen(QColor("#fef9c3"))
            p.drawText(m_rect.translated(-0.6, -0.6), Qt.AlignmentFlag.AlignCenter, symbol_txt)

            # 2. العنوان الرئيسي (MILLION) بالذهب تحت الرمز
            if title_txt:
                mil_font = QFont("Arial", 9, QFont.Weight.Black)
                mil_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.8)
                p.setFont(mil_font)
                mil_rect = QRectF(cx - 64, cy - 22, 128, 18)
                p.setPen(QColor("#451a03"))
                p.drawText(mil_rect.translated(0, 1.0), Qt.AlignmentFlag.AlignCenter, title_txt)
                p.setPen(QColor("#fffbeb"))
                p.drawText(mil_rect, Qt.AlignmentFlag.AlignCenter, title_txt)

            # خط فاصل ذهبي دقيق
            p.setPen(QPen(QColor("#78350f"), 1.0))
            p.drawLine(QPointF(cx - 48, cy - 2), QPointF(cx + 48, cy - 2))

            # 3. النص العربي الفرعي واضح ومقروء بالكامل بالذهب أسفله
            if subtitle_txt:
                ar_font = QFont("Tahoma", 8, QFont.Weight.Bold)
                p.setFont(ar_font)
                ar_rect = QRectF(cx - 68, cy + 1, 136, 20)
                p.setPen(QColor("#451a03"))
                p.drawText(ar_rect.translated(0, 1.0), Qt.AlignmentFlag.AlignCenter, subtitle_txt)
                p.setPen(QColor("#fef9c3"))
                p.drawText(ar_rect, Qt.AlignmentFlag.AlignCenter, subtitle_txt)

        p.end()
        self._center_hub_pixmap = hub_pm

    def _draw_diamond_pointer(self, p: QPainter, cx: float, cy: float):
        """
        رسم المؤشر العلوي الذهبي المرصع بالألماس (Gold & Diamond-Encrusted Pointer)
        في أعلى منتصف الإطار المعدني تماماً.
        """
        p.save()
        # نقطة ارتكاز المؤشر في أعلى الإطار الذهبي المقلّص
        pivot_x = cx
        pivot_y = cy - 230.0
        p.translate(pivot_x, pivot_y)
        p.scale(0.82, 0.82)
        p.rotate(self.pointer_deflection)

        # ظل المؤشر
        p.save()
        p.translate(0, 4.0)
        shadow_path = QPainterPath()
        shadow_path.moveTo(0, 56)
        shadow_path.cubicTo(14, 26, 24, 10, 20, -14)
        shadow_path.cubicTo(10, -26, -10, -26, -20, -14)
        shadow_path.cubicTo(-24, 10, -14, 26, 0, 56)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawPath(shadow_path)
        p.restore()

        # جسم المؤشر الذهبي المنحوت
        ptr_grad = QLinearGradient(-22, -20, 22, 50)
        ptr_grad.setColorAt(0.0, QColor("#fef08a"))
        ptr_grad.setColorAt(0.3, QColor("#eab308"))
        ptr_grad.setColorAt(0.5, QColor("#fffbeb"))
        ptr_grad.setColorAt(0.75, QColor("#b45309"))
        ptr_grad.setColorAt(1.0, QColor("#78350f"))

        ptr_path = QPainterPath()
        ptr_path.moveTo(0, 56)  # رأس المؤشر المدبب يشير إلى الرقم العلوي في العجلة
        ptr_path.cubicTo(12, 28, 24, 12, 20, -12)
        ptr_path.cubicTo(12, -25, -12, -25, -20, -12)
        ptr_path.cubicTo(-24, 12, -12, 28, 0, 56)

        p.setPen(QPen(QColor("#fef9c3"), 1.6))
        p.setBrush(QBrush(ptr_grad))
        p.drawPath(ptr_path)

        # إطار داخلي ذهبي للمؤشر
        inner_ptr = QPainterPath()
        inner_ptr.moveTo(0, 44)
        inner_ptr.lineTo(11, 4)
        inner_ptr.lineTo(0, -14)
        inner_ptr.lineTo(-11, 4)
        inner_ptr.closeSubpath()
        p.setPen(QPen(QColor("#fde047"), 1.0))
        p.setBrush(QBrush(QColor("#92400e")))
        p.drawPath(inner_ptr)

        # ترصيع الألماس اللامع (Diamond Encrustation)
        diamonds = [
            (0, -2, 7.5),     # الجوهرة الماسية المركزية الكبرى
            (0, 14, 4.2),     # ألماسة وسطى
            (0, 26, 3.0),     # ألماسة قرب الحافة المدببة
            (-11, -5, 3.4),   # ألماسة جانبية يسرى
            (11, -5, 3.4),    # ألماسة جانبية يمنى
            (-8, -14, 2.8),   # ألماسة علوية يسرى
            (8, -14, 2.8),    # ألماسة علوية يمنى
            (0, -16, 3.2),    # ألماسة التاج العلوي
        ]
        for dx, dy, dr in diamonds:
            d_grad = QRadialGradient(QPointF(dx - dr * 0.25, dy - dr * 0.25), dr * 1.1)
            d_grad.setColorAt(0.0, QColor("#ffffff"))
            d_grad.setColorAt(0.45, QColor("#e0f2fe"))
            d_grad.setColorAt(0.80, QColor("#7dd3fc"))
            d_grad.setColorAt(1.0, QColor("#0284c7"))
            p.setPen(QPen(QColor("#ffffff"), 0.8))
            p.setBrush(QBrush(d_grad))
            p.drawEllipse(QPointF(dx, dy), dr, dr)

        # بريق نجمي فوق الماسة الرئيسية
        p.setPen(QPen(QColor(255, 255, 255, 230), 1.3))
        p.drawLine(QPointF(-10, -2), QPointF(10, -2))
        p.drawLine(QPointF(0, -12), QPointF(0, 8))

        p.restore()

    def set_Subscriber_Display(self, sub_number: str, is_winner: bool = False):
        self.current_sub_number = str(sub_number or "---")
        self.is_winner_state = is_winner
        self.update()

    def highlight_winner_segment(self, seg_idx: int):
        if self.winning_seg_index != seg_idx:
            self.winning_seg_index = seg_idx
            self._rebuild_wheel_disc_pixmap()
            self.update()

    def target_angle_for_segment(self, seg_idx: int) -> float:
        """
        حساب زاوية الدوران اللازمة ليتوقف القطاع seg_idx في الأعلى تماماً تحت المؤشر.
        بما أن القطاع i مركزه عند: -90 + (i - 0.5) * seg_angle
        فإن زاوية الدوران المطلوبة هي: -(i - 0.5) * seg_angle (موجبة باتجاه عقارب الساعة).
        """
        center_offset = (seg_idx - 0.5) * self.seg_angle
        return (-center_offset) % 360.0

    def set_segments(self, labels):
        """تحديث قطاعات العجلة لتعرض أرقام المؤهلين فقط بشكل ديناميكي."""
        clean = [str(x).strip() for x in (labels or []) if str(x).strip()]
        if not clean:
            clean = ["---"]
        self.segments = clean
        self.num_segments = len(self.segments)
        self.seg_angle = 360.0 / self.num_segments
        self.winning_seg_index = -1
        self._rebuild_wheel_disc_pixmap()
        self.update()

    def segment_index_for_subscriber(self, sub_number: str) -> int:
        """إرجاع فهرس قطاع المشترك المطابق مباشرة داخل العجلة (أو الاحتياطي 1..49 في المعاينة)."""
        target = str(sub_number or "").strip()
        if target in self.segments:
            return self.segments.index(target)
        digits = "".join(ch for ch in target if ch.isdigit())
        if digits and digits in self.segments:
            return self.segments.index(digits)
        if digits:
            num_val = ((int(digits) - 1) % max(1, self.num_segments))
            return num_val
        return 0

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scale = self.display_size / float(self.wheel_size)
        if abs(scale - 1.0) > 1e-4:
            p.scale(scale, scale)

        cx = self.wheel_size / 2.0
        cy = self.wheel_size / 2.0

        # 1. خلفية الاستوديو والإطار الذهبي العريض الثابت
        if self._static_bg_frame_pixmap:
            p.drawPixmap(0, 0, self._static_bg_frame_pixmap)

        # 2. قرص العجلة الزمردي الدوار
        if self._wheel_disc_pixmap:
            p.save()
            p.translate(cx, cy)
            p.rotate(self.wheel_angle)
            p.translate(-cx, -cy)
            p.drawPixmap(0, 0, self._wheel_disc_pixmap)
            p.restore()

        # 3. القرص المركزي الذهبي الثابت (يحمل شعار M و MILLION وهكبة المليون الأسبوعية)
        if self._center_hub_pixmap:
            p.drawPixmap(0, 0, self._center_hub_pixmap)

        # شارة رقم المشترك أسفل القرص المركزي مباشرة داخل العجلة
        if self.current_sub_number and self.current_sub_number != "---":
            badge_w = 136.0
            badge_h = 26.0
            badge_rect = QRectF(cx - badge_w / 2.0, cy + 31.0, badge_w, badge_h)
            badge_bg = QLinearGradient(badge_rect.topLeft(), badge_rect.bottomRight())
            if self.is_winner_state:
                badge_bg.setColorAt(0.0, QColor("#fef08a"))
                badge_bg.setColorAt(0.5, QColor("#facc15"))
                badge_bg.setColorAt(1.0, QColor("#ca8a04"))
                p.setPen(QPen(QColor("#ffffff"), 1.5))
                txt_col = QColor("#052e16")
            else:
                badge_bg.setColorAt(0.0, QColor(2, 44, 34, 235))
                badge_bg.setColorAt(1.0, QColor(6, 78, 59, 235))
                p.setPen(QPen(QColor("#facc15"), 1.3))
                txt_col = QColor("#fef08a")

            p.setBrush(QBrush(badge_bg))
            p.drawRoundedRect(badge_rect, 13, 13)

            sub_font = QFont("Arial", 11, QFont.Weight.Black)
            p.setFont(sub_font)
            p.setPen(txt_col)
            p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"#{self.current_sub_number}")

        # 4. المؤشر العلوي الذهبي المرصع بالألماس
        self._draw_diamond_pointer(p, cx, cy)
        p.end()


class WheelPreviewDialog(QDialog):
    """نافذة معاينة وتجربة حية لعجلة القرعة والقرص الذهبي المركزي من شاشة الإعدادات."""
    def __init__(self, parent=None, db=None, hub_config=None):
        super().__init__(parent)
        self.setWindowTitle("معاينة عجلة القرعة والقرص المركزي الذهبي")
        avail = get_available_screen_geometry(self)
        avail_h = avail.height() if avail else 768
        avail_w = avail.width() if avail else 1024
        wheel_sz = min(520, max(240, min(int(avail_h * 0.90) - 140, int(avail_w * 0.90) - 80)))
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setStyleSheet("""
            QDialog {
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.85, fx:0.5, fy:0.5,
                    stop:0 #06351d, stop:0.6 #031c0f, stop:1 #010b06);
                color: white;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(10)

        title = QLabel("🎡 معاينة عجلة القرعة والقرص الذهبي المركزي")
        title.setStyleSheet("font-size: 18px; font-weight: 900; color: #fde047; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        self.wheel = LuxuryPrizeWheelWidget(self, size=wheel_sz, db=db, hub_config=hub_config)
        lay.addWidget(self.wheel, 0, Qt.AlignmentFlag.AlignCenter)

        btn_row = QHBoxLayout()
        btn_spin = QPushButton("🎲 تجربة تدوير العجلة")
        btn_spin.setObjectName("PrimaryBtn")
        btn_spin.setFixedHeight(42)
        btn_spin.clicked.connect(self.start_demo_spin)

        btn_close = QPushButton("إغلاق المعاينة")
        btn_close.setObjectName("DangerBtn")
        btn_close.setFixedHeight(42)
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_spin)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)

        fit_dialog_to_screen(self, wheel_sz + 100, wheel_sz + 145)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step_demo)
        self._t0 = 0.0
        self._dur = 3.2
        self._start_ang = 0.0
        self._target_ang = 0.0
        self._last_seg = -1
        self._win_idx = 0

    def start_demo_spin(self):
        self.wheel.highlight_winner_segment(-1)
        self._win_idx = random.randint(0, self.wheel.num_segments - 1)
        target_mod = self.wheel.target_angle_for_segment(self._win_idx)
        self._start_ang = self.wheel.wheel_angle % 360.0
        delta = (target_mod - self._start_ang) % 360.0
        self._target_ang = self._start_ang + 360.0 * 5 + delta
        self._t0 = datetime.datetime.now().timestamp()
        self._last_seg = -1
        self._timer.setInterval(16)
        self._timer.start()

    def _step_demo(self):
        elapsed = datetime.datetime.now().timestamp() - self._t0
        p = min(1.0, max(0.0, elapsed / self._dur))
        eased = 1.0 - pow(1.0 - p, 4)
        cur = self._start_ang + (self._target_ang - self._start_ang) * eased
        self.wheel.wheel_angle = cur
        seg_under = int(((-cur) % 360.0) / self.wheel.seg_angle)
        if seg_under != self._last_seg and p < 0.985:
            self._last_seg = seg_under
            self.wheel.pointer_deflection = -13.0 * min(1.0, (1.0 - eased) * 2.2 + 0.15)
            self.wheel.set_Subscriber_Display(f"00{self.wheel.segments[seg_under]}", is_winner=False)
        else:
            self.wheel.pointer_deflection *= 0.72
        self.wheel.update()
        if p >= 1.0:
            self._timer.stop()
            self.wheel.pointer_deflection = 0.0
            self.wheel.highlight_winner_segment(self._win_idx)
            self.wheel.set_Subscriber_Display(f"00{self.wheel.segments[self._win_idx]}", is_winner=True)


class DrawAnimationDialog(QDialog):
    def __init__(self, parent, qualified_by_category, draw_name, db, category_reports=None):
        super().__init__(parent)
        self.setWindowTitle(f"{draw_name} — تقارير الفئات والقرعة")
        avail = get_available_screen_geometry(self)
        avail_w = avail.width() if avail else 1024
        avail_h = avail.height() if avail else 768
        self.setMinimumSize(min(680, max(360, avail_w - 40)), min(520, max(320, avail_h - 40)))
        fit_dialog_to_screen(self, 1020, 800)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setStyleSheet("""
            QDialog {
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.85, fx:0.5, fy:0.5,
                    stop:0 #06351d, stop:0.6 #031c0f, stop:1 #010b06);
                color: white;
            }
        """)
        self.db = db
        self.draw_name = draw_name
        self.qualified_by_category = dict(qualified_by_category or {})
        self.category_reports = dict(category_reports or {})

        if self.category_reports and "الجائزة الكبرى" not in self.draw_name:
            self.categories = list(self.category_reports.keys())
        else:
            self.categories = list(self.qualified_by_category.keys())

        self.current_cat_index = 0
        self.winners = []  # list of (cat_name, winner_sub, cycle_num)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 14, 20, 16)
        self.layout.setSpacing(10)

        self.stage_stack = QStackedWidget(self)
        self.layout.addWidget(self.stage_stack)

        # الصفحة 0: تقرير الفئة قبل القرعة
        self.page_pre_report = QWidget()
        self.pre_report_layout = QVBoxLayout(self.page_pre_report)
        self.pre_report_layout.setContentsMargins(6, 4, 6, 4)
        self.pre_report_layout.setSpacing(10)
        self.stage_stack.addWidget(self.page_pre_report)

        # الصفحة 1: عجلة القرعة الفاخرة للفئة الحالية
        self.page_wheel = QWidget()
        self.wheel_page_layout = QVBoxLayout(self.page_wheel)
        self.wheel_page_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        is_compact_wheel = avail_h < 760
        self.wheel_page_layout.setContentsMargins(8, 4, 8, 4)
        self.wheel_page_layout.setSpacing(5 if is_compact_wheel else 8)

        self.cat_label = QLabel("")
        self.cat_label.setStyleSheet(
            f"font-size: {19 if is_compact_wheel else 24}px; color: #fde047; font-weight: 900; background: transparent;"
        )
        self.cat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wheel_page_layout.addWidget(self.cat_label)

        max_wheel_h = int(avail_h * 0.92) - (205 if is_compact_wheel else 240)
        max_wheel_w = int(avail_w * 0.92) - 80
        wheel_sz = min(500, max(240, min(max_wheel_h, max_wheel_w)))
        self.wheel_widget = LuxuryPrizeWheelWidget(self, size=wheel_sz, db=self.db)
        self.wheel_page_layout.addWidget(self.wheel_widget, 0, Qt.AlignmentFlag.AlignCenter)

        self.wheel_label = QLabel("---")
        self.wheel_label.setFixedHeight(36 if is_compact_wheel else 44)
        self.wheel_label.setMinimumWidth(min(420, max(240, avail_w - 120)))
        self.wheel_label.setStyleSheet(f"""
            font-size: {20 if is_compact_wheel else 25}px;
            font-weight: 900;
            color: #fef08a;
            background-color: rgba(4, 47, 29, 0.85);
            border: 2px solid #eab308;
            border-radius: 12px;
            padding: 3px 16px;
        """)
        self.wheel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wheel_page_layout.addWidget(self.wheel_label, 0, Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("استعد للسحب...")
        self.status_label.setStyleSheet(f"font-size: {14 if is_compact_wheel else 18}px; color: #a7f3d0; font-weight: bold; background: transparent;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wheel_page_layout.addWidget(self.status_label)

        self.btn_next_after_wheel = QPushButton("الانتقال للفئة التالية ⬅️")
        self.btn_next_after_wheel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next_after_wheel.setFixedHeight(38 if is_compact_wheel else 44)
        self.btn_next_after_wheel.setMinimumWidth(min(340, max(220, avail_w - 140)))
        self.btn_next_after_wheel.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #eab308, stop:0.5 #facc15, stop:1 #ca8a04);
                color: #052e16;
                font-size: {14 if is_compact_wheel else 16}px;
                font-weight: 900;
                border-radius: 12px;
                border: 2px solid #fef08a;
                padding: 6px 20px;
            }}
            QPushButton:hover {{
                background: #fde047;
            }}
        """)
        self.btn_next_after_wheel.clicked.connect(self.next_category)
        self.btn_next_after_wheel.hide()
        self.wheel_page_layout.addWidget(self.btn_next_after_wheel, 0, Qt.AlignmentFlag.AlignCenter)

        self.stage_stack.addWidget(self.page_wheel)

        # الصفحة 2: التقرير النهائي للفائزين من كل فئة ورقم الدورة
        self.page_final_report = QWidget()
        self.final_report_layout = QVBoxLayout(self.page_final_report)
        self.final_report_layout.setContentsMargins(10, 6, 10, 6)
        self.final_report_layout.setSpacing(12)
        self.stage_stack.addWidget(self.page_final_report)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_wheel)
        self._spin_start_time = 0.0
        self._spin_duration = 4.6
        self._start_angle = 0.0
        self._target_angle = 0.0
        self._last_tick_seg = -1
        self._selected_winner = None
        self._current_target_cycle = 1

        self.start_category_draw()

    def _clear_layout(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _get_category_report_lists(self, cat_name):
        """إرجاع (رقم الدورة، قائمة المؤهلين، قائمة الفائزين سابقاً، قائمة المستبعدين في الدورة) للفئة المحددة."""
        info = self.category_reports.get(cat_name, {})
        is_incentive = ("تحفيزية" in self.draw_name or "التحفيزية" in self.draw_name)

        target_cycle = info.get("target_cycle")
        if not target_cycle:
            parent_win = self.parent()
            if parent_win and hasattr(parent_win, "category_selected_cycles"):
                sel_c = parent_win.category_selected_cycles.get(cat_name, "auto")
                if sel_c != "auto" and isinstance(sel_c, int):
                    target_cycle = sel_c
        if not target_cycle:
            target_cycle = 1

        if info:
            if is_incentive:
                q_entries = info.get("incentive_qualified_entries", [])
                p_entries = info.get("incentive_previous_winners_entries", [])
                x_entries = info.get("incentive_excluded_entries", [])
            else:
                q_entries = info.get("weekly_qualified_entries", [])
                p_entries = info.get("weekly_previous_winners_entries", [])
                x_entries = info.get("weekly_excluded_entries", [])
        else:
            subs = self.qualified_by_category.get(cat_name, [])
            q_entries = [
                {"id": s.id, "number": s.subscriber_number or "-", "name": s.name or "-"}
                for s in subs
            ]
            p_entries = []
            x_entries = []

        return target_cycle, q_entries, p_entries, x_entries

    def _on_report_cycle_changed(self, cat_name, new_cycle_data):
        """عند تغيير رقم الدورة من داخل شاشة تقرير الفئة قبل القرعة، يتم إعادة حساب التقرير فوراً."""
        try:
            from gui.pages.draw import compute_category_draw_analytics
            parent_win = self.parent()
            sel_map = {}
            if parent_win and hasattr(parent_win, "category_selected_cycles"):
                parent_win.category_selected_cycles[cat_name] = new_cycle_data
                sel_map = dict(parent_win.category_selected_cycles)
            else:
                sel_map = {cat_name: new_cycle_data}

            new_analytics = compute_category_draw_analytics(self.db, selected_cycles=sel_map)
            if cat_name in new_analytics:
                self.category_reports[cat_name] = new_analytics[cat_name]
                c_info = new_analytics[cat_name]
                is_inc = ("تحفيزية" in self.draw_name or "التحفيزية" in self.draw_name)
                q_ids = c_info.get("incentive_qualified_ids" if is_inc else "weekly_qualified_ids", [])
                subs_objs = (
                    self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.id.in_(q_ids)).all()
                    if q_ids
                    else []
                )
                sub_map = {s.id: s for s in subs_objs}
                self.qualified_by_category[cat_name] = [sub_map[sid] for sid in q_ids if sid in sub_map]
            self.show_category_pre_draw_report()
        except Exception as e:
            print("Error updating category cycle report:", e)

    def start_category_draw(self):
        """يبدأ بعرض تقرير الفئة الحالية قبل إجراء القرعة لها."""
        if self.current_cat_index >= len(self.categories):
            self.show_final_report()
            return
        self.show_category_pre_draw_report()

    def show_category_pre_draw_report(self):
        """بناء وعرض تقرير الفئة الحالية (رقم الدورة، أرقام المؤهلين، أرقام الفائزين سابقاً، وأرقام الذين خرجوا من القرعة)."""
        self._clear_layout(self.pre_report_layout)
        cat_name = self.categories[self.current_cat_index]
        info = self.category_reports.get(cat_name, {})
        target_cycle, q_entries, p_entries, x_entries = self._get_category_report_lists(cat_name)
        self._current_target_cycle = target_cycle

        # حساب كثافة التقرير وحجم الشاشة لضبط حجم الخط وعدد الأعمدة تلقائياً حتى تظهر كافة البيانات دون الحاجة للتمرير
        avail = get_available_screen_geometry(self)
        avail_w = avail.width() if avail else 1280
        avail_h = avail.height() if avail else 760
        total_items = len(q_entries) + len(p_entries) + len(x_entries)
        is_small_screen = (avail_h < 760) or (avail_w < 1200)

        if total_items > 90:
            chip_font, detail_font, hdr_font = 9, 8, 11
            chip_pad, grid_spacing, card_pad = "1px 4px", 3, 6
            cols_cnt = 10 if avail_w < 1200 else 12
            compact_label = True
            top_title_font, sum_val_font, sum_lbl_font = 15, 14, 10
        elif total_items > 45:
            chip_font, detail_font, hdr_font = 10, 9, 12
            chip_pad, grid_spacing, card_pad = "2px 5px", 4, 7
            cols_cnt = 8 if avail_w < 1200 else 10
            compact_label = True
            top_title_font, sum_val_font, sum_lbl_font = 16, 15, 10
        elif total_items > 20 or is_small_screen:
            chip_font, detail_font, hdr_font = 11, 10, 12
            chip_pad, grid_spacing, card_pad = "3px 6px", 5, 8
            cols_cnt = 6 if avail_w < 1200 else 8
            compact_label = True
            top_title_font, sum_val_font, sum_lbl_font = 17, 16, 11
        else:
            chip_font, detail_font, hdr_font = 13, 11, 14
            chip_pad, grid_spacing, card_pad = "4px 8px", 6, 10
            cols_cnt = 5 if avail_w < 1200 else 6
            compact_label = False
            top_title_font, sum_val_font, sum_lbl_font = 19, 18, 11

        # 1. الشريط العلوي لتقرير الفئة
        top_card = QFrame()
        top_card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #064e3b, stop:0.5 #047857, stop:1 #064e3b);
                border: 2px solid #eab308;
                border-radius: 12px;
                padding: {6 if compact_label else 8}px 12px;
            }}
        """)
        top_lay = QHBoxLayout(top_card)
        top_lay.setSpacing(10)
        top_lay.setContentsMargins(6, 4, 6, 4)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        step_lbl = QLabel(
            f"📌 الفئة ({self.current_cat_index + 1} من {len(self.categories)}) — {self.draw_name}"
        )
        step_lbl.setStyleSheet(f"font-size: {11 if compact_label else 12}px; color: #a7f3d0; font-weight: bold; border: none; background: transparent;")
        main_title = QLabel(f"📋 تقرير فئة: {cat_name}  |  الدورة التي سوف تُقرع: (الدورة رقم {target_cycle})")
        main_title.setWordWrap(True)
        main_title.setStyleSheet(f"font-size: {top_title_font}px; color: #fde047; font-weight: 900; border: none; background: transparent;")
        title_vbox.addWidget(step_lbl)
        title_vbox.addWidget(main_title)
        top_lay.addLayout(title_vbox, 1)

        # قائمة منسدلة لتغيير الدورة مباشرة من التقرير عند الحاجة
        if info:
            cycle_box_lay = QHBoxLayout()
            lbl_ch = QLabel("تغيير الدورة:")
            lbl_ch.setStyleSheet("font-size: 12px; color: #fef08a; font-weight: bold; border: none; background: transparent;")
            combo_c = QComboBox()
            combo_c.setMinimumWidth(145)
            combo_c.setFixedHeight(32)
            combo_c.setStyleSheet("""
                QComboBox {
                    background-color: #022c22;
                    color: #fef08a;
                    border: 1px solid #eab308;
                    border-radius: 8px;
                    padding: 3px 8px;
                    font-size: 12px;
                    font-weight: bold;
                }
            """)
            auto_c = info.get("auto_cycle", target_cycle)
            total_c = info.get("total_cycles", max(target_cycle, auto_c))
            combo_c.addItem(f"تلقائي (دورة {auto_c})", "auto")
            for c_i in range(1, total_c + 1):
                tag = " (مكتملة)" if c_i == auto_c else ""
                combo_c.addItem(f"الدورة {c_i}{tag}", c_i)

            parent_win = self.parent()
            cur_sel = "auto"
            if parent_win and hasattr(parent_win, "category_selected_cycles"):
                cur_sel = parent_win.category_selected_cycles.get(cat_name, "auto")
            if cur_sel == "auto" or cur_sel is None:
                combo_c.setCurrentIndex(0)
            else:
                idx_f = combo_c.findData(cur_sel)
                combo_c.setCurrentIndex(idx_f if idx_f >= 0 else 0)

            combo_c.currentIndexChanged.connect(
                lambda: self._on_report_cycle_changed(cat_name, combo_c.currentData())
            )
            cycle_box_lay.addWidget(lbl_ch)
            cycle_box_lay.addWidget(combo_c)
            top_lay.addLayout(cycle_box_lay)

        self.pre_report_layout.addWidget(top_card)

        # 2. بطاقات الملخص الرقمية الأربع
        summary_row = QHBoxLayout()
        summary_row.setSpacing(8)
        summary_items = [
            ("🎯 رقم الدورة المقررة", f"الدورة {target_cycle}", "#38bdf8", "#0c4a6e"),
            ("🟢 المؤهلون في هذه الدورة", f"{len(q_entries)} مشترك", "#4ade80", "#064e3b"),
            ("🏆 فازوا في دورات سابقة", f"{len(p_entries)} مشترك", "#facc15", "#422006"),
            ("🚫 خرجوا من قرعة الدورة", f"{len(x_entries)} مشترك", "#f87171", "#450a0a"),
        ]
        for s_title, s_val, fg_col, bg_col in summary_items:
            s_card = QFrame()
            s_card.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_col};
                    border: 1px solid {fg_col};
                    border-radius: 9px;
                    padding: {4 if compact_label else 6}px 8px;
                }}
            """)
            s_v = QVBoxLayout(s_card)
            s_v.setSpacing(1)
            s_v.setContentsMargins(4, 3, 4, 3)
            l1 = QLabel(s_title)
            l1.setWordWrap(True)
            l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l1.setStyleSheet(f"font-size: {sum_lbl_font}px; color: #e2e8f0; font-weight: bold; border: none; background: transparent;")
            l2 = QLabel(s_val)
            l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l2.setStyleSheet(f"font-size: {sum_val_font}px; color: {fg_col}; font-weight: 900; border: none; background: transparent;")
            s_v.addWidget(l1)
            s_v.addWidget(l2)
            summary_row.addWidget(s_card)

        self.pre_report_layout.addLayout(summary_row)

        # 3. منطقة التفاصيل للأقسام الثلاثة (المؤهلون | الفائزون سابقاً | الذين خرجوا من القرعة)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll_con = QWidget()
        scroll_con.setStyleSheet("background: transparent;")
        sections_lay = QVBoxLayout(scroll_con)
        sections_lay.setContentsMargins(0, 0, 0, 0)
        sections_lay.setSpacing(6 if compact_label else 10)

        def _build_section_card(sec_title, sec_subtitle, border_col, header_bg, badge_bg, badge_fg, items_text_list, empty_msg):
            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(15, 23, 42, 0.85);
                    border: 1.5px solid {border_col};
                    border-radius: 10px;
                }}
            """)
            flay = QVBoxLayout(frame)
            flay.setContentsMargins(card_pad, card_pad, card_pad, card_pad)
            flay.setSpacing(4 if compact_label else 6)

            hdr = QFrame()
            hdr.setStyleSheet(f"background-color: {header_bg}; border-radius: 7px; border: none; padding: 3px 8px;")
            h_l = QHBoxLayout(hdr)
            h_l.setContentsMargins(6, 2, 6, 2)
            t_lbl = QLabel(sec_title)
            t_lbl.setWordWrap(True)
            t_lbl.setStyleSheet(f"font-size: {hdr_font}px; font-weight: 900; color: {badge_fg}; border: none; background: transparent;")
            h_l.addWidget(t_lbl, 1)
            flay.addWidget(hdr)

            if not items_text_list:
                emp = QLabel(empty_msg)
                emp.setWordWrap(True)
                emp.setStyleSheet(f"font-size: {chip_font}px; color: #94a3b8; padding: 3px 8px; border: none; background: transparent;")
                flay.addWidget(emp)
            else:
                # عرض أرقام المشتركين في شبكة متجاوبة تتقلص خطوطها تلقائياً مع زيادة العدد لإظهار كافة البيانات بوضوح
                grid_w = QWidget()
                grid_w.setStyleSheet("background: transparent; border: none;")
                g_lay = QGridLayout(grid_w)
                g_lay.setContentsMargins(2, 2, 2, 2)
                g_lay.setSpacing(grid_spacing)
                for idx_item, (num_txt, detail_txt) in enumerate(items_text_list):
                    chip = QFrame()
                    chip.setStyleSheet(f"""
                        QFrame {{
                            background-color: {badge_bg};
                            border: 1px solid {border_col};
                            border-radius: 6px;
                            padding: {chip_pad};
                        }}
                    """)
                    c_lay = QHBoxLayout(chip)
                    c_lay.setContentsMargins(4, 2, 4, 2)
                    c_lay.setSpacing(4)

                    lbl_str = f"#{num_txt}" if compact_label else f"رقم: {num_txt}"
                    n_lbl = QLabel(lbl_str)
                    n_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    n_lbl.setStyleSheet(f"font-size: {chip_font}px; font-weight: 900; color: {badge_fg}; border: none; background: transparent;")
                    c_lay.addWidget(n_lbl)
                    if detail_txt:
                        d_lbl = QLabel(detail_txt)
                        d_lbl.setStyleSheet(f"font-size: {detail_font}px; color: #e2e8f0; font-weight: bold; border: none; background: transparent;")
                        c_lay.addWidget(d_lbl)
                    g_lay.addWidget(chip, idx_item // cols_cnt, idx_item % cols_cnt)
                for c_k in range(cols_cnt):
                    g_lay.setColumnStretch(c_k, 1)
                flay.addWidget(grid_w)

            return frame

        # أ) قسم المؤهلين في هذه الدورة (أرقام المشتركين فقط)
        q_formatted = [(e["number"], "") for e in q_entries]
        q_numbers_summary = " ، ".join(e["number"] for e in q_entries) if q_entries else "لا يوجد"
        sections_lay.addWidget(
            _build_section_card(
                f"🟢 أولاً: أرقام المؤهلين للدخول في قرعة الدورة ({target_cycle}) — العدد: ({len(q_entries)})",
                f"الأرقام: {q_numbers_summary[:95]}{'...' if len(q_numbers_summary) > 95 else ''}",
                "#22c55e",
                "rgba(22, 163, 74, 0.25)",
                "rgba(6, 78, 59, 0.75)",
                "#4ade80",
                q_formatted,
                "لا يوجد مشتركون مؤهلون في هذه الدورة حالياً.",
            )
        )

        # ب) قسم الفائزين في الدورات السابقة (رقم المشترك ورقم الدورة فقط)
        p_formatted = [(e["number"], f"({e.get('won_cycle', 'دورة سابقة')})") for e in p_entries]
        p_numbers_summary = " ، ".join(f"{e['number']} ({e.get('won_cycle', '')})" for e in p_entries) if p_entries else "لا يوجد"
        sections_lay.addWidget(
            _build_section_card(
                f"🏆 ثانياً: أرقام الذين قد فازوا في الدورات السابقة — العدد: ({len(p_entries)})",
                f"الأرقام: {p_numbers_summary[:95]}{'...' if len(p_numbers_summary) > 95 else ''}",
                "#eab308",
                "rgba(202, 138, 4, 0.25)",
                "rgba(66, 32, 6, 0.75)",
                "#fde047",
                p_formatted,
                "لا يوجد فائزون سابقون مستبعدون في هذه الفئة.",
            )
        )

        # ج) قسم الذين خرجوا من القرعة في هذه الدورة (أرقام المشتركين فقط)
        x_formatted = [(e["number"], f"(دورة {target_cycle})") for e in x_entries]
        x_numbers_summary = " ، ".join(e["number"] for e in x_entries) if x_entries else "لا يوجد"
        sections_lay.addWidget(
            _build_section_card(
                f"🚫 ثالثاً: أرقام الذين خرجوا من القرعة في هذه الدورة ({target_cycle}) — العدد: ({len(x_entries)})",
                f"الأرقام: {x_numbers_summary[:95]}{'...' if len(x_numbers_summary) > 95 else ''}",
                "#ef4444",
                "rgba(220, 38, 38, 0.25)",
                "rgba(69, 10, 10, 0.75)",
                "#fca5a5",
                x_formatted,
                "لم يخرج أي مشترك من القرعة في هذه الدورة (الجميع ملتزمون ومؤهلون).",
            )
        )

        sections_lay.addStretch()
        scroll.setWidget(scroll_con)
        self.pre_report_layout.addWidget(scroll, 1)

        # 4. أزرار التحكم أسفل التقرير
        actions_row = QHBoxLayout()
        actions_row.setSpacing(14)

        subs_for_wheel = self.qualified_by_category.get(cat_name, [])
        has_next_cat = (self.current_cat_index + 1) < len(self.categories)
        next_cat_label = self.categories[self.current_cat_index + 1] if has_next_cat else ""

        if subs_for_wheel:
            btn_spin = QPushButton(
                f"🎡 ابدأ القرعة وتدوير العجلة لفئة ({cat_name}) — الدورة ({target_cycle})  [{len(subs_for_wheel)} مؤهل]"
            )
            btn_spin.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_spin.setFixedHeight(50)
            btn_spin.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #16a34a, stop:0.5 #22c55e, stop:1 #15803d);
                    color: white;
                    font-size: 17px;
                    font-weight: 900;
                    border-radius: 12px;
                    border: 2px solid #fde047;
                    padding: 8px 26px;
                }
                QPushButton:hover {
                    background: #15803d;
                }
            """)
            btn_spin.clicked.connect(self.begin_wheel_spin_for_current_category)
            actions_row.addWidget(btn_spin, 2)

        btn_skip_txt = (
            f"تخطي ({cat_name}) والانتقال إلى تقرير ({next_cat_label}) ⬅️"
            if has_next_cat
            else "تخطي الفئة وعرض التقرير النهائي للفائزين ⬅️"
        )
        btn_skip = QPushButton(btn_skip_txt)
        btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_skip.setFixedHeight(50)
        btn_skip.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #fef08a;
                font-size: 14px;
                font-weight: bold;
                border-radius: 12px;
                border: 1px solid #eab308;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        btn_skip.clicked.connect(self.next_category)
        actions_row.addWidget(btn_skip, 1)

        btn_cancel = QPushButton("إغلاق")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setFixedHeight(50)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 12px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #991b1b;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        actions_row.addWidget(btn_cancel)

        self.pre_report_layout.addLayout(actions_row)
        self.stage_stack.setCurrentWidget(self.page_pre_report)

    def begin_wheel_spin_for_current_category(self):
        """الانتقال من شاشة تقرير الفئة إلى شاشة عجلة القرعة وبدء التدوير للفئة الحالية."""
        cat_name = self.categories[self.current_cat_index]
        subs = self.qualified_by_category.get(cat_name, [])
        if not subs:
            self.next_category()
            return

        self.stage_stack.setCurrentWidget(self.page_wheel)
        self.btn_next_after_wheel.hide()

        # تعبئة العجلة بأرقام المؤهلين فقط والاختيار العشوائي منهم مباشرة
        qual_numbers = [str(s.subscriber_number or f"#{s.id}").strip() for s in subs]
        self.wheel_widget.set_segments(qual_numbers)

        winner_idx = random.randrange(len(subs))
        self._selected_winner = subs[winner_idx]
        self._win_seg_idx = winner_idx

        target_cycle = self._current_target_cycle or 1
        self.cat_label.setText(
            f"✨ {self.draw_name} — قرعة فئة: {cat_name} (الدورة رقم {target_cycle}) ✨"
        )
        self.status_label.setText(f"جاري تدوير عجلة القرعة بين ({len(subs)}) مشتركين مؤهلين...")
        self.wheel_label.setStyleSheet("""
            font-size: 26px;
            font-weight: 900;
            color: #fef08a;
            background-color: rgba(4, 47, 29, 0.85);
            border: 2px solid #eab308;
            border-radius: 14px;
            padding: 4px 20px;
        """)

        self.wheel_widget.highlight_winner_segment(-1)
        self.wheel_widget.set_Subscriber_Display("---", is_winner=False)

        base_target_mod = self.wheel_widget.target_angle_for_segment(winner_idx)

        self._start_angle = self.wheel_widget.wheel_angle % 360.0
        self.wheel_widget.wheel_angle = self._start_angle
        extra_rotations = random.randint(6, 8) * 360.0
        delta = (base_target_mod - self._start_angle) % 360.0
        self._target_angle = self._start_angle + extra_rotations + delta

        self._spin_start_time = datetime.datetime.now().timestamp()
        self._last_tick_seg = -1
        self.timer.setInterval(16)
        self.timer.start()

    def update_wheel(self):
        now = datetime.datetime.now().timestamp()
        elapsed = now - self._spin_start_time
        progress = min(1.0, max(0.0, elapsed / self._spin_duration))

        eased = 1.0 - pow(1.0 - progress, 4)
        current_angle = self._start_angle + (self._target_angle - self._start_angle) * eased
        self.wheel_widget.wheel_angle = current_angle

        seg_under_ptr = (int(((-current_angle) % 360.0) / self.wheel_widget.seg_angle) + 1) % self.wheel_widget.num_segments
        speed_factor = max(0.0, 1.0 - eased)
        if seg_under_ptr != self._last_tick_seg and progress < 0.985:
            self._last_tick_seg = seg_under_ptr
            self.wheel_widget.pointer_deflection = -14.0 * min(1.0, speed_factor * 2.4 + 0.18)
            shown_num = self.wheel_widget.segments[seg_under_ptr]
            self.wheel_label.setText(f"رقم المشترك: {shown_num}  |  الدورة رقم ({self._current_target_cycle})")
            self.wheel_widget.set_Subscriber_Display(shown_num, is_winner=False)
        else:
            self.wheel_widget.pointer_deflection *= 0.72

        self.wheel_widget.update()

        if progress >= 1.0:
            self.timer.stop()
            self.wheel_widget.wheel_angle = self._target_angle % 360.0
            self.wheel_widget.pointer_deflection = 0.0
            self.wheel_widget.highlight_winner_segment(self._win_seg_idx)
            self.conclude_category_draw(self._selected_winner)

    def conclude_category_draw(self, winner_sub):
        cat_name = self.categories[self.current_cat_index]

        # تحديد رقم الدورة التي أُجريت لها القرعة بدقة
        cycle_num = self._current_target_cycle
        if not cycle_num:
            parent_win = self.parent()
            sub_cat_name = getattr(winner_sub, "category", None) or cat_name
            if parent_win:
                sel_map = getattr(parent_win, "category_selected_cycles", {}) or {}
                sel_c = sel_map.get(sub_cat_name, "auto")
                if sel_c != "auto" and isinstance(sel_c, int):
                    cycle_num = sel_c
                else:
                    stats_cache = getattr(parent_win, "_draw_stats_cache", {}) or {}
                    c_info = stats_cache.get(sub_cat_name)
                    if isinstance(c_info, dict) and c_info.get("target_cycle"):
                        cycle_num = c_info.get("target_cycle")

        if not cycle_num:
            active_p = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == winner_sub.id,
                db_mod.Payment.due_date <= datetime.datetime.now()
            ).order_by(db_mod.Payment.due_date.desc()).first()
            cycle_num = active_p.cycle_number if active_p else 1

        self.winners.append((cat_name, winner_sub, cycle_num))

        self.wheel_widget.set_Subscriber_Display(winner_sub.subscriber_number, is_winner=True)
        self.wheel_label.setStyleSheet("""
            font-size: 28px;
            font-weight: 900;
            color: #052e16;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #fde047, stop:0.5 #facc15, stop:1 #eab308);
            border: 3px solid #ffffff;
            border-radius: 14px;
            padding: 4px 24px;
        """)
        self.wheel_label.setText(
            f"🏆 رقم المشترك الفائز: ({winner_sub.subscriber_number})  |  الدورة رقم ({cycle_num})"
        )
        self.status_label.setText(
            f"🎉 مبروك للفائز في ({cat_name}) — الدورة رقم ({cycle_num}): رقم المشترك ({winner_sub.subscriber_number})"
        )

        w_season_id = getattr(winner_sub, 'season_id', None)
        if not w_season_id and self.parent() and hasattr(self.parent(), 'combo_header_season'):
            w_season_id = self.parent().combo_header_season.currentData()

        if "الجائزة الكبرى" in self.draw_name:
            saved_draw_type = self.draw_name
        else:
            saved_draw_type = f"{self.draw_name} - {cat_name}"

        new_w = db_mod.Winner(
            subscriber_number=winner_sub.subscriber_number,
            draw_type=saved_draw_type,
            draw_date=datetime.datetime.now(),
            cycle_number=cycle_num,
            season_id=w_season_id
        )
        self.db.add(new_w)
        self.db.commit()

        # استبعاد الفائز المختار من الجولات التالية في نفس السحب
        for k_cat, k_list in self.qualified_by_category.items():
            self.qualified_by_category[k_cat] = [s for s in k_list if s.id != winner_sub.id]

        has_next = (self.current_cat_index + 1) < len(self.categories)
        if has_next:
            next_cat = self.categories[self.current_cat_index + 1]
            self.btn_next_after_wheel.setText(f"📋 الانتقال إلى تقرير الفئة التالية ({next_cat}) ⬅️")
        else:
            self.btn_next_after_wheel.setText("🏆 عرض التقرير النهائي للفائزين من كل فئة ⬅️")
        self.btn_next_after_wheel.show()

    def next_category(self):
        self.current_cat_index += 1
        self.start_category_draw()

    def show_final_report(self):
        """عرض التقرير النهائي الشامل للفائزين من كل فئة (رقم الدورة ورقم المشترك فقط بدون الأسماء أو الهواتف)."""
        self._clear_layout(self.final_report_layout)

        avail = get_available_screen_geometry(self)
        avail_h = avail.height() if avail else 760
        is_compact = (len(self.winners) > 5) or (avail_h < 760)
        title_sz = 20 if is_compact else 25
        card_font = 14 if is_compact else 17
        win_num_font = 16 if is_compact else 20
        card_pad = "8px 14px" if is_compact else "12px 20px"

        title = QLabel(f"🏆 التقرير النهائي للفائزين — {self.draw_name}")
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size: {title_sz}px; color: #fde047; font-weight: 900; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.final_report_layout.addWidget(title)

        sub_title = QLabel("بيان الفائزين من كل فئة (رقم الدورة ورقم المشترك فقط)")
        sub_title.setStyleSheet("font-size: 13px; color: #a7f3d0; font-weight: bold; margin-bottom: 4px; background: transparent;")
        sub_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.final_report_layout.addWidget(sub_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8 if is_compact else 12)

        if not self.winners:
            empty_lbl = QLabel("لم يتم تسجيل أي فائز في هذه الجولة.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("font-size: 16px; color: #cbd5e1; padding: 24px;")
            scroll_layout.addWidget(empty_lbl)
        else:
            for idx_w, item_w in enumerate(self.winners, start=1):
                if len(item_w) == 3:
                    cat, sub, cycle_num = item_w
                else:
                    cat, sub = item_w
                    cycle_num = 1

                card = QFrame()
                card.setStyleSheet(f"""
                    QFrame {{
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #064e3b, stop:0.5 #022c22, stop:1 #0f172a);
                        border-radius: 12px;
                        border: 2px solid #eab308;
                        margin: 2px 8px;
                        padding: {card_pad};
                    }}
                """)
                card_lay = QHBoxLayout(card)
                card_lay.setSpacing(14)

                cat_lbl = QLabel(f"📊 الفئة ({idx_w}): {cat}")
                cat_lbl.setWordWrap(True)
                cat_lbl.setStyleSheet(f"font-size: {card_font}px; color: #fde047; font-weight: 900; border: none; background: transparent;")

                cycle_lbl = QLabel(f"🔄 الدورة رقم ({cycle_num})")
                cycle_lbl.setWordWrap(True)
                cycle_lbl.setStyleSheet(f"font-size: {card_font}px; color: #38bdf8; font-weight: 900; border: none; background: transparent;")

                sub_num_lbl = QLabel(f"🏆 الفائز: #{sub.subscriber_number}")
                sub_num_lbl.setWordWrap(True)
                sub_num_lbl.setStyleSheet(f"font-size: {win_num_font}px; color: #4ade80; font-weight: 900; border: none; background: transparent;")

                card_lay.addWidget(cat_lbl, 1)
                card_lay.addWidget(cycle_lbl, 1)
                card_lay.addWidget(sub_num_lbl, 1)

                scroll_layout.addWidget(card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        self.final_report_layout.addWidget(scroll, 1)

        btns_row = QHBoxLayout()
        btns_row.setSpacing(15)
        btns_row.addStretch()

        if self.winners or self.category_reports:
            btn_export = QPushButton("📊 تصدير تقرير القرعة والفائزين (Excel)")
            btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_export.setFixedHeight(48)
            btn_export.setMinimumWidth(260)
            btn_export.setStyleSheet("""
                QPushButton {
                    background-color: #eab308;
                    color: #052e16;
                    font-size: 15px;
                    font-weight: 900;
                    border-radius: 10px;
                    padding: 8px 20px;
                }
                QPushButton:hover {
                    background-color: #fde047;
                }
            """)
            btn_export.clicked.connect(self.export_full_draw_session_excel)
            btns_row.addWidget(btn_export)

        btn_close = QPushButton("إغلاق والعودة للسجل ✅")
        btn_close.setObjectName("PrimaryBtn")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setFixedWidth(260)
        btn_close.setFixedHeight(48)
        btn_close.clicked.connect(self.accept)
        btns_row.addWidget(btn_close)
        btns_row.addStretch()

        self.final_report_layout.addLayout(btns_row)
        self.stage_stack.setCurrentWidget(self.page_final_report)

    def export_full_draw_session_excel(self):
        """تصدير التقرير النهائي للفائزين وتقارير الفئات التفصيلية إلى ملف Excel (رقم الدورة ورقم المشترك فقط)."""
        try:
            winners_rows = []
            for item_w in self.winners:
                cat, sub, cycle_num = item_w if len(item_w) == 3 else (item_w[0], item_w[1], 1)
                winners_rows.append({
                    "الفئة المالية": cat,
                    "رقم الدورة التي فاز فيها": cycle_num,
                    "رقم المشترك الفائز": sub.subscriber_number or "-",
                    "نوع السحب": self.draw_name,
                    "تاريخ السحب": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                })

            details_rows = []
            for cat_name in self.categories:
                t_cycle, q_list, p_list, x_list = self._get_category_report_lists(cat_name)
                for e in q_list:
                    details_rows.append({
                        "الفئة": cat_name,
                        "رقم الدورة": t_cycle,
                        "رقم المشترك": e.get("number", "-"),
                        "الحالة في القرعة": "مؤهل في هذه الدورة",
                    })
                for e in p_list:
                    details_rows.append({
                        "الفئة": cat_name,
                        "رقم الدورة": e.get("won_cycle", f"دورة سابقة"),
                        "رقم المشترك": e.get("number", "-"),
                        "الحالة في القرعة": "فاز في دورة سابقة",
                    })
                for e in x_list:
                    details_rows.append({
                        "الفئة": cat_name,
                        "رقم الدورة": t_cycle,
                        "رقم المشترك": e.get("number", "-"),
                        "الحالة في القرعة": "خرج من القرعة في هذه الدورة",
                    })

            default_name = f"draw_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير القرعة والفائزين", default_name, "Excel Files (*.xlsx)")
            if not file_path:
                return

            with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
                df_w = pd.DataFrame(winners_rows) if winners_rows else pd.DataFrame([{"ملاحظة": "لا يوجد فائزون"}])
                df_w.to_excel(writer, index=False, sheet_name="الفائزون من كل فئة")
                writer.sheets["الفائزون من كل فئة"].right_to_left()

                if details_rows:
                    df_d = pd.DataFrame(details_rows)
                    df_d.to_excel(writer, index=False, sheet_name="تقارير الفئات قبل القرعة")
                    writer.sheets["تقارير الفئات قبل القرعة"].right_to_left()

            ModernDialog(self, "نجاح", f"تم تصدير تقرير القرعة والفائزين بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {e}").exec()

class SubscriberEditDialog(QDialog):
    def __init__(self, parent, sub):
        super().__init__(parent)
        self.setWindowTitle("تعديل بيانات المشترك")
        fit_dialog_to_screen(self, 450, fixed_width=True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        self.sub = sub
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        title = QLabel("تعديل بيانات المشترك")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        
        self.ent_name = QLineEdit()
        self.ent_name.setText(sub.name or "")
        layout.addWidget(QLabel("الاسم الكامل:"))
        layout.addWidget(self.ent_name)
        
        self.ent_phone = QLineEdit()
        self.ent_phone.setText(sub.phone or "")
        layout.addWidget(QLabel("رقم الهاتف:"))
        layout.addWidget(self.ent_phone)
        
        self.ent_acc = QLineEdit()
        self.ent_acc.setText(sub.subscriber_number or "")
        layout.addWidget(QLabel("رقم الحساب:"))
        layout.addWidget(self.ent_acc)
        
        self.ent_pwd = QLineEdit()
        self.ent_pwd.setPlaceholderText("اتركها فارغة لعدم التغيير")
        layout.addWidget(QLabel("كلمة السر الجديدة:"))
        layout.addWidget(self.ent_pwd)
        
        self.btn_save = QPushButton("حفظ التغييرات")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.clicked.connect(self.accept)
        layout.addWidget(self.btn_save)

class SeasonDialog(QDialog):
    def __init__(self, parent=None, season=None):
        super().__init__(parent)
        self.setWindowTitle("تعديل الموسم" if season else "إضافة موسم جديد")
        fit_dialog_to_screen(self, 460, fixed_width=True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.season = season

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(14)

        title = QLabel("بيانات الموسم")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e3a8a;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.ent_name = QLineEdit(season.name if season else "")
        self.ent_name.setPlaceholderText("مثال: الموسم الثاني 2026")
        form.addRow("اسم الموسم:", self.ent_name)

        self.ent_number = QLineEdit(str(season.season_number) if season and season.season_number else "1")
        form.addRow("رقم الموسم التسلسلي:", self.ent_number)

        self.ent_code = QLineEdit(season.code if season and season.code else "")
        self.ent_code.setPlaceholderText("مثال: S2")
        form.addRow("رمز الموسم (اختياري):", self.ent_code)

        self.combo_status = QComboBox()
        self.combo_status.addItem("نشط (Active)", "active")
        self.combo_status.addItem("قريباً / تسجيل مبكر (Upcoming)", "upcoming")
        self.combo_status.addItem("مكتمل (Completed)", "completed")
        self.combo_status.addItem("مؤرشف (Archived)", "archived")
        if season:
            idx = self.combo_status.findData(season.status)
            if idx >= 0:
                self.combo_status.setCurrentIndex(idx)
        form.addRow("حالة الموسم:", self.combo_status)

        self.chk_current = QCheckBox("تعيين كموسم نشط حالي للنظام")
        self.chk_current.setChecked(season.is_current if season else True)
        form.addRow("", self.chk_current)

        self.dt_start = QDateEdit()
        self.dt_start.setCalendarPopup(True)
        self.dt_start.setDisplayFormat("yyyy-MM-dd")
        if season and season.start_date:
            self.dt_start.setDate(QDate(season.start_date.year, season.start_date.month, season.start_date.day))
        else:
            self.dt_start.setDate(QDate.currentDate())
        form.addRow("تاريخ بدء الموسم:", self.dt_start)

        self.dt_end = QDateEdit()
        self.dt_end.setCalendarPopup(True)
        self.dt_end.setDisplayFormat("yyyy-MM-dd")
        if season and season.end_date:
            self.dt_end.setDate(QDate(season.end_date.year, season.end_date.month, season.end_date.day))
        else:
            self.dt_end.setDate(QDate.currentDate().addMonths(10))
        form.addRow("تاريخ الانتهاء المتوقع:", self.dt_end)

        self.ent_desc = QTextEdit(season.description if season and season.description else "")
        self.ent_desc.setFixedHeight(60)
        self.ent_desc.setPlaceholderText("ملاحظات أو وصف خاص بهذا الموسم...")
        form.addRow("وصف الموسم:", self.ent_desc)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        self.btn_save = QPushButton("حفظ الموسم")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.setFixedHeight(38)
        self.btn_save.clicked.connect(self.validate_and_accept)

        self.btn_cancel = QPushButton("إلغاء")
        self.btn_cancel.setObjectName("DangerBtn")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(self.btn_save)
        btn_box.addWidget(self.btn_cancel)
        layout.addLayout(btn_box)

    def validate_and_accept(self):
        name = self.ent_name.text().strip()
        if not name:
            QMessageBox.warning(self, "تنبيه", "يرجى كتابة اسم الموسم.")
            return
        self.accept()

class CategoryEditDialog(QDialog):
    def __init__(self, parent, cat):
        super().__init__(parent)
        self.setWindowTitle("تعديل بيانات الفئة")
        fit_dialog_to_screen(self, 400, fixed_width=True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        self.cat = cat
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        title = QLabel("تعديل بيانات الفئة")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        
        self.ent_name = QLineEdit()
        self.ent_name.setText(cat.name or "")
        layout.addWidget(QLabel("اسم الفئة:"))
        layout.addWidget(self.ent_name)
        
        self.ent_amount = QLineEdit()
        self.ent_amount.setText(str(cat.amount) if cat.amount else "0")
        layout.addWidget(QLabel("المبلغ اليومي:"))
        layout.addWidget(self.ent_amount)
        
        self.ent_prize = QLineEdit()
        prize = getattr(cat, 'prize_amount', 0.0)
        self.ent_prize.setText(str(prize) if prize else "0")
        layout.addWidget(QLabel("مبلغ الجائزة:"))
        layout.addWidget(self.ent_prize)

        self.combo_season = QComboBox()
        if hasattr(parent, 'db') and parent.db:
            seasons = db_mod.get_all_seasons(parent.db)
            for s in seasons:
                self.combo_season.addItem(s.name, s.id)
            if getattr(cat, 'season_id', None):
                idx = self.combo_season.findData(cat.season_id)
                if idx >= 0:
                    self.combo_season.setCurrentIndex(idx)
        layout.addWidget(QLabel("الموسم التابع له:"))
        layout.addWidget(self.combo_season)
        
        self.btn_save = QPushButton("حفظ التغييرات")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.clicked.connect(self.accept)
        layout.addWidget(self.btn_save)

class CreateGroupBatchDialog(QDialog):
    def __init__(self, parent, cat=None):
        super().__init__(parent)
        self.setWindowTitle("فتح مجموعة / دفعة جديدة للفئة")
        fit_dialog_to_screen(self, 460, fixed_width=True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        self.cat = cat
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(14)
        
        title = QLabel("إنشاء مجموعة / دفعة جديدة")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e3a8a;")
        layout.addWidget(title)
        
        form = QFormLayout()
        form.setSpacing(10)

        # Season
        self.combo_season = QComboBox()
        if hasattr(parent, 'db') and parent.db:
            seasons = db_mod.get_all_seasons(parent.db)
            for s in seasons:
                self.combo_season.addItem(s.name, s.id)
            if cat and getattr(cat, 'season_id', None):
                idx = self.combo_season.findData(cat.season_id)
                if idx >= 0:
                    self.combo_season.setCurrentIndex(idx)
        form.addRow("الموسم التابع له:", self.combo_season)
        
        # Name
        default_name = f"{cat.name} - المجموعة 2" if cat else "فئة جديدة - المجموعة 1"
        self.ent_name = QLineEdit(default_name)
        form.addRow("اسم المجموعة الجديدة:", self.ent_name)
        
        # Daily amount & prize
        self.ent_amount = QLineEdit(str(cat.amount) if cat and cat.amount else "1000")
        self.ent_prize = QLineEdit(str(getattr(cat, 'prize_amount', 0.0)) if cat else "0")
        form.addRow("المبلغ اليومي (القسط):", self.ent_amount)
        form.addRow("مبلغ الجائزة:", self.ent_prize)
        
        # Cycles & Installments
        self.ent_cycles = QLineEdit(str(getattr(cat, 'max_cycles', 10)) if cat else "10")
        self.ent_inst = QLineEdit(str(getattr(cat, 'max_installments', 12)) if cat else "12")
        form.addRow("عدد الدورات:", self.ent_cycles)
        form.addRow("أقساط الدورة:", self.ent_inst)
        
        # Start date
        self.dt_start = QDateEdit()
        self.dt_start.setCalendarPopup(True)
        self.dt_start.setDisplayFormat("yyyy-MM-dd")
        self.dt_start.setDate(QDate.currentDate())
        form.addRow("تاريخ بدء المجموعة:", self.dt_start)
        
        # Numbers Generation Info
        divider = QLabel("<b>توليد أرقام المشتركين للمجموعة:</b>")
        divider.setStyleSheet("color: #0f766e; margin-top: 8px;")
        layout.addLayout(form)
        layout.addWidget(divider)
        
        num_form = QFormLayout()
        num_form.setSpacing(8)
        self.ent_prefix = QLineEdit("G2-")
        self.ent_num_start = QLineEdit("1")
        self.ent_num_end = QLineEdit("100")
        num_form.addRow("بادئة الأرقام (Prefix):", self.ent_prefix)
        num_form.addRow("من رقم:", self.ent_num_start)
        num_form.addRow("إلى رقم (السعة):", self.ent_num_end)
        layout.addLayout(num_form)
        
        btn_box = QHBoxLayout()
        self.btn_create = QPushButton("إنشاء وتوليد الأرقام")
        self.btn_create.setObjectName("PrimaryBtn")
        self.btn_create.setFixedHeight(38)
        self.btn_create.clicked.connect(self.validate_and_accept)
        
        self.btn_cancel = QPushButton("إلغاء")
        self.btn_cancel.setObjectName("DangerBtn")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_box.addWidget(self.btn_create)
        btn_box.addWidget(self.btn_cancel)
        layout.addLayout(btn_box)

    def validate_and_accept(self):
        name = self.ent_name.text().strip()
        if not name:
            QMessageBox.warning(self, "تنبيه", "يرجى كتابة اسم المجموعة.")
            return
        try:
            float(self.ent_amount.text().strip())
            float(self.ent_prize.text().strip())
            int(self.ent_num_start.text().strip())
            int(self.ent_num_end.text().strip())
        except ValueError:
            QMessageBox.warning(self, "تنبيه", "يرجى التأكد من إدخال قيم رقمية صحيحة للمبالغ والأرقام.")
            return
        self.accept()

class ExcludeSubscriberDialog(QDialog):
    def __init__(self, parent, subscriber):
        super().__init__(parent)
        self.setWindowTitle("استبعاد مشترك")
        fit_dialog_to_screen(self, 440, fixed_width=True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        self.subscriber = subscriber
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(14)
        
        title = QLabel(f"استبعاد المشترك: {subscriber.name}")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #b91c1c;")
        layout.addWidget(title)
        
        info_lbl = QLabel(f"رقم الحساب: <b>{subscriber.subscriber_number or '-'}</b> | الفئة: <b>{subscriber.category or '-'}</b>")
        info_lbl.setStyleSheet("color: #475569; font-size: 13px;")
        layout.addWidget(info_lbl)
        
        form = QFormLayout()
        form.setSpacing(10)
        
        self.reason_combo = QComboBox()
        self.reason_combo.addItems([
            "تأخر متكرر وتعثر في سداد الأقساط",
            "قرار إداري مباشر",
            "مخالفة الشروط والأحكام",
            "بناءً على طلب المشترك (انسحاب)",
            "سبب آخر"
        ])
        form.addRow("سبب الاستبعاد:", self.reason_combo)
        
        self.ent_notes = QLineEdit()
        self.ent_notes.setPlaceholderText("تفاصيل أو ملاحظات إضافية (اختياري)...")
        form.addRow("ملاحظات إضافية:", self.ent_notes)
        layout.addLayout(form)
        
        warn_lbl = QLabel("⚠️ سيتم نقل المشترك إلى قائمة المستبعدين وإيقاف مشاركته في السحوبات والعمليات النشطة.")
        warn_lbl.setWordWrap(True)
        warn_lbl.setStyleSheet("color: #991b1b; font-size: 12px; background: #fee2e2; padding: 8px; border-radius: 6px;")
        layout.addWidget(warn_lbl)
        
        btn_box = QHBoxLayout()
        self.btn_confirm = QPushButton("تأكيد الاستبعاد")
        self.btn_confirm.setObjectName("DangerBtn")
        self.btn_confirm.setFixedHeight(36)
        self.btn_confirm.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("إلغاء")
        self.btn_cancel.setObjectName("PrimaryBtn")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_box.addWidget(self.btn_confirm)
        btn_box.addWidget(self.btn_cancel)
        layout.addLayout(btn_box)

    def get_reason(self):
        main_reason = self.reason_combo.currentText()
        notes = self.ent_notes.text().strip()
        if notes:
            return f"{main_reason} ({notes})"
        return main_reason

class PaymentReceiptDialog(QDialog):
    def __init__(self, parent, payment_id, db):
        super().__init__(parent)
        self.payment_id = payment_id
        self.db = db
        p = db.get(db_mod.Payment, payment_id)
        sub = db.get(db_mod.Subscriber, p.subscriber_id) if p else None

        self.setWindowTitle("سند القسط")
        fit_dialog_to_screen(self, 450, fixed_width=True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setStyleSheet("background-color: #f1f5f9;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        if not p:
            layout.addWidget(QLabel("بيانات القسط غير متوفرة"))
            return

        # Container to look like a printed receipt
        receipt_frame = QFrame()
        receipt_frame.setObjectName("ReceiptFrame")
        receipt_frame.setStyleSheet("""
            QFrame#ReceiptFrame {
                background-color: white;
                border: 2px dashed #94a3b8;
                border-radius: 12px;
            }
        """)
        
        # Add shadow
        shadow = QGraphicsDropShadowEffect(receipt_frame)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 20))
        receipt_frame.setGraphicsEffect(shadow)

        r_layout = QVBoxLayout(receipt_frame)
        r_layout.setContentsMargins(25, 25, 25, 25)
        r_layout.setSpacing(15)

        # Header
        header_lay = QHBoxLayout()
        logo_lbl = QLabel("🧾")
        logo_lbl.setFont(QFont("Segoe UI Emoji", 24))
        header_lay.addWidget(logo_lbl)
        
        title = QLabel("سند قسط")
        title.setFont(QFont("Tajawal", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #0f172a;")
        header_lay.addStretch()
        header_lay.addWidget(title)
        header_lay.addStretch()
        r_layout.addLayout(header_lay)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #e2e8f0;")
        r_layout.addWidget(sep1)

        # Amount Prominent Display
        amount_lay = QVBoxLayout()
        amount_lbl = QLabel(f"{p.amount:,.2f} ر.ي")
        amount_lbl.setFont(QFont("Tajawal", 26, QFont.Weight.Bold))
        amount_lbl.setStyleSheet("color: #16a34a;")
        amount_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        status_lbl = QLabel("تم الدفع بنجاح ✓" if p.is_paid else "غير مدفوع ✗")
        status_lbl.setFont(QFont("Tajawal", 12, QFont.Weight.Bold))
        status_lbl.setStyleSheet("color: #16a34a;" if p.is_paid else "color: #dc2626;")
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        amount_lay.addWidget(amount_lbl)
        amount_lay.addWidget(status_lbl)
        r_layout.addLayout(amount_lay)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #e2e8f0;")
        r_layout.addWidget(sep2)

        # Details Grid
        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.setHorizontalSpacing(20)
        
        def add_row(r, label, value):
            lbl = QLabel(label)
            lbl.setFont(QFont("Tajawal", 11))
            lbl.setStyleSheet("color: #64748b;")
            val = QLabel(str(value))
            val.setFont(QFont("Tajawal", 12, QFont.Weight.Bold))
            val.setStyleSheet("color: #1e293b;")
            grid.addWidget(lbl, r, 0)
            grid.addWidget(val, r, 1)

        add_row(0, "رقم السند:", f"#{p.id}")
        add_row(1, "رقم المشترك:", sub.subscriber_number if sub else "-")
        add_row(2, "اسم المشترك:", sub.name if sub else "-")
        add_row(3, "رقم الهاتف:", sub.phone if sub else "-")
        
        add_row(4, "تاريخ تسديد القسط المستحق:", p.due_date.strftime('%Y-%m-%d') if p.due_date else '-')
        add_row(5, "تاريخ تسديد القسط الفعلي:", p.paid_date.strftime('%Y-%m-%d %H:%M') if p.paid_date else '-')
        add_row(6, "القسط / الدورة:", f"{p.installment_number} / {p.cycle_number}")
        
        if p.note:
            add_row(6, "الملاحظة:", p.note)

        r_layout.addLayout(grid)
        layout.addWidget(receipt_frame)

        # Print Button
        btn_print = QPushButton("طباعة / حفظ PDF")
        btn_print.setFixedHeight(45)
        btn_print.setFont(QFont("Tajawal", 12, QFont.Weight.Bold))
        btn_print.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; color: white; border-radius: 8px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        btn_print.clicked.connect(lambda: self.save_receipt_pdf(p, sub))
        layout.addWidget(btn_print)

    def save_receipt_pdf(self, p, sub):
        try:
            filename, _ = QFileDialog.getSaveFileName(self, "حفظ سند القسط (PDF)", f"receipt_{sub.subscriber_number}_{p.id}.pdf", "PDF Files (*.pdf)")
            if not filename: return
            
            c = canvas.Canvas(filename, pagesize=(A4[0], A4[1]/2)) # Half A4 page for receipt
            width, height = A4[0], A4[1]/2
            
            try:
                font_path = "C:/Windows/Fonts/arial.ttf"
                pdfmetrics.registerFont(TTFont('ArabicFont', font_path))
                font_name = 'ArabicFont'
            except:
                font_name = 'Helvetica'
                
            # Draw Background
            c.setFillColorRGB(0.97, 0.98, 0.99)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            
            # Draw Header Background
            c.setFillColorRGB(0.02, 0.13, 0.04) # Dark Green
            c.rect(0, height - 80, width, 80, fill=1, stroke=0)
            
            # Header Text
            c.setFillColor(colors.white)
            c.setFont(font_name, 22)
            c.drawCentredString(width/2, height - 45, reshape_text("سند قسط - هكبة المليون"))
            
            c.setFont(font_name, 12)
            c.drawRightString(width - 40, height - 65, reshape_text(f"رقم السند: {p.id}"))
            date_str = p.paid_date.strftime('%Y-%m-%d') if p.paid_date else (p.due_date.strftime('%Y-%m-%d') if p.due_date else '-')
            c.drawString(40, height - 65, reshape_text(f"التاريخ: {date_str}"))

            # Draw Receipt Body (White Card)
            c.setFillColorRGB(1, 1, 1)
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.setLineWidth(1)
            c.roundRect(40, 40, width - 80, height - 150, 10, fill=1, stroke=1)
            
            # Amount
            c.setFillColorRGB(0.09, 0.64, 0.29) # Green
            c.setFont(font_name, 26)
            c.drawCentredString(width/2, height - 130, reshape_text(f"{p.amount:,.2f} ر.ي"))
            
            # Status
            c.setFont(font_name, 14)
            c.setFillColorRGB(0.09, 0.64, 0.29) if p.is_paid else c.setFillColorRGB(0.86, 0.15, 0.15)
            status_txt = "تم الدفع بنجاح" if p.is_paid else "غير مدفوع"
            c.drawCentredString(width/2, height - 160, reshape_text(status_txt))

            # Details
            c.setFillColorRGB(0, 0, 0)
            y = height - 210
            lines = [
                ("اسم المشترك:", sub.name if sub else "-"),
                ("رقم المشترك:", sub.subscriber_number if sub else "-"),
                ("رقم الهاتف:", sub.phone if sub else "-"),
                ("القسط / الدورة:", f"قسط {p.installment_number} - دورة {p.cycle_number}"),
            ]
            if p.note:
                lines.append(("الملاحظة:", p.note))

            c.setStrokeColorRGB(0.9, 0.9, 0.9)
            for label, val in lines:
                c.setFont(font_name, 14)
                c.drawRightString(width - 60, y, reshape_text(label))
                c.drawRightString(width - 200, y, reshape_text(str(val)))
                
                c.line(60, y - 10, width - 60, y - 10)
                y -= 30

            # Footer
            c.setFont(font_name, 10)
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.drawCentredString(width/2, 20, reshape_text("شكراً لثقتكم بهكبة المليون"))

            c.save()
            ModernDialog(self, "نجاح", f"تم حفظ السند في {filename}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", str(e)).exec()

class PaymentDialog(QDialog):
    def __init__(self, parent, payment=None, max_inst=24, max_cycles=10, staff_list=None, default_amount=None):
        super().__init__(parent)
        self.setWindowTitle("بيانات العملية المالية" if not payment else "تعديل العملية المالية")
        fit_dialog_to_screen(self, 400, fixed_width=True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        max_inst = max(1, int(max_inst or 24))
        max_cycles = max(1, int(max_cycles or 10))
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.ent_amount = QLineEdit()
        if payment:
            self.ent_amount.setText(str(payment.amount))
        elif default_amount and float(default_amount) > 0:
            self.ent_amount.setText(str(default_amount))
        form.addRow("المبلغ:", self.ent_amount)

        self.cb_staff = QComboBox()
        self.cb_staff.addItem("تلقائي (بدون موظف محدد)", None)
        if staff_list:
            for s in staff_list:
                self.cb_staff.addItem(s.name, s.id)
                if payment and payment.staff_id == s.id:
                    self.cb_staff.setCurrentIndex(self.cb_staff.count() - 1)
        form.addRow("الموظف المحصل:", self.cb_staff)
        
        self.ent_date = QDateEdit()
        self.ent_date.setCalendarPopup(True)
        if payment and payment.due_date:
            self.ent_date.setDate(QDate(payment.due_date.year, payment.due_date.month, payment.due_date.day))
        else:
            self.ent_date.setDate(QDate.currentDate())
        form.addRow("التاريخ:", self.ent_date)
        
        self.cb_paid = QComboBox()
        self.cb_paid.addItems(["غير مدفوع", "مدفوع"])
        if payment is None or (payment and payment.is_paid):
            self.cb_paid.setCurrentIndex(1)
        form.addRow("الحالة:", self.cb_paid)
        
        self.cb_inst = QComboBox()
        self.cb_inst.addItems([str(i) for i in range(1, max_inst + 1)])
        if payment: self.cb_inst.setCurrentText(str(payment.installment_number))
        form.addRow("رقم القسط:", self.cb_inst)
        
        self.cb_cycle = QComboBox()
        self.cb_cycle.addItems([str(i) for i in range(1, max_cycles + 1)])
        if payment: self.cb_cycle.setCurrentText(str(payment.cycle_number))
        form.addRow("رقم الدورة:", self.cb_cycle)
        
        self.ent_note = QLineEdit()
        self.ent_note.setText(payment.note or "" if payment else "")
        form.addRow("الملاحظة:", self.ent_note)
        
        layout.addLayout(form)
        
        self.btn_save = QPushButton("حفظ")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.clicked.connect(self.validate_and_accept)
        layout.addWidget(self.btn_save)

    def validate_and_accept(self):
        amt_txt = self.ent_amount.text().strip()
        try:
            val = float(amt_txt)
            if val <= 0:
                ModernDialog(self, "تنبيه", "يرجى إدخال مبلغ أكبر من الصفر.").exec()
                return
        except ValueError:
            ModernDialog(self, "تنبيه", "يرجى إدخال مبلغ رقمي صحيح.").exec()
            return
        self.accept()

class AddSubscriberDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("إضافة مشترك جديد")
        fit_dialog_to_screen(self, 500, 450)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        form_frame = QFrame(); form_frame.setObjectName("StatCard")
        form = QFormLayout(form_frame); form.setSpacing(15)
        
        self.ent_name = QLineEdit()
        self.ent_name.setPlaceholderText("الاسم الرباعي")
        form.addRow("الاسم:", self.ent_name)
        
        self.ent_phone = QLineEdit()
        self.ent_phone.setPlaceholderText("05xxxxxxxx")
        form.addRow("رقم الهاتف:", self.ent_phone)

        self.cb_season = QComboBox()
        seasons = db_mod.get_all_seasons(self.db)
        curr_season = db_mod.get_current_season(self.db)
        for s in seasons:
            label = f"{s.name} (النشط ⭐)" if s.is_current else s.name
            self.cb_season.addItem(label, s.id)
        if curr_season:
            idx = self.cb_season.findData(curr_season.id)
            if idx >= 0:
                self.cb_season.setCurrentIndex(idx)
        self.cb_season.currentIndexChanged.connect(self.load_categories)
        form.addRow("الموسم:", self.cb_season)
        
        self.cb_cat = QComboBox()
        self.cb_cat.currentIndexChanged.connect(self.load_numbers)
        form.addRow("الفئة:", self.cb_cat)
        
        self.cb_num = QComboBox()
        self.cb_num.addItem("اختر الرقم...", None)
        form.addRow("رقم المشترك:", self.cb_num)

        self.load_categories()
        
        self.ent_pwd = QLineEdit()
        self.ent_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.ent_pwd.setPlaceholderText("كلمة المرور (6 أحرف على الأقل)")
        form.addRow("كلمة المرور للموقع:", self.ent_pwd)
        
        layout.addWidget(form_frame)
        
        self.btn_save = QPushButton("إضافة المشترك")
        self.btn_save.setObjectName("PrimaryBtn"); self.btn_save.setFixedHeight(45)
        self.btn_save.clicked.connect(self.validate_and_accept)
        layout.addWidget(self.btn_save)

    def load_categories(self):
        self.cb_cat.blockSignals(True)
        self.cb_cat.clear()
        self.cb_cat.addItem("اختر الفئة...", None)
        season_id = self.cb_season.currentData()
        q = self.db.query(db_mod.Category)
        if season_id:
            q = q.filter(db_mod.Category.season_id == season_id)
        for cat in q.all():
            self.cb_cat.addItem(cat.name, cat.id)
        self.cb_cat.blockSignals(False)
        if hasattr(self, 'cb_num'):
            self.load_numbers()

    def load_numbers(self):
        if not hasattr(self, 'cb_num'):
            return
        self.cb_num.clear()
        self.cb_num.addItem("اختر الرقم...", None)
        cat_id = self.cb_cat.currentData()
        if cat_id:
            nums = self.db.query(db_mod.SubscriberNumber).filter(
                db_mod.SubscriberNumber.category_id == cat_id,
                db_mod.SubscriberNumber.is_reserved == False
            ).all()
            for n in nums:
                self.cb_num.addItem(n.number, n.id)

    def validate_and_accept(self):
        if not self.ent_name.text() or not self.ent_phone.text() or not self.cb_cat.currentData() or not self.cb_num.currentData() or not self.ent_pwd.text():
            QMessageBox.warning(self, "خطأ", "يرجى ملء جميع الحقول")
            return
        if len(self.ent_pwd.text().strip()) < 6:
            QMessageBox.warning(self, "خطأ", "يجب أن تكون كلمة المرور 6 أحرف على الأقل")
            return
        self.accept()

class AddStaffDialog(QDialog):
    def __init__(self, parent, is_edit=False):
        super().__init__(parent)
        self.is_edit = is_edit
        self.setWindowTitle("تعديل بيانات الموظف" if is_edit else "إنشاء حساب موظف جديد")
        fit_dialog_to_screen(self, 400, fixed_width=True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        title = QLabel("تعديل بيانات الموظف" if is_edit else "إضافة موظف جديد")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2e7d32; margin-bottom: 10px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.ent_name = QLineEdit()
        self.ent_phone = QLineEdit()
        self.ent_staff_id = QLineEdit()
        self.ent_pwd = QLineEdit()
        self.ent_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        if is_edit:
            self.ent_pwd.setPlaceholderText("اتركه فارغاً للإبقاء على كلمة السر الحالية")
        self.role_combo = QComboBox()
        self.role_combo.addItems(["مدير", "محاسب", "موظف", "مشاهد"])

        form.addRow("اسم الموظف:", self.ent_name)
        form.addRow("رقم الهاتف:", self.ent_phone)
        form.addRow("رقم الموظف الخاص:", self.ent_staff_id)
        form.addRow("الصلاحية:", self.role_combo)
        form.addRow("كلمة السر:", self.ent_pwd)
        layout.addLayout(form)

        self.btn_save = QPushButton("حفظ التعديلات" if is_edit else "إنشاء الحساب")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.setFixedHeight(40)
        self.btn_save.clicked.connect(self.validate)
        layout.addWidget(self.btn_save)

    def validate(self):
        if not self.ent_name.text().strip() or not self.ent_staff_id.text().strip():
            QMessageBox.warning(self, "تنبيه", "يرجى ملء الحقول الإجبارية (الاسم ورقم الموظف)")
            return
        if not self.is_edit and not self.ent_pwd.text().strip():
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال كلمة السر")
            return
        self.accept()

class _BatchPaymentWorker(QThread):
    """Worker thread لتنفيذ السداد المتعدد في الخلفية بسرعة فائقة دون تجميد الواجهة"""
    progress = pyqtSignal(int, int, str)   # current, total, subscriber_name
    finished = pyqtSignal(int, int, int)   # created, updated, skipped
    error    = pyqtSignal(str)

    def __init__(self, db_url, selected_ids, amount, due_date, inst, cycle, note, staff_id):
        super().__init__()
        self.db_url       = db_url
        self.selected_ids = list(selected_ids)
        self.amount       = amount
        self.due_date     = due_date
        self.inst         = inst
        self.cycle        = cycle
        self.note         = note
        self.staff_id     = staff_id

    def run(self):
        db = db_mod.SessionLocal()
        try:
            skipped = 0
            updated = 0
            created = 0
            total   = len(self.selected_ids)

            if not self.selected_ids:
                self.finished.emit(0, 0, 0)
                return

            # 1. جلب البيانات المشتركة دفعة واحدة لتفادي مئات الاستعلامات الشبكية المتكررة
            cats_map  = {c.name: c for c in db.query(db_mod.Category).all()}
            staff_obj = db.get(db_mod.Staff, self.staff_id) if self.staff_id else None
            s_name    = staff_obj.name if staff_obj else None

            subs_list = db.query(db_mod.Subscriber).filter(
                db_mod.Subscriber.id.in_(self.selected_ids)
            ).all()
            subs_map = {s.id: s for s in subs_list}

            all_payments = db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id.in_(self.selected_ids)
            ).order_by(
                db_mod.Payment.cycle_number.asc(),
                db_mod.Payment.installment_number.asc()
            ).all()

            payments_by_sub = {}
            for p in all_payments:
                payments_by_sub.setdefault(p.subscriber_id, []).append(p)

            for idx, sid in enumerate(self.selected_ids):
                sub = subs_map.get(sid)
                if not sub:
                    skipped += 1
                    self.progress.emit(idx + 1, total, "—")
                    continue

                self.progress.emit(idx + 1, total, sub.name)

                cat = cats_map.get(sub.category)
                cat_amount = cat.amount if (cat and cat.amount and cat.amount > 0) else self.amount
                max_c = cat.max_cycles       if cat else 99
                max_i = cat.max_installments if cat else 99
                cat_start = (cat.start_date.date() if hasattr(cat.start_date, 'date') else cat.start_date) if (cat and cat.start_date) else None

                remaining = self.amount
                sub_payments = payments_by_sub.get(sid, [])

                # أ. التوزيع على الأقساط غير المسددة أولاً (FIFO)
                targets = [p for p in sub_payments if not p.is_paid]
                last_processed_c = 0
                last_processed_i = 0

                for p in targets:
                    if remaining <= 0:
                        break

                    if remaining < p.amount:
                        balance  = p.amount - remaining
                        p.amount = remaining
                        p.is_paid          = True
                        p.paid_date        = self.due_date
                        p.staff_id         = self.staff_id
                        p.is_staff_settled = False
                        p.note = db_mod.build_installment_note(
                            is_paid=True, due_date=p.due_date,
                            paid_date=self.due_date, user_note=self.note,
                            staff_name=s_name, is_partial=True
                        )
                        new_unpaid = db_mod.Payment(
                            subscriber_id      = sid,
                            amount             = balance,
                            due_date           = p.due_date,
                            is_paid            = False,
                            cycle_number       = p.cycle_number,
                            installment_number = p.installment_number,
                            note=db_mod.build_installment_note(
                                is_paid=False, due_date=p.due_date, is_partial=True
                            )
                        )
                        db.add(new_unpaid)
                        sub_payments.append(new_unpaid)
                        remaining = 0
                        updated  += 1
                    else:
                        p.is_paid          = True
                        p.paid_date        = self.due_date
                        p.staff_id         = self.staff_id
                        p.is_staff_settled = False
                        p.note = db_mod.build_installment_note(
                            is_paid=True, due_date=p.due_date,
                            paid_date=self.due_date, user_note=self.note,
                            staff_name=s_name
                        )
                        remaining -= p.amount
                        updated   += 1

                    last_processed_c = p.cycle_number
                    last_processed_i = p.installment_number

                # ب. إذا بقي رصيد يُكمل للأمام باستخدام القاموس في الذاكرة دون استعلامات شبكية
                if remaining > 0:
                    lookup = {(p.cycle_number, p.installment_number): p for p in sub_payments}
                    if last_processed_c > 0:
                        curr_c, curr_i = last_processed_c, last_processed_i + 1
                        if curr_i > max_i:
                            curr_i  = 1
                            curr_c += 1
                    else:
                        curr_c, curr_i = self.cycle, self.inst

                    safety_counter = 0
                    max_safety     = max_c * max_i

                    while remaining > 0 and curr_c <= max_c and safety_counter < max_safety:
                        safety_counter += 1
                        p = lookup.get((curr_c, curr_i))

                        if p and p.is_paid:
                            curr_i += 1
                            if curr_i > max_i:
                                curr_i  = 1
                                curr_c += 1
                            continue

                        pay_now    = min(remaining, cat_amount)
                        is_partial = (pay_now < cat_amount)

                        if cat_start:
                            day_offset = (curr_c - 1) * max_i + (curr_i - 1)
                            sched_due  = datetime.datetime.combine(cat_start + datetime.timedelta(days=day_offset), datetime.time.min)
                        else:
                            sched_due  = self.due_date

                        p_due     = p.due_date if (p and p.due_date) else sched_due
                        note_text = db_mod.build_installment_note(
                            is_paid=True, due_date=p_due,
                            paid_date=self.due_date, user_note=self.note,
                            staff_name=s_name, is_partial=is_partial
                        )

                        if p:
                            p.amount           = pay_now
                            p.is_paid          = True
                            p.paid_date        = self.due_date
                            p.staff_id         = self.staff_id
                            p.is_staff_settled = False
                            p.note             = note_text
                            updated           += 1
                        else:
                            new_p = db_mod.Payment(
                                subscriber_id      = sid,
                                amount             = pay_now,
                                due_date           = p_due,
                                paid_date          = self.due_date,
                                is_paid            = True,
                                installment_number = curr_i,
                                cycle_number       = curr_c,
                                note               = note_text,
                                staff_id           = self.staff_id,
                                is_staff_settled   = False
                            )
                            db.add(new_p)
                            lookup[(curr_c, curr_i)] = new_p
                            created += 1

                        if is_partial:
                            db.add(db_mod.Payment(
                                subscriber_id      = sid,
                                amount             = cat_amount - pay_now,
                                due_date           = p_due,
                                is_paid            = False,
                                cycle_number       = curr_c,
                                installment_number = curr_i,
                                note               = "متبقي من سداد جزئي"
                            ))
                            remaining = 0
                        else:
                            remaining -= pay_now

                        curr_i += 1
                        if curr_i > max_i:
                            curr_i  = 1
                            curr_c += 1

                # حفظ مرحلي كل 10 مشتركين لتسريع الاستجابة
                if (idx + 1) % 10 == 0:
                    db.commit()

            db.commit()
            self.finished.emit(created, updated, skipped)

        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            self.error.emit(str(e))
        finally:
            db.close()


class BatchPaymentDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db       = db
        self._worker  = None
        self._loading = None
        self.setWindowTitle("القيد المتعدد - إضافة دفعة لمجموعة")
        fit_dialog_to_screen(self, 600, 700)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # تصفية حسب الفئة
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("تصفية حسب الفئة:"))
        self.cb_cat = QComboBox()
        self.cb_cat.addItem("الكل", None)
        for cat in db.query(db_mod.Category).all():
            self.cb_cat.addItem(cat.name, cat.id)
        self.cb_cat.currentIndexChanged.connect(self.load_subscribers)
        filter_layout.addWidget(self.cb_cat)
        layout.addLayout(filter_layout)

        # شريط التحديد
        subs_header_layout = QHBoxLayout()
        subs_header_layout.addWidget(QLabel("اختر المشتركين:"))
        subs_header_layout.addStretch()

        self.btn_select_all = QPushButton("تحديد الكل")
        self.btn_select_all.setFixedWidth(90)
        self.btn_select_all.clicked.connect(lambda: self.set_all_check_state(Qt.CheckState.Checked))
        subs_header_layout.addWidget(self.btn_select_all)

        self.btn_deselect_all = QPushButton("إلغاء الكل")
        self.btn_deselect_all.setFixedWidth(90)
        self.btn_deselect_all.clicked.connect(lambda: self.set_all_check_state(Qt.CheckState.Unchecked))
        subs_header_layout.addWidget(self.btn_deselect_all)

        layout.addLayout(subs_header_layout)

        self.list_subs = QListWidget()
        layout.addWidget(self.list_subs)

        # نموذج تفاصيل الدفعة
        form_frame = QFrame()
        form_frame.setObjectName("StatCard")
        form = QFormLayout(form_frame)

        self.ent_amount = QLineEdit()
        form.addRow("المبلغ لكل مشترك:", self.ent_amount)

        self.ent_date = QDateEdit()
        self.ent_date.setCalendarPopup(True)
        self.ent_date.setDate(QDate.currentDate())
        form.addRow("التاريخ:", self.ent_date)

        self.cb_inst = QComboBox()
        self.cb_inst.addItems([str(i) for i in range(1, 25)])
        form.addRow("رقم القسط:", self.cb_inst)

        self.cb_cycle = QComboBox()
        self.cb_cycle.addItems([str(i) for i in range(1, 11)])
        form.addRow("رقم الدورة:", self.cb_cycle)

        self.ent_note = QLineEdit()
        form.addRow("الملاحظة:", self.ent_note)

        layout.addWidget(form_frame)

        btns_layout = QHBoxLayout()
        self.btn_save = QPushButton("تسجيل القيد للمختارين")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.setFixedHeight(45)
        self.btn_save.clicked.connect(self.submit_batch_payment)
        btns_layout.addWidget(self.btn_save)

        self.btn_close = QPushButton("إغلاق النافذة")
        self.btn_close.setObjectName("SecondaryBtn")
        self.btn_close.setFixedHeight(45)
        self.btn_close.clicked.connect(self.accept)
        btns_layout.addWidget(self.btn_close)

        layout.addLayout(btns_layout)

        self.load_subscribers()

    def load_subscribers(self):
        self.list_subs.clear()
        cat_id = self.cb_cat.currentData()
        max_i, max_c = 24, 10

        query = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted")
        if cat_id:
            cat = self.db.get(db_mod.Category, cat_id)
            if cat:
                max_i = cat.max_installments
                max_c = cat.max_cycles
            cat_name = self.cb_cat.currentText()
            query = query.filter(db_mod.Subscriber.category == cat_name)

        self.cb_inst.clear()
        self.cb_inst.addItems([str(i) for i in range(1, max_i + 1)])
        self.cb_cycle.clear()
        self.cb_cycle.addItems([str(i) for i in range(1, max_c + 1)])

        subs    = query.order_by(db_mod.Subscriber.name).all()
        sub_ids = [s.id for s in subs]

        next_unpaid_map = {}
        if sub_ids:
            rows = self.db.query(
                db_mod.Payment.subscriber_id,
                db_mod.Payment.cycle_number,
                db_mod.Payment.installment_number
            ).filter(
                db_mod.Payment.subscriber_id.in_(sub_ids),
                db_mod.Payment.is_paid == False
            ).order_by(
                db_mod.Payment.subscriber_id,
                db_mod.Payment.cycle_number.asc(),
                db_mod.Payment.installment_number.asc()
            ).all()
            for sub_id, c_num, i_num in rows:
                if sub_id not in next_unpaid_map:
                    next_unpaid_map[sub_id] = (c_num, i_num)

        for s in subs:
            if s.id in next_unpaid_map:
                c_num, i_num   = next_unpaid_map[s.id]
                status_hint = f" | القسط التالي: د{c_num}/ق{i_num}"
            else:
                status_hint = " | ✅ مكتمل"
            item = QListWidgetItem(f"{s.name} ({s.subscriber_number or s.phone}){status_hint}")
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list_subs.addItem(item)

    def set_all_check_state(self, state):
        for i in range(self.list_subs.count()):
            self.list_subs.item(i).setCheckState(state)

    def get_selected_ids(self):
        return [
            self.list_subs.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_subs.count())
            if self.list_subs.item(i).checkState() == Qt.CheckState.Checked
        ]

    def submit_batch_payment(self):
        selected_ids = self.get_selected_ids()
        if not selected_ids:
            ModernDialog(self, "تنبيه", "يرجى اختيار مشترك واحد على الأقل").exec()
            return

        # التحقق من المبلغ
        try:
            amount_str = self.ent_amount.text().strip()
            if not amount_str:
                ModernDialog(self, "خطأ", "يرجى إدخال المبلغ").exec()
                return
            amount = float(amount_str)
            if amount <= 0:
                ModernDialog(self, "خطأ", "يجب أن يكون المبلغ أكبر من صفر").exec()
                return
        except ValueError:
            ModernDialog(self, "خطأ", "يرجى إدخال مبلغ صحيح").exec()
            return

        due_date = datetime.datetime.combine(self.ent_date.date().toPyDate(), datetime.time.min)
        inst     = int(self.cb_inst.currentText())
        cycle    = int(self.cb_cycle.currentText())
        note     = self.ent_note.text().strip()
        staff    = getattr(self.parent(), 'logged_in_staff', None)
        staff_id = staff.id if staff else None

        # استخراج رابط DB غير المقنع
        db_url = get_safe_db_url(self.db)

        # تعطيل الأزرار
        self._set_buttons_enabled(False)

        # نافذة التحميل مع شريط تقدم حقيقي
        self._loading = LoadingDialog(
            self,
            title="⏳ جاري تسجيل السداد...",
            message=f"جاري معالجة {len(selected_ids)} مشترك — يرجى الانتظار"
        )
        self._loading.progress_bar.setRange(0, len(selected_ids))
        self._loading.progress_bar.setValue(0)
        self._loading.show()

        # تشغيل Worker في Thread منفصل
        self._worker = _BatchPaymentWorker(
            db_url=db_url, selected_ids=selected_ids,
            amount=amount, due_date=due_date,
            inst=inst, cycle=cycle, note=note, staff_id=staff_id
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int, name: str):
        if self._loading:
            self._loading.progress_bar.setValue(current)
            self._loading.set_message(
                f"جاري معالجة: {name}  ({current}/{total})",
                title="⏳ جاري تسجيل السداد..."
            )

    def _on_finished(self, created: int, updated: int, skipped: int):
        self._cleanup()
        try:
            self.db.expire_all()
        except Exception:
            pass
        parts = []
        if created: parts.append(f"تم إنشاء {created} قسط جديد")
        if updated: parts.append(f"تم تحديث {updated} قسط موجود")
        if skipped: parts.append(f"تم تجاوز {skipped} مشترك")
        ModernDialog(self, "✅ نجاح", " | ".join(parts) if parts else "تم التسجيل بنجاح").exec()
        self.load_subscribers()

    def _on_error(self, msg: str):
        self._cleanup()
        ModernDialog(self, "خطأ", f"حدث خطأ أثناء التسجيل:\n{msg}").exec()

    def _cleanup(self):
        if self._loading:
            self._loading.close()
            self._loading = None
        self._set_buttons_enabled(True)

    def _set_buttons_enabled(self, enabled: bool):
        for btn in (self.btn_save, self.btn_close, self.btn_select_all, self.btn_deselect_all):
            btn.setEnabled(enabled)


class JoinAnotherCategoryDialog(QDialog):
    """نافذة إشراك مشترك حالي في فئة أخرى مع منع تكرار الاشتراك في نفس الفئة مرتين"""
    def __init__(self, parent, sub_id, db):
        super().__init__(parent)
        self.db = db
        self.sub = db.get(db_mod.Subscriber, sub_id)
        self.new_sub = None
        self.setWindowTitle(f"إشراك في فئة أخرى — {self.sub.name if self.sub else ''}")
        fit_dialog_to_screen(self, 460, fixed_width=True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(f"➕ إشراك المشترك ({self.sub.name if self.sub else ''}) في فئة إضافية")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #10b981;")
        layout.addWidget(title)

        linked = db_mod.get_linked_subscriber_accounts(self.db, self.sub) if self.sub else []
        self.subscribed_cats = {(a.category or "").strip() for a in linked if a.category}

        info_txt = "الفئات المشترك بها حالياً: " + (
            " ، ".join(f"{a.category} (#{a.subscriber_number})" for a in linked) if linked else "لا يوجد"
        )
        lbl_info = QLabel(info_txt)
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("font-size: 12px; color: #64748b; background: #f8fafc; padding: 8px 12px; border-radius: 8px; border: 1px solid #e2e8f0;")
        layout.addWidget(lbl_info)

        form = QFormLayout()
        form.setSpacing(12)

        self.cb_cat = QComboBox()
        self.cb_cat.addItem("اختر الفئة الجديدة...", None)

        season_id = self.sub.season_id if self.sub else None
        q = self.db.query(db_mod.Category).filter(db_mod.Category.is_active == True)
        if season_id:
            q = q.filter(db_mod.Category.season_id == season_id)
        cats = q.order_by(db_mod.Category.id.asc()).all()
        if not cats:
            cats = self.db.query(db_mod.Category).filter(db_mod.Category.is_active == True).order_by(db_mod.Category.id.asc()).all()

        for c in cats:
            c_name = (c.name or "").strip()
            if c_name not in self.subscribed_cats:
                self.cb_cat.addItem(f"{c.name} — ({c.amount:,.0f} ر.ي)", c.id)

        self.cb_cat.currentIndexChanged.connect(self.load_numbers)
        form.addRow("الفئة المتاحة:", self.cb_cat)

        self.cb_num = QComboBox()
        self.cb_num.addItem("اختر الرقم...", None)
        form.addRow("رقم المشترك في الفئة:", self.cb_num)

        layout.addLayout(form)

        btns = QHBoxLayout()
        self.btn_save = QPushButton("تأكيد الاشتراك ✅")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.setFixedHeight(40)
        self.btn_save.clicked.connect(self.submit_join)

        btn_cancel = QPushButton("إلغاء")
        btn_cancel.setObjectName("DangerBtn")
        btn_cancel.setFixedHeight(40)
        btn_cancel.clicked.connect(self.reject)

        btns.addWidget(self.btn_save)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def load_numbers(self):
        self.cb_num.clear()
        self.cb_num.addItem("اختر الرقم...", None)
        cat_id = self.cb_cat.currentData()
        if cat_id:
            nums = self.db.query(db_mod.SubscriberNumber).filter(
                db_mod.SubscriberNumber.category_id == cat_id,
                db_mod.SubscriberNumber.is_reserved == False
            ).all()
            for n in nums:
                self.cb_num.addItem(n.number, n.id)

    def submit_join(self):
        cat_id = self.cb_cat.currentData()
        num_id = self.cb_num.currentData()
        if not cat_id or not num_id:
            ModernDialog(self, "تنبيه", "يرجى اختيار الفئة والرقم المتاح.").exec()
            return

        cat_obj = self.db.get(db_mod.Category, int(cat_id))
        if not cat_obj:
            ModernDialog(self, "خطأ", "الفئة غير موجودة.").exec()
            return

        linked = db_mod.get_linked_subscriber_accounts(self.db, self.sub)
        for acc in linked:
            if (acc.category or "").strip() == (cat_obj.name or "").strip():
                ModernDialog(
                    self,
                    "تنبيه",
                    f"المشترك مسجل بالفعل في ({cat_obj.name}) برقم (#{acc.subscriber_number})، لا يمكن الاشتراك في نفس الفئة مرتين."
                ).exec()
                return

        num_obj = self.db.get(db_mod.SubscriberNumber, int(num_id))
        if not num_obj or num_obj.is_reserved:
            ModernDialog(self, "تنبيه", "هذا الرقم تم حجزه مؤخراً، يرجى اختيار رقم آخر.").exec()
            return

        try:
            new_sub = db_mod.Subscriber(
                name=self.sub.name,
                phone=self.sub.phone,
                password=self.sub.password,
                national_id=self.sub.national_id,
                address=self.sub.address,
                email=self.sub.email,
                category=cat_obj.name,
                season_id=cat_obj.season_id or self.sub.season_id,
                selected_number_id=num_obj.id,
                subscriber_number=num_obj.number,
                status="accepted"
            )
            self.db.add(new_sub)
            self.db.flush()

            num_obj.is_reserved = True
            num_obj.subscriber_id = new_sub.id

            db_mod.ensure_daily_payments(self.db, new_sub)
            self.db.commit()
            self.new_sub = new_sub
            ModernDialog(
                self,
                "نجاح",
                f"تم إشراك ({self.sub.name}) في ({cat_obj.name}) برقم (#{num_obj.number}) بنجاح ✅"
            ).exec()
            self.accept()
        except Exception as e:
            self.db.rollback()
            ModernDialog(self, "خطأ", f"فشل إتمام الاشتراك: {e}").exec()


class AccountDetailsDialog(QDialog):
    def __init__(self, parent, sub_id, db):
        super().__init__(parent)
        self.sub_id = sub_id
        self.db = db
        self._changes_made = False
        sub = db.get(db_mod.Subscriber, sub_id)
        
        self.setWindowTitle(f"كشف حساب - {sub.name if sub else ''}")
        fit_dialog_to_screen(self, 900, 600)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        
        # الصف الأول من الرأس: اسم المشترك والفئة الحالية وأزرار التبديل بين الفئات
        header_top = QHBoxLayout()
        header_top.setSpacing(8)
        self.lbl_title = QLabel(f"كشف الحساب: {sub.name if sub else ''}")
        self.lbl_title.setObjectName("SectionTitle")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 800;")
        header_top.addWidget(self.lbl_title)

        # شارة الفئة والرقم الحالي
        self.lbl_current_cat_badge = QLabel("")
        self.lbl_current_cat_badge.setStyleSheet("""
            background-color: #e0f2fe;
            color: #0369a1;
            font-weight: 800;
            font-size: 11px;
            padding: 4px 10px;
            border-radius: 8px;
            border: 1px solid #bae6fd;
        """)
        header_top.addWidget(self.lbl_current_cat_badge)
        header_top.addStretch()

        # زر أرقام الفئات التي اشترك فيها المشترك والتنقل بين حساباته
        self.btn_switch_cat_account = QPushButton("🔄 أرقام الفئات المشترك بها")
        self.btn_switch_cat_account.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_switch_cat_account.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);
                color: #ffffff;
                font-weight: 900;
                font-size: 11px;
                padding: 5px 10px;
                border-radius: 8px;
                border: 1.5px solid #fde68a;
            }
            QPushButton:hover {
                background: #b45309;
            }
        """)
        self.btn_switch_cat_account.clicked.connect(self.show_linked_accounts_menu)
        header_top.addWidget(self.btn_switch_cat_account)

        # زر إشراك المشترك في فئة أخرى
        self.btn_join_other_cat = QPushButton("➕ فئة أخرى")
        self.btn_join_other_cat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_join_other_cat.setToolTip("إشراك المشترك في فئة إضافية أخرى واختيار رقم له فيها")
        self.btn_join_other_cat.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                font-weight: bold;
                font-size: 11px;
                padding: 5px 10px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.btn_join_other_cat.clicked.connect(self.open_join_another_category_dialog)
        header_top.addWidget(self.btn_join_other_cat)
        layout.addLayout(header_top)

        # الصف الثاني من الرأس: أزرار الإجراءات المالية والتصدير (موزعة بشكل متجاوب لا يتجاوز عرض الشاشة)
        header_actions = QHBoxLayout()
        header_actions.setSpacing(6)
        
        btn_add = QPushButton("قيد يدوي")
        btn_add.setObjectName("PrimaryBtn")
        btn_add.clicked.connect(self.add_payment)
        
        btn_pay_multi = QPushButton("تسديد المختار")
        btn_pay_multi.setObjectName("PrimaryBtn")
        btn_pay_multi.clicked.connect(self.pay_selected_payments)

        btn_del_multi = QPushButton("حذف المختار")
        btn_del_multi.setObjectName("DangerBtn")
        btn_del_multi.clicked.connect(self.delete_selected_payments)

        btn_exp_ex = QPushButton("إكسل")
        btn_exp_ex.clicked.connect(self.export_history_excel)
        
        btn_exp_pdf = QPushButton("PDF")
        btn_exp_pdf.setObjectName("DangerBtn")
        btn_exp_pdf.clicked.connect(self.export_history_pdf)
        
        header_actions.addWidget(btn_add)
        header_actions.addWidget(btn_pay_multi)
        header_actions.addWidget(btn_del_multi)
        header_actions.addStretch()
        header_actions.addWidget(btn_exp_ex)
        header_actions.addWidget(btn_exp_pdf)
        layout.addLayout(header_actions)

        # شريط ملخص الحساب العلوي
        summary_lay = QHBoxLayout()
        summary_lay.setSpacing(10)
        
        self.lbl_total_paid = self.create_summary_card(summary_lay, "إجمالي المسدد", "#10b981")
        self.lbl_total_remaining = self.create_summary_card(summary_lay, "المبالغ المتبقية", "#ef4444")
        self.lbl_paid_count = self.create_summary_card(summary_lay, "الأقساط المنجزة", "#3b82f6")
        layout.addLayout(summary_lay)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "تاريخ الاستحقاق",
            "تاريخ السداد الفعلي",
            "المبلغ",
            "القسط",
            "الدورة",
            "الحالة",
            "الملاحظة"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(48)
        self.table.setWordWrap(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setStyleSheet(
            "QTableWidget { font-size: 11px; } "
            "QHeaderView::section { font-size: 11px; padding: 4px 3px; }"
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        # فتح سند القسط عند النقر المزدوج على أي صف
        self.table.cellDoubleClicked.connect(self.open_payment_receipt)
        layout.addWidget(self.table)
        
        self.load_payments()

    def create_summary_card(self, layout, title, color):
        card = QFrame()
        card.setObjectName("StatCard")
        card.setFixedHeight(70)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(10, 6, 10, 6)
        vbox.setSpacing(2)
        
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold;")
        t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(t_lbl)
        
        v_lbl = QLabel("0.00 ر.ي")
        v_lbl.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: 800;")
        v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(v_lbl)
        
        layout.addWidget(card)
        return v_lbl

    def export_history_excel(self):
        self.db.expire_all()
        try:
            sub = self.db.get(db_mod.Subscriber, self.sub_id)
            payments = self.db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == self.sub_id).order_by(
                db_mod.Payment.cycle_number.desc(),
                db_mod.Payment.installment_number.desc(),
                db_mod.Payment.due_date.desc(),
                db_mod.Payment.id.desc()
            ).all()
            
            total_paid = sum(p.amount for p in payments if p.is_paid)
            total_due = sum(p.amount for p in payments if not p.is_paid)

            data = [{
                "تاريخ تسديد القسط المستحق": (p.due_date.strftime("%Y-%m-%d") if p.due_date else "-"),
                "تاريخ تسديد القسط الفعلي": (p.paid_date.strftime("%Y-%m-%d %H:%M") if p.paid_date else "-"),
                "المبلغ": p.amount,
                "القسط": p.installment_number,
                "الدورة": p.cycle_number,
                "الحالة": "مدفوع" if p.is_paid else "غير مدفوع",
                "الملاحظة": (p.note or "-").split("|")[0].strip()
            } for p in payments]
            df = pd.DataFrame(data)
            
            filename, _ = QFileDialog.getSaveFileName(self, "حفظ كشف الحساب (Excel)", f"statement_{sub.phone}.xlsx", "Excel Files (*.xlsx)")
            if not filename: return
            
            def get_setting(key, default=""):
                s = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
                return s.value if s else default

            company_name = get_setting("company_name", "هكبة المليون")
            company_logo_path = get_setting("company_logo_path", "")

            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Statement', index=False, startrow=8)
                workbook = writer.book
                worksheet = writer.sheets['Statement']

                # --- تنسيقات احترافية ---
                header_bg = '#052109'
                title_color = '#c9a84c'
                header_font_color = '#FFFFFF'
                
                header_format = workbook.add_format({'bold': True, 'bg_color': header_bg, 'color': title_color, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial', 'font_size': 12})
                title_format = workbook.add_format({'bold': True, 'font_size': 20, 'color': title_color, 'bg_color': header_bg, 'align': 'center', 'valign': 'vcenter'})
                subtitle_format = workbook.add_format({'font_size': 11, 'color': header_font_color, 'bg_color': header_bg, 'align': 'center', 'valign': 'vcenter'})
                summary_header_format = workbook.add_format({'bold': True, 'bg_color': '#e8f5e9', 'color': '#0a3d0e', 'border': 1, 'font_name': 'Arial', 'font_size': 11})
                summary_value_format = workbook.add_format({'bg_color': '#e8f5e9', 'border': 1, 'num_format': '#,##0.00', 'font_name': 'Arial', 'font_size': 11})
                
                # --- الترويسة ---
                worksheet.merge_range('A1:G2', company_name, title_format)
                if company_logo_path and os.path.exists(company_logo_path):
                    worksheet.insert_image('A1', company_logo_path, {'x_offset': 5, 'y_offset': 5, 'x_scale': 0.5, 'y_scale': 0.5})

                worksheet.merge_range('A3:G3', f"كشف حساب المشترك: {sub.name} ({sub.subscriber_number})", subtitle_format)

                # --- ملخص الحساب ---
                worksheet.write('A5', 'إجمالي المسدد', summary_header_format)
                worksheet.write('B5', total_paid, summary_value_format)
                worksheet.write('C5', 'إجمالي المتبقي', summary_header_format)
                worksheet.write('D5', total_due, summary_value_format)
                worksheet.write('E5', 'تاريخ التقرير', summary_header_format)
                worksheet.write('F5', datetime.datetime.now().strftime('%Y-%m-%d'), summary_value_format)
                worksheet.set_row(4, 30)

                # --- ترويسة الجدول ---
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(8, col_num, value, header_format)

                # --- تنسيق الأعمدة ---
                worksheet.set_column('A:A', 22) # تاريخ تسديد القسط المستحق
                worksheet.set_column('B:B', 22) # تاريخ تسديد القسط الفعلي
                worksheet.set_column('C:C', 15) # المبلغ
                worksheet.set_column('D:D', 10) # القسط
                worksheet.set_column('E:E', 10) # الدورة
                worksheet.set_column('F:F', 12) # الحالة
                worksheet.set_column('G:G', 40) # الملاحظة

                # --- تنسيق شرطي للألوان ---
                paid_format = workbook.add_format({'bg_color': '#dcfce7', 'font_color': '#166534'})
                unpaid_format = workbook.add_format({'bg_color': '#fee2e2', 'font_color': '#991b1b'})
                worksheet.conditional_format('F9:F1000', {'type': 'cell', 'criteria': '==', 'value': '"مدفوع"', 'format': paid_format})
                worksheet.conditional_format('F9:F1000', {'type': 'cell', 'criteria': '==', 'value': '"غير مدفوع"', 'format': unpaid_format})

                # --- تجميد الأجزاء العلوية ---
                worksheet.freeze_panes(9, 0)

                # --- إخفاء خطوط الشبكة ---
                worksheet.hide_gridlines(2)

            ModernDialog(self, "نجاح", f"تم تصدير {filename} بنجاح").exec()
        except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()

    def export_history_pdf(self):
        self.db.expire_all()
        try:
            sub = self.db.get(db_mod.Subscriber, self.sub_id)
            payments = self.db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == self.sub_id).order_by(
                db_mod.Payment.cycle_number.desc(),
                db_mod.Payment.installment_number.desc(),
                db_mod.Payment.due_date.desc(),
                db_mod.Payment.id.desc()
            ).all()
            
            total_paid = sum(p.amount for p in payments if p.is_paid)
            total_due = sum(p.amount for p in payments if not p.is_paid)

            filename, _ = QFileDialog.getSaveFileName(self, "حفظ كشف الحساب (PDF)", f"statement_{sub.phone}.pdf", "PDF Files (*.pdf)")
            if not filename: return
            
            c = canvas.Canvas(filename, pagesize=A4)
            W, H = A4
            M = 36
            font_name = register_arabic_font()

            GOLD        = colors.HexColor("#c9a84c")
            DARK_GREEN  = colors.HexColor("#052109")
            MID_GREEN   = colors.HexColor("#0a3d0e")
            LIGHT_GREEN = colors.HexColor("#e8f5e9")
            PAID_COLOR  = colors.HexColor("#1b5e20")
            UNPAID_CLR  = colors.HexColor("#b71c1c")
            ROW_ALT     = colors.HexColor("#f1f8f1")
            ROW_EVEN    = colors.white
            BORDER_CLR  = colors.HexColor("#c8e6c9")
            GREY_TXT    = colors.HexColor("#546e7a")

            def get_setting(key, default=""):
                s = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
                return s.value if s else default

            company_name       = get_setting("company_name",             "هكبة المليون")
            company_legal_name = get_setting("company_legal_name",       "الاسبوعية")
            company_record     = get_setting("company_commercial_record", "")
            company_logo_path  = get_setting("company_logo_path",        "")

            def draw_ar(cv, x, y, text, size=10, color=colors.black):
                cv.setFont(font_name, size)
                cv.setFillColor(color)
                cv.drawString(x, y, reshape_text(str(text)))

            def draw_header(cv, page_num=1):
                cv.setFillColor(DARK_GREEN)
                cv.roundRect(M, H - 132, W - 2*M, 120, 8, fill=1, stroke=0)

                if company_logo_path and os.path.exists(company_logo_path):
                    try:
                        cv.drawImage(company_logo_path, M + 12, H - 122, width=68, height=68, preserveAspectRatio=True, mask='auto')
                    except Exception:
                        pass

                cx = W / 2
                cv.setFillColor(GOLD)
                cv.setFont(font_name, 22)
                cv.drawCentredString(cx, H - 68, reshape_text(company_name))
                cv.setFont(font_name, 11)
                cv.setFillColor(colors.white)
                cv.drawCentredString(cx, H - 84, reshape_text(company_legal_name))
                if company_record:
                    cv.setFont(font_name, 8)
                    cv.setFillColor(colors.HexColor("#a5d6a7"))
                    cv.drawCentredString(cx, H - 97, reshape_text(f"السجل التجاري: {company_record}"))

                cv.setFont(font_name, 9)
                cv.setFillColor(colors.HexColor("#a5d6a7"))
                cv.drawRightString(W - M - 12, H - 62, reshape_text(f"تاريخ الإصدار: {datetime.date.today().strftime('%Y-%m-%d')}"))
                cv.setFont(font_name, 8)
                cv.setFillColor(colors.HexColor("#69f0ae"))
                cv.drawRightString(W - M - 12, H - 76, reshape_text("كشف حساب المشترك"))
                cv.setFont(font_name, 8)
                cv.setFillColor(colors.white)
                cv.drawRightString(W - M - 12, H - 90, reshape_text(f"صفحة {page_num}"))

                cv.setStrokeColor(GOLD)
                cv.setLineWidth(1.5)
                cv.line(M, H - 137, W - M, H - 137)

            page_num = 1
            draw_header(c, page_num)
            y = H - 152

            BOX_H = 96
            half  = (W - 2*M) / 2

            c.setFillColor(LIGHT_GREEN)
            c.setStrokeColor(BORDER_CLR)
            c.setLineWidth(0.8)
            c.roundRect(M, y - BOX_H, W - 2*M, BOX_H, 6, fill=1, stroke=1)

            c.setStrokeColor(colors.HexColor("#b2dfdb"))
            c.setLineWidth(0.5)
            c.line(M + half, y - 10, M + half, y - BOX_H + 10)

            c.setFillColor(MID_GREEN)
            c.roundRect(M + 6,        y - 20, half - 12, 16, 3, fill=1, stroke=0)
            c.roundRect(M + half + 6, y - 20, half - 12, 16, 3, fill=1, stroke=0)
            draw_ar(c, M + 12,        y - 15, "بيانات المشترك", size=9, color=GOLD)
            draw_ar(c, M + half + 12, y - 15, "بيانات المنظومة", size=9, color=GOLD)

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

            total_all = total_paid + total_due
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

            c.setFillColor(MID_GREEN)
            c.roundRect(M, y - 18, W - 2*M, 18, 4, fill=1, stroke=0)
            draw_ar(c, M + 10, y - 13, "سجل الأقساط التفصيلي", size=10, color=GOLD)
            y -= 22

            COL_X = [M, M+48, M+105, M+195, M+285, M+365]
            HDRS  = ["الدورة/القسط", "المبلغ", "تاريخ القسط المستحق", "تاريخ القسط الفعلي", "الحالة", "ملاحظة"]
            ROW_H = 17

            def draw_table_header(cv, y_pos):
                cv.setFillColor(DARK_GREEN)
                cv.rect(M, y_pos - ROW_H, W - 2*M, ROW_H, fill=1, stroke=0)
                for idx, h in enumerate(HDRS):
                    draw_ar(cv, COL_X[idx] + 3, y_pos - 12, h, size=8, color=GOLD)
                return y_pos - ROW_H

            y = draw_table_header(c, y)

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
                status_fg  = PAID_COLOR if p.is_paid else UNPAID_CLR
                note_short = (p.note or "").split("|")[0].strip()[:28]
                txt_clr    = colors.HexColor("#1a2e1b")

                draw_ar(c, COL_X[0]+3, y-12, f"{p.cycle_number or '-'}/{p.installment_number or '-'}", size=8, color=txt_clr)
                draw_ar(c, COL_X[1]+3, y-12, f"{p.amount or 0:,.0f}", size=8, color=txt_clr)
                draw_ar(c, COL_X[2]+3, y-12, due_date,                size=7, color=txt_clr)
                draw_ar(c, COL_X[3]+3, y-12, paid_date,               size=7, color=txt_clr)
                draw_ar(c, COL_X[4]+3, y-12, status_lbl,              size=8, color=status_fg)
                draw_ar(c, COL_X[5]+3, y-12, note_short,              size=7, color=GREY_TXT)
                y -= ROW_H

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
                ("إجمالي الأقساط",  f"{total_all:,.0f} ريال",  colors.white),
                ("إجمالي المسدّد",  f"{total_paid:,.0f} ريال",  colors.HexColor("#69f0ae")),
                ("المتبقي",          f"{total_due:,.0f} ريال",   colors.HexColor("#ff8a80")),
            ]
            for idx, (lbl, val, clr) in enumerate(summary):
                bx = M + idx * blk_w
                if idx > 0:
                    c.setStrokeColor(colors.HexColor("#1b5e20"))
                    c.setLineWidth(0.4)
                    c.line(bx, y - 8, bx, y - 44)
                draw_ar(c, bx + 8, y - 18, lbl, size=8,  color=colors.HexColor("#a5d6a7"))
                draw_ar(c, bx + 8, y - 36, val, size=13, color=clr)

            c.setFont(font_name, 7)
            c.setFillColor(GREY_TXT)
            c.drawCentredString(W / 2, M + 8, reshape_text(f"صادر تلقائياً من منظومة {company_name} — {datetime.date.today().strftime('%Y-%m-%d')}"))

            c.save()
            ModernDialog(self, "نجاح", f"تم تصدير {filename} بنجاح").exec()
        except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()

    def _update_account_switcher_header(self):
        """تحديث شارة الفئة الحالية وزر أرقام الفئات المشترك بها للتنقل بين حسابات المشترك."""
        sub = self.db.get(db_mod.Subscriber, self.sub_id)
        if not sub:
            return
        self.setWindowTitle(f"كشف حساب - {sub.name or ''} ({sub.category or ''} - #{sub.subscriber_number or ''})")
        if hasattr(self, "lbl_title"):
            self.lbl_title.setText(f"كشف الحساب: {sub.name or ''}")
        if hasattr(self, "lbl_current_cat_badge"):
            self.lbl_current_cat_badge.setText(f"🏷️ {sub.category or 'بدون فئة'}  |  🔢 #{sub.subscriber_number or '-'}")

        linked = db_mod.get_linked_subscriber_accounts(self.db, sub)
        if hasattr(self, "btn_switch_cat_account"):
            if len(linked) > 1:
                self.btn_switch_cat_account.setText(f"🔄 أرقام فئات المشترك ({len(linked)}) ▾")
                self.btn_switch_cat_account.show()
            else:
                self.btn_switch_cat_account.hide()

    def show_linked_accounts_menu(self):
        """عرض قائمة بأرقام المشترك في جميع الفئات المشترك بها للانتقال الفوري بين حساباته."""
        sub = self.db.get(db_mod.Subscriber, self.sub_id)
        if not sub:
            return
        linked = db_mod.get_linked_subscriber_accounts(self.db, sub)
        menu = QMenu(self)
        menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f172a;
                color: #f8fafc;
                border: 2px solid #f59e0b;
                border-radius: 10px;
                padding: 6px;
                font-family: 'Tajawal';
                font-size: 13px;
                font-weight: bold;
            }
            QMenu::item {
                padding: 8px 18px;
                border-radius: 6px;
                margin: 2px 4px;
            }
            QMenu::item:selected {
                background-color: #1e293b;
                color: #fde047;
            }
        """)
        for acc in linked:
            is_curr = (acc.id == self.sub_id)
            prefix = "✅ " if is_curr else "🏷️ "
            suffix = "  (الحساب المفتوح حالياً)" if is_curr else "  ⬅️ انتقال لهذا الحساب"
            act = QAction(f"{prefix}{acc.category or 'بدون فئة'} — رقم المشترك: #{acc.subscriber_number or '-'}{suffix}", self)
            act.triggered.connect(lambda checked=False, tid=acc.id: self.switch_to_account(tid))
            menu.addAction(act)

        pos = self.btn_switch_cat_account.mapToGlobal(QPoint(0, self.btn_switch_cat_account.height() + 4))
        menu.exec(pos)

    def switch_to_account(self, target_sub_id):
        """التبديل الفوري إلى حساب المشترك في الفئة المختارة."""
        if not target_sub_id or int(target_sub_id) == int(self.sub_id):
            return
        self.sub_id = int(target_sub_id)
        self.load_payments()

    def open_join_another_category_dialog(self):
        """فتح نافذة إشراك المشترك الحالي في فئة إضافية أخرى."""
        dlg = JoinAnotherCategoryDialog(self, self.sub_id, self.db)
        if dlg.exec() and dlg.new_sub:
            self._changes_made = True
            self.sub_id = dlg.new_sub.id
            self.load_payments()

    def load_payments(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all() # Ensure fresh data
        self._update_account_switcher_header()
        payments = self.db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == self.sub_id).order_by(
            db_mod.Payment.cycle_number.desc(),
            db_mod.Payment.installment_number.desc(),
            db_mod.Payment.due_date.desc(),
            db_mod.Payment.id.desc()
        ).all()
        self.table.setRowCount(len(payments))

        total_paid = 0
        total_remaining = 0
        paid_count = 0
        
        now = datetime.datetime.now()

        for i, p in enumerate(payments):
            if p.is_paid:
                total_paid += p.amount
                paid_count += 1
            else:
                total_remaining += p.amount
            
            # تحديد الحالة واللون الخلفي للصف
            is_arrear = not p.is_paid and p.due_date and p.due_date < now
            is_partial_balance = p.note and ("(متبقي من" in p.note)
            
            bg_color = None
            if is_arrear:
                bg_color = QColor("#fee2e2") # أحمر فاتح للمتأخرات
            elif is_partial_balance:
                bg_color = QColor("#fff7ed") # برتقالي فاتح للمتبقي من سداد جزئي

            due_date_cell = p.due_date.strftime("%Y-%m-%d") if p.due_date else "-"
            paid_date_cell = p.paid_date.strftime("%Y-%m-%d %H:%M") if p.paid_date else "-"
            items = [
                QTableWidgetItem(due_date_cell),
                QTableWidgetItem(paid_date_cell),
                QTableWidgetItem(f"{p.amount:,.2f}"),
                QTableWidgetItem(str(p.installment_number)),
                QTableWidgetItem(str(p.cycle_number)),
                QTableWidgetItem("مدفوع" if p.is_paid else "غير مدفوع"),
                QTableWidgetItem(p.note or "-")
            ]
            
            items[5].setForeground(QColor("#2e7d32" if p.is_paid else "#ef4444"))

            for col, item in enumerate(items):
                if bg_color: item.setBackground(bg_color)
                self.table.setItem(i, col, item)
            
            # Store ID in data role
            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, p.id)

        # تحديث أرقام الملخص
        self.lbl_total_paid.setText(f"{total_paid:,.2f} ر.ي")
        self.lbl_total_remaining.setText(f"{total_remaining:,.2f} ر.ي")
        self.lbl_paid_count.setText(f"{paid_count} / {len(payments)}")

    def process_smart_payment(self, total_amount, cycle, inst, date, is_paid, note, cat_amount, max_c, max_i, staff_id=None):
        self.db.expire_all()
        sub = self.db.get(db_mod.Subscriber, self.sub_id)
        if sub:
            try:
                db_mod.ensure_daily_payments(self.db, sub)
            except Exception:
                pass

        staff_obj = self.db.get(db_mod.Staff, staff_id) if staff_id else None
        s_name = staff_obj.name if staff_obj else None

        if not is_paid or total_amount <= 0 or cat_amount <= 0:
            return False 
            
        remaining = total_amount

        cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first() if sub else None
        cat_start = (cat.start_date.date() if hasattr(cat.start_date, 'date') else cat.start_date) if (cat and cat.start_date) else None
        
        # 1. Collect all potential payment targets:
        targets = self.db.query(db_mod.Payment).filter(
            db_mod.Payment.subscriber_id == self.sub_id,
            db_mod.Payment.is_paid == False
        ).order_by(db_mod.Payment.cycle_number.asc(), db_mod.Payment.installment_number.asc()).all()
        
        selected_exists = any(t.cycle_number == cycle and t.installment_number == inst for t in targets)
        
        if not selected_exists:
            p_selected = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == self.sub_id,
                db_mod.Payment.cycle_number == cycle,
                db_mod.Payment.installment_number == inst
            ).first()
            
            if p_selected and not p_selected.is_paid:
                targets.append(p_selected)
                targets.sort(key=lambda x: (x.cycle_number, x.installment_number))

        # 2. Distribute among existing targets first (FIFO)
        last_processed_c = 0
        last_processed_i = 0
        
        for p in targets:
            if remaining <= 0: break
            
            if remaining < p.amount:
                # حالة السداد الجزئي لسجل موجود
                balance = p.amount - remaining
                p.amount = remaining
                p.is_paid = True
                p.paid_date = date
                p.staff_id = staff_id
                p.is_staff_settled = False
                p.note = db_mod.build_installment_note(is_paid=True, due_date=p.due_date, paid_date=date, user_note=note, staff_name=s_name, is_partial=True)

                # إنشاء سجل متبقي
                new_unpaid = db_mod.Payment(
                    subscriber_id=self.sub_id,
                    amount=balance,
                    due_date=p.due_date,
                    is_paid=False,
                    cycle_number=p.cycle_number,
                    installment_number=p.installment_number,
                    note=db_mod.build_installment_note(is_paid=False, due_date=p.due_date, is_partial=True)
                )
                self.db.add(new_unpaid)
                remaining = 0
            else:
                pay_now = p.amount
                p.is_paid = True
                p.paid_date = date
                p.staff_id = staff_id
                p.is_staff_settled = False
                p.note = db_mod.build_installment_note(is_paid=True, due_date=p.due_date, paid_date=date, user_note=note, staff_name=s_name)
                remaining -= pay_now
            last_processed_c = p.cycle_number
            last_processed_i = p.installment_number

        # 3. If balance remains, continue forward creation/update
        if remaining > 0:
            if last_processed_c > 0:
                curr_c, curr_i = last_processed_c, last_processed_i + 1
                if curr_i > max_i:
                    curr_i = 1; curr_c += 1
            else:
                curr_c, curr_i = cycle, inst

            safety_counter = 0
            max_safety = max_c * max_i

            while remaining > 0 and curr_c <= max_c and safety_counter < max_safety:
                safety_counter += 1
                p = self.db.query(db_mod.Payment).filter(
                    db_mod.Payment.subscriber_id == self.sub_id,
                    db_mod.Payment.cycle_number == curr_c,
                    db_mod.Payment.installment_number == curr_i
                ).first()
                
                if p and p.is_paid:
                    curr_i += 1
                    if curr_i > max_i: curr_i = 1; curr_c += 1
                    continue
                
                pay_now = min(remaining, cat_amount)
                is_partial = (pay_now < cat_amount)

                # حساب تاريخ الاستحقاق المجدول الطبيعي للقسط
                if cat_start:
                    day_offset = (curr_c - 1) * max_i + (curr_i - 1)
                    sched_due = datetime.datetime.combine(cat_start + datetime.timedelta(days=day_offset), datetime.time.min)
                else:
                    sched_due = date

                p_due = p.due_date if p else sched_due
                new_note = db_mod.build_installment_note(is_paid=True, due_date=p_due, paid_date=date, user_note=note, staff_name=s_name, is_partial=is_partial)

                if p:
                    # تحديث السجل غير المسدد الموجود بدلاً من إنشاء قسط مكرر!
                    if pay_now < p.amount:
                        balance = p.amount - pay_now
                        p.amount = pay_now
                        p.is_paid = True
                        p.paid_date = date
                        p.staff_id = staff_id
                        p.is_staff_settled = False
                        p.note = new_note
                        new_unpaid = db_mod.Payment(
                            subscriber_id=self.sub_id,
                            amount=balance,
                            due_date=p.due_date,
                            is_paid=False,
                            cycle_number=curr_c,
                            installment_number=curr_i,
                            note=db_mod.build_installment_note(is_paid=False, due_date=p.due_date, is_partial=True)
                        )
                        self.db.add(new_unpaid)
                        remaining = 0
                    else:
                        p.amount = pay_now
                        p.is_paid = True
                        p.paid_date = date
                        p.staff_id = staff_id
                        p.is_staff_settled = False
                        p.note = new_note
                        remaining -= pay_now
                else:
                    new_paid = db_mod.Payment(
                        subscriber_id=self.sub_id,
                        amount=pay_now,
                        due_date=sched_due,
                        paid_date=date,
                        is_paid=True,
                        cycle_number=curr_c,
                        installment_number=curr_i,
                        note=new_note,
                        staff_id=staff_id,
                        is_staff_settled=False
                    )
                    self.db.add(new_paid)

                    if pay_now < cat_amount:
                        new_unpaid = db_mod.Payment(
                            subscriber_id=self.sub_id,
                            amount=cat_amount - pay_now,
                            due_date=sched_due,
                            is_paid=False,
                            cycle_number=curr_c,
                            installment_number=curr_i,
                            note=db_mod.build_installment_note(is_paid=False, due_date=sched_due, is_partial=True)
                        )
                        self.db.add(new_unpaid)
                        remaining = 0
                    else:
                        remaining -= pay_now

                curr_i += 1
                if curr_i > max_i: curr_i = 1; curr_c += 1
        
        self.db.commit()
        return True

    def open_payment_receipt(self, row, col):
        try:
            item = self.table.item(row, 0)
            if not item: return
            pid = item.data(Qt.ItemDataRole.UserRole)
            if not pid: return
            dlg = PaymentReceiptDialog(self, pid, self.db)
            dlg.exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"فشل عرض السند: {e}").exec()

    def add_payment(self):
        sub = self.db.get(db_mod.Subscriber, self.sub_id)
        cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first() if sub else None
        cat_amount = float(cat.amount or 0) if cat else 0.0
        max_c = max(1, int(cat.max_cycles or 10)) if cat else 10
        max_i = max(1, int(cat.max_installments or 24)) if cat else 24

        staff_list = self.db.query(db_mod.Staff).all()

        dialog = PaymentDialog(
            self,
            max_cycles=max_c,
            max_inst=max_i,
            staff_list=staff_list,
            default_amount=cat_amount if cat_amount > 0 else None,
        )
        if dialog.exec():
            try:
                entered_amount = float(dialog.ent_amount.text().strip())
                is_paid = (dialog.cb_paid.currentIndex() == 1)
                cycle = int(dialog.cb_cycle.currentText() or 1)
                inst = int(dialog.cb_inst.currentText() or 1)
                date = datetime.datetime.combine(dialog.ent_date.date().toPyDate(), datetime.time.min)
                note = dialog.ent_note.text().strip()
                staff_id = dialog.cb_staff.currentData()
                if not staff_id and self.parent() and getattr(self.parent(), "logged_in_staff", None):
                    staff_id = self.parent().logged_in_staff.id

                if is_paid and cat_amount > 0:
                    processed_count = self._execute_smart_payment_sync(
                        entered_amount, cycle, inst, date, note, cat_amount, max_c, max_i, staff_id
                    )
                    self._changes_made = True
                    self.load_payments()
                    ModernDialog(self, "نجاح", f"تم تسجيل السداد ومعالجة {processed_count} قسط بنجاح").exec()
                else:
                    new_p = db_mod.Payment(
                        subscriber_id=self.sub_id,
                        amount=entered_amount,
                        due_date=date,
                        is_paid=is_paid,
                        paid_date=date if is_paid else None,
                        installment_number=inst,
                        cycle_number=cycle,
                        note=note,
                        staff_id=staff_id,
                        is_staff_settled=False if is_paid else None,
                    )
                    self.db.add(new_p)
                    self.db.commit()
                    self._changes_made = True
                    self.load_payments()
                    ModernDialog(self, "نجاح", "تم تسجيل القيد اليدوي بنجاح").exec()
            except Exception as e:
                try:
                    self.db.rollback()
                except Exception:
                    pass
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء تسجيل القيد: {e}").exec()

    def _execute_smart_payment_sync(self, total_amount, cycle, inst, date, note, cat_amount, max_c, max_i, staff_id=None):
        """توزيع وتسديد المبلغ مباشرة على قاعدة البيانات المحلية بسرعة فورية ومع تفعيل المزامنة السحابية."""
        sub = self.db.get(db_mod.Subscriber, self.sub_id)
        staff_obj = self.db.get(db_mod.Staff, staff_id) if staff_id else None
        s_name = staff_obj.name if staff_obj else None

        cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first() if sub else None
        cat_start = (cat.start_date.date() if hasattr(cat.start_date, 'date') else cat.start_date) if (cat and cat.start_date) else None

        remaining = float(total_amount)
        processed = 0

        all_sub_payments = self.db.query(db_mod.Payment).filter(
            db_mod.Payment.subscriber_id == self.sub_id
        ).order_by(
            db_mod.Payment.cycle_number.asc(),
            db_mod.Payment.installment_number.asc()
        ).all()

        targets = [p for p in all_sub_payments if not p.is_paid]
        last_processed_c = 0
        last_processed_i = 0

        # 1. توزيع المبلغ على الأقساط غير المسددة الموجودة أولاً (FIFO)
        for p in targets:
            if remaining <= 0:
                break

            if remaining < p.amount:
                balance = p.amount - remaining
                p.amount = remaining
                p.is_paid = True
                p.paid_date = date
                p.staff_id = staff_id
                p.is_staff_settled = False
                p.note = db_mod.build_installment_note(
                    is_paid=True, due_date=p.due_date, paid_date=date,
                    user_note=note, staff_name=s_name, is_partial=True
                )
                new_unpaid = db_mod.Payment(
                    subscriber_id=self.sub_id,
                    amount=balance,
                    due_date=p.due_date,
                    is_paid=False,
                    cycle_number=p.cycle_number,
                    installment_number=p.installment_number,
                    note=db_mod.build_installment_note(is_paid=False, due_date=p.due_date, is_partial=True)
                )
                self.db.add(new_unpaid)
                all_sub_payments.append(new_unpaid)
                remaining = 0
            else:
                pay_now = p.amount
                p.is_paid = True
                p.paid_date = date
                p.staff_id = staff_id
                p.is_staff_settled = False
                p.note = db_mod.build_installment_note(
                    is_paid=True, due_date=p.due_date, paid_date=date,
                    user_note=note, staff_name=s_name
                )
                remaining -= pay_now

            last_processed_c = p.cycle_number
            last_processed_i = p.installment_number
            processed += 1

        # 2. إذا بقي رصيد، نكمل للأمام باستخدام القاموس في الذاكرة
        if remaining > 0:
            lookup = {(p.cycle_number, p.installment_number): p for p in all_sub_payments}
            if last_processed_c > 0:
                curr_c, curr_i = last_processed_c, last_processed_i + 1
                if curr_i > max_i:
                    curr_i = 1
                    curr_c += 1
            else:
                curr_c, curr_i = cycle, inst

            safety_counter = 0
            max_safety = max(1, max_c * max_i)

            while remaining > 0 and curr_c <= max_c and safety_counter < max_safety:
                safety_counter += 1
                p = lookup.get((curr_c, curr_i))

                if p and p.is_paid:
                    curr_i += 1
                    if curr_i > max_i:
                        curr_i = 1
                        curr_c += 1
                    continue

                pay_now = min(remaining, cat_amount)
                is_partial = (pay_now < cat_amount)

                if cat_start:
                    day_offset = (curr_c - 1) * max_i + (curr_i - 1)
                    sched_due = datetime.datetime.combine(cat_start + datetime.timedelta(days=day_offset), datetime.time.min)
                else:
                    sched_due = date

                p_due = p.due_date if (p and p.due_date) else sched_due
                new_note = db_mod.build_installment_note(
                    is_paid=True, due_date=p_due, paid_date=date,
                    user_note=note, staff_name=s_name, is_partial=is_partial
                )

                if p:
                    if pay_now < p.amount:
                        balance = p.amount - pay_now
                        p.amount = pay_now
                        p.is_paid = True
                        p.paid_date = date
                        p.staff_id = staff_id
                        p.is_staff_settled = False
                        p.note = new_note
                        new_unpaid = db_mod.Payment(
                            subscriber_id=self.sub_id,
                            amount=balance,
                            due_date=p.due_date,
                            is_paid=False,
                            cycle_number=curr_c,
                            installment_number=curr_i,
                            note=db_mod.build_installment_note(is_paid=False, due_date=p.due_date, is_partial=True)
                        )
                        self.db.add(new_unpaid)
                        remaining = 0
                    else:
                        p.amount = pay_now
                        p.is_paid = True
                        p.paid_date = date
                        p.staff_id = staff_id
                        p.is_staff_settled = False
                        p.note = new_note
                        remaining -= pay_now
                else:
                    new_paid = db_mod.Payment(
                        subscriber_id=self.sub_id,
                        amount=pay_now,
                        due_date=sched_due,
                        paid_date=date,
                        is_paid=True,
                        cycle_number=curr_c,
                        installment_number=curr_i,
                        note=new_note,
                        staff_id=staff_id,
                        is_staff_settled=False
                    )
                    self.db.add(new_paid)
                    lookup[(curr_c, curr_i)] = new_paid

                    if pay_now < cat_amount:
                        new_unpaid = db_mod.Payment(
                            subscriber_id=self.sub_id,
                            amount=cat_amount - pay_now,
                            due_date=sched_due,
                            is_paid=False,
                            cycle_number=curr_c,
                            installment_number=curr_i,
                            note=db_mod.build_installment_note(is_paid=False, due_date=sched_due, is_partial=True)
                        )
                        self.db.add(new_unpaid)
                        remaining = 0
                    else:
                        remaining -= pay_now

                processed += 1
                curr_i += 1
                if curr_i > max_i:
                    curr_i = 1
                    curr_c += 1

        self.db.commit()
        return processed

    def edit_payment(self, pid):
        p = self.db.get(db_mod.Payment, pid)
        sub = self.db.get(db_mod.Subscriber, self.sub_id)
        cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first() if sub else None
        cat_amount = float(cat.amount or 0) if cat else 0.0
        max_c = max(1, int(cat.max_cycles or 10)) if cat else 10
        max_i = max(1, int(cat.max_installments or 24)) if cat else 24

        staff_list = self.db.query(db_mod.Staff).all()
        
        dialog = PaymentDialog(self, p, max_cycles=max_c, max_inst=max_i, staff_list=staff_list)
        if dialog.exec():
            try:
                entered_amount = float(dialog.ent_amount.text().strip())
                is_paid = (dialog.cb_paid.currentIndex() == 1)
                cycle = int(dialog.cb_cycle.currentText() or 1)
                inst = int(dialog.cb_inst.currentText() or 1)
                date = datetime.datetime.combine(dialog.ent_date.date().toPyDate(), datetime.time.min)
                note = dialog.ent_note.text().strip()
                staff_id = dialog.cb_staff.currentData()

                p.amount = entered_amount
                p.due_date = date
                p.is_paid = is_paid
                p.paid_date = date if is_paid else None
                p.installment_number = inst
                p.cycle_number = cycle
                p.note = note
                p.staff_id = staff_id
                if is_paid:
                    p.is_staff_settled = False
                self.db.commit()
                self._changes_made = True
                self.load_payments()
            except Exception as e:
                try:
                    self.db.rollback()
                except Exception:
                    pass
                ModernDialog(self, "خطأ", f"بيانات غير صحيحة: {e}").exec()

    def show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0: return
        
        pid = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        
        act_edit = QAction("تعديل", self)
        act_edit.triggered.connect(lambda: self.edit_payment(pid))
        
        act_del = QAction("حذف", self)
        act_del.triggered.connect(lambda: self.delete_payment(pid))

        act_pay_multi = QAction("تسديد العمليات المختارة", self)
        act_pay_multi.triggered.connect(self.pay_selected_payments)
        
        act_del_multi = QAction("حذف العمليات المختارة", self)
        act_del_multi.triggered.connect(self.delete_selected_payments)
        
        menu.addAction(act_edit)
        menu.addAction(act_del)
        menu.addSeparator()
        menu.addAction(act_pay_multi)
        menu.addAction(act_del_multi)
        menu.exec(QCursor.pos())

    def pay_selected_payments(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            ModernDialog(self, "تنبيه", "يرجى اختيار قسط واحد على الأقل لتسديده").exec()
            return

        payment_ids = []
        for index in selected_rows:
            item = self.table.item(index.row(), 0)
            if item:
                pid = item.data(Qt.ItemDataRole.UserRole)
                if pid is not None:
                    payment_ids.append(pid)

        if not payment_ids:
            ModernDialog(self, "تنبيه", "لم يتم العثور على أقساط صالحة للتسديد").exec()
            return

        count = len(payment_ids)
        if not ModernDialog(self, "تأكيد التسديد", f"هل تريد تسديد {count} قسط محدد الآن؟", is_confirm=True).exec():
            return

        try:
            staff = getattr(self.parent(), 'logged_in_staff', None)
            staff_id = staff.id if staff else None
            s_name = staff.name if staff else None
            now_dt = datetime.datetime.now()

            payments = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.id.in_(payment_ids)
            ).all()

            paid_count = 0
            for p in payments:
                p.is_paid = True
                p.paid_date = now_dt
                p.staff_id = staff_id
                p.is_staff_settled = False
                p.note = db_mod.build_installment_note(
                    is_paid=True, due_date=p.due_date, paid_date=now_dt, staff_name=s_name
                )
                paid_count += 1

            self.db.commit()
            self._changes_made = True
            self.load_payments()
            ModernDialog(self, "نجاح", f"تم تسديد {paid_count} قسط بنجاح").exec()
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء تسديد الأقساط: {e}").exec()

    def delete_payment(self, pid):
        if ModernDialog(self, "تأكيد", "هل تريد حذف هذه العملية؟", is_confirm=True).exec():
            self._execute_delete_payments_sync([pid])

    def delete_selected_payments(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            ModernDialog(self, "تنبيه", "يرجى اختيار عملية واحدة على الأقل").exec()
            return
            
        payment_ids = []
        for index in selected_rows:
            item = self.table.item(index.row(), 0)
            if item:
                pid = item.data(Qt.ItemDataRole.UserRole)
                if pid is not None:
                    payment_ids.append(pid)

        if not payment_ids:
            ModernDialog(self, "تنبيه", "لم يتم العثور على عمليات صالحة للحذف").exec()
            return

        count = len(payment_ids)
        if ModernDialog(self, "تأكيد", f"هل تريد حذف {count} عملية مختارة؟", is_confirm=True).exec():
            self._execute_delete_payments_sync(payment_ids)

    def _execute_delete_payments_sync(self, payment_ids):
        try:
            objs = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.id.in_(payment_ids)
            ).all()
            deleted_count = len(objs)
            for obj in objs:
                self.db.delete(obj)
            self.db.commit()
            self._changes_made = True
            self.load_payments()
            ModernDialog(self, "نجاح", f"تم حذف {deleted_count} عملية بنجاح").exec()
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء الحذف: {e}").exec()


class _SmartPaymentWorker(QThread):
    """Worker thread لتوزيع وتسديد مبلغ كبير على الأقساط في الخلفية بسرعة فائقة مع شريط تقدم"""
    progress = pyqtSignal(int, int, str)  # (processed_so_far, est_total, msg)
    finished = pyqtSignal(int)            # total_processed
    error    = pyqtSignal(str)

    def __init__(self, db_url, sub_id, total_amount, cycle, inst, date, note, cat_amount, max_c, max_i, staff_id=None):
        super().__init__()
        self.db_url       = db_url
        self.sub_id       = sub_id
        self.total_amount = total_amount
        self.cycle        = cycle
        self.inst         = inst
        self.date         = date
        self.note         = note
        self.cat_amount   = cat_amount
        self.max_c        = max_c
        self.max_i        = max_i
        self.staff_id     = staff_id

    def run(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        kw = {"check_same_thread": False} if "sqlite" in self.db_url else {}
        engine  = create_engine(self.db_url, connect_args=kw)
        Session = sessionmaker(bind=engine)
        db      = Session()
        try:
            sub = db.get(db_mod.Subscriber, self.sub_id)
            staff_obj = db.get(db_mod.Staff, self.staff_id) if self.staff_id else None
            s_name = staff_obj.name if staff_obj else None

            cat = db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first() if sub else None
            cat_start = (cat.start_date.date() if hasattr(cat.start_date, 'date') else cat.start_date) if (cat and cat.start_date) else None

            est_total = max(1, int(self.total_amount // self.cat_amount) + (1 if self.total_amount % self.cat_amount > 0 else 0)) if self.cat_amount > 0 else 1
            remaining = self.total_amount
            processed = 0

            # جلب جميع أقساط المشترك في استعلام واحد فقط إلى الذاكرة لتجنب الاستعلامات المتكررة داخل الحلقات
            all_sub_payments = db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == self.sub_id
            ).order_by(
                db_mod.Payment.cycle_number.asc(),
                db_mod.Payment.installment_number.asc()
            ).all()

            targets = [p for p in all_sub_payments if not p.is_paid]
            last_processed_c = 0
            last_processed_i = 0

            # 1. توزيع المبلغ على الأقساط غير المسددة الموجودة أولاً (FIFO)
            for p in targets:
                if remaining <= 0:
                    break

                if remaining < p.amount:
                    balance = p.amount - remaining
                    p.amount = remaining
                    p.is_paid = True
                    p.paid_date = self.date
                    p.staff_id = self.staff_id
                    p.is_staff_settled = False
                    p.note = db_mod.build_installment_note(
                        is_paid=True, due_date=p.due_date, paid_date=self.date,
                        user_note=self.note, staff_name=s_name, is_partial=True
                    )
                    new_unpaid = db_mod.Payment(
                        subscriber_id=self.sub_id,
                        amount=balance,
                        due_date=p.due_date,
                        is_paid=False,
                        cycle_number=p.cycle_number,
                        installment_number=p.installment_number,
                        note=db_mod.build_installment_note(is_paid=False, due_date=p.due_date, is_partial=True)
                    )
                    db.add(new_unpaid)
                    all_sub_payments.append(new_unpaid)
                    remaining = 0
                else:
                    pay_now = p.amount
                    p.is_paid = True
                    p.paid_date = self.date
                    p.staff_id = self.staff_id
                    p.is_staff_settled = False
                    p.note = db_mod.build_installment_note(
                        is_paid=True, due_date=p.due_date, paid_date=self.date,
                        user_note=self.note, staff_name=s_name
                    )
                    remaining -= pay_now

                last_processed_c = p.cycle_number
                last_processed_i = p.installment_number
                processed += 1
                self.progress.emit(processed, est_total, f"جاري تسديد الدورة {p.cycle_number} — القسط {p.installment_number} ({processed}/{est_total})")

            # 2. إذا بقي رصيد، نكمل للأمام باستخدام القاموس في الذاكرة دون استعلام شبكي لكل قسط
            if remaining > 0:
                lookup = {(p.cycle_number, p.installment_number): p for p in all_sub_payments}
                if last_processed_c > 0:
                    curr_c, curr_i = last_processed_c, last_processed_i + 1
                    if curr_i > self.max_i:
                        curr_i = 1
                        curr_c += 1
                else:
                    curr_c, curr_i = self.cycle, self.inst

                safety_counter = 0
                max_safety = self.max_c * self.max_i

                while remaining > 0 and curr_c <= self.max_c and safety_counter < max_safety:
                    safety_counter += 1
                    p = lookup.get((curr_c, curr_i))

                    if p and p.is_paid:
                        curr_i += 1
                        if curr_i > self.max_i:
                            curr_i = 1
                            curr_c += 1
                        continue

                    pay_now = min(remaining, self.cat_amount)
                    is_partial = (pay_now < self.cat_amount)

                    if cat_start:
                        day_offset = (curr_c - 1) * self.max_i + (curr_i - 1)
                        sched_due = datetime.datetime.combine(cat_start + datetime.timedelta(days=day_offset), datetime.time.min)
                    else:
                        sched_due = self.date

                    p_due = p.due_date if (p and p.due_date) else sched_due
                    new_note = db_mod.build_installment_note(
                        is_paid=True, due_date=p_due, paid_date=self.date,
                        user_note=self.note, staff_name=s_name, is_partial=is_partial
                    )

                    if p:
                        if pay_now < p.amount:
                            balance = p.amount - pay_now
                            p.amount = pay_now
                            p.is_paid = True
                            p.paid_date = self.date
                            p.staff_id = self.staff_id
                            p.is_staff_settled = False
                            p.note = new_note
                            new_unpaid = db_mod.Payment(
                                subscriber_id=self.sub_id,
                                amount=balance,
                                due_date=p.due_date,
                                is_paid=False,
                                cycle_number=curr_c,
                                installment_number=curr_i,
                                note=db_mod.build_installment_note(is_paid=False, due_date=p.due_date, is_partial=True)
                            )
                            db.add(new_unpaid)
                            remaining = 0
                        else:
                            p.amount = pay_now
                            p.is_paid = True
                            p.paid_date = self.date
                            p.staff_id = self.staff_id
                            p.is_staff_settled = False
                            p.note = new_note
                            remaining -= pay_now
                    else:
                        new_paid = db_mod.Payment(
                            subscriber_id=self.sub_id,
                            amount=pay_now,
                            due_date=sched_due,
                            paid_date=self.date,
                            is_paid=True,
                            cycle_number=curr_c,
                            installment_number=curr_i,
                            note=new_note,
                            staff_id=self.staff_id,
                            is_staff_settled=False
                        )
                        db.add(new_paid)
                        lookup[(curr_c, curr_i)] = new_paid

                        if pay_now < self.cat_amount:
                            new_unpaid = db_mod.Payment(
                                subscriber_id=self.sub_id,
                                amount=self.cat_amount - pay_now,
                                due_date=sched_due,
                                is_paid=False,
                                cycle_number=curr_c,
                                installment_number=curr_i,
                                note=db_mod.build_installment_note(is_paid=False, due_date=sched_due, is_partial=True)
                            )
                            db.add(new_unpaid)
                            remaining = 0
                        else:
                            remaining -= pay_now

                    processed += 1
                    self.progress.emit(processed, max(est_total, processed), f"جاري تسديد الدورة {curr_c} — القسط {curr_i} ({processed}/{max(est_total, processed)})")

                    curr_i += 1
                    if curr_i > self.max_i:
                        curr_i = 1
                        curr_c += 1

            db.commit()
            self.finished.emit(processed)
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            self.error.emit(str(e))
        finally:
            db.close()


class _PaySelectedPaymentsWorker(QThread):
    """Worker thread لتسديد الأقساط المحددة على دفعات في الخلفية مع شريط تقدم"""
    progress = pyqtSignal(int, int)  # (paid_so_far, total)
    finished = pyqtSignal(int)       # total_paid
    error    = pyqtSignal(str)

    def __init__(self, db_url, payment_ids, staff_id=None):
        super().__init__()
        self.db_url      = db_url
        self.payment_ids = list(payment_ids)
        self.staff_id    = staff_id

    def run(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        kw = {"check_same_thread": False} if "sqlite" in self.db_url else {}
        engine  = create_engine(self.db_url, connect_args=kw)
        Session = sessionmaker(bind=engine)
        db      = Session()
        try:
            total = len(self.payment_ids)
            staff_obj = db.get(db_mod.Staff, self.staff_id) if self.staff_id else None
            s_name = staff_obj.name if staff_obj else None
            now_dt = datetime.datetime.now()

            payments = db.query(db_mod.Payment).filter(
                db_mod.Payment.id.in_(self.payment_ids)
            ).all()

            paid_so_far = 0
            for idx, p in enumerate(payments, 1):
                p.is_paid = True
                p.paid_date = now_dt
                p.staff_id = self.staff_id
                p.is_staff_settled = False
                p.note = db_mod.build_installment_note(
                    is_paid=True, due_date=p.due_date, paid_date=now_dt, staff_name=s_name
                )
                paid_so_far += 1
                if idx % 10 == 0 or idx == len(payments):
                    db.commit()
                    self.progress.emit(paid_so_far, total)

            self.finished.emit(paid_so_far)
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            self.error.emit(str(e))
        finally:
            db.close()


class _DeletePaymentsWorker(QThread):
    """Worker thread لحذف الأقساط المحددة على دفعات في الخلفية مع شريط تقدم دون تجميد الواجهة"""
    progress = pyqtSignal(int, int)  # (deleted_so_far, total)
    finished = pyqtSignal(int)       # total_deleted
    error    = pyqtSignal(str)

    def __init__(self, db_url, payment_ids):
        super().__init__()
        self.db_url = db_url
        self.payment_ids = list(payment_ids)

    def run(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        kw = {"check_same_thread": False} if "sqlite" in self.db_url else {}
        engine  = create_engine(self.db_url, connect_args=kw)
        Session = sessionmaker(bind=engine)
        db      = Session()
        try:
            total = len(self.payment_ids)
            # تقسيم الحذف إلى دفعات صغيرة لتحديث شريط التقدم بسلاسة وسرعة عالية
            chunk_size = max(1, min(20, (total // 5) or 1))
            deleted_so_far = 0

            for i in range(0, total, chunk_size):
                chunk = self.payment_ids[i:i + chunk_size]
                db.query(db_mod.Payment).filter(
                    db_mod.Payment.id.in_(chunk)
                ).delete(synchronize_session=False)
                db.commit()
                deleted_so_far += len(chunk)
                self.progress.emit(deleted_so_far, total)

            self.finished.emit(deleted_so_far)
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            self.error.emit(str(e))
        finally:
            db.close()

class StaffActivityDialog(QDialog):
    def __init__(self, parent, staff_id, db):
        super().__init__(parent)
        self.staff_id = staff_id
        self.db = db
        staff = db.get(db_mod.Staff, staff_id)
        
        self.setWindowTitle(f"سجل تحصيلات الموظف - {staff.name}")
        fit_dialog_to_screen(self, 800, 550)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        title = QLabel(f"كشف المقبوضات المحصلة بواسطة: {staff.name}")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        
        # إضافة أدوات تصفية التاريخ
        filter_lay = QHBoxLayout()
        filter_lay.addWidget(QLabel("من تاريخ:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1)) # الافتراضي: قبل شهر
        self.date_from.dateChanged.connect(self.load_data)
        filter_lay.addWidget(self.date_from)

        filter_lay.addWidget(QLabel("إلى تاريخ:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self.load_data)
        filter_lay.addWidget(self.date_to)

        self.chk_show_settled = QCheckBox("عرض العمليات المسلمة سابقاً")
        self.chk_show_settled.stateChanged.connect(self.load_data)
        filter_lay.addWidget(self.chk_show_settled)

        filter_lay.addStretch()
        layout.addLayout(filter_lay)

        summary_lay = QHBoxLayout()
        self.lbl_total = QLabel("إجمالي المبالغ المحصلة: 0.00 ر.ي")
        self.lbl_total.setStyleSheet("font-size: 16px; font-weight: bold; color: #10b981; background: #f8fafc; padding: 12px; border-radius: 10px; border: 1px solid #e2e8f0;")
        summary_lay.addWidget(self.lbl_total)
        summary_lay.addStretch()

        btn_pdf = QPushButton("تصدير PDF")
        btn_pdf.setObjectName("DangerBtn")
        btn_pdf.setFixedWidth(120)
        btn_pdf.clicked.connect(self.export_to_pdf)
        summary_lay.addWidget(btn_pdf)

        self.btn_settle = QPushButton("تصفير السجل (تسليم للإدارة)")
        self.btn_settle.setObjectName("PrimaryBtn")
        self.btn_settle.setFixedWidth(180)
        self.btn_settle.clicked.connect(self.settle_payments)
        summary_lay.addWidget(self.btn_settle)

        layout.addLayout(summary_lay)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["اسم المشترك", "المبلغ المحصل", "تاريخ العملية", "ملاحظات"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        self.load_data()

    def load_data(self):
        # تحويل التاريخ من QDate إلى datetime لتوافقه مع قاعدة البيانات
        self.db.rollback() # لضمان تحديث لقطة قاعدة البيانات ورؤية تسديدات الموقع
        self.db.expire_all()
        start_date = datetime.datetime.combine(self.date_from.date().toPyDate(), datetime.time.min)
        end_date = datetime.datetime.combine(self.date_to.date().toPyDate(), datetime.time.max)

        query = self.db.query(db_mod.Payment, db_mod.Subscriber).join(db_mod.Subscriber).filter(
            db_mod.Payment.staff_id == self.staff_id,
            db_mod.Payment.paid_date >= start_date,
            db_mod.Payment.paid_date <= end_date
        )

        # إذا لم يتم تفعيل خيار "عرض المسلمة"، نظهر فقط العهدة الحالية
        if self.chk_show_settled.isChecked():
            pass # نظهر الكل
        else:
            query = query.filter(db_mod.Payment.is_staff_settled == False)

        results = query.order_by(db_mod.Payment.paid_date.desc()).all()

        self.table.setRowCount(len(results))
        total = 0
        for i, (p, sub) in enumerate(results):
            self.table.setItem(i, 0, QTableWidgetItem(sub.name if sub else "غير معروف"))
            self.table.setItem(i, 1, QTableWidgetItem(f"{p.amount:,.2f} ر.ي"))
            self.table.setItem(i, 2, QTableWidgetItem(p.paid_date.strftime("%Y-%m-%d %H:%M") if p.paid_date else "-"))
            self.table.setItem(i, 3, QTableWidgetItem(p.note or "-"))
            total += p.amount
        self.lbl_total.setText(f"إجمالي المبالغ المحصلة: {total:,.2f} ر.ي")
        self.btn_settle.setEnabled(total > 0 and not self.chk_show_settled.isChecked())

    def settle_payments(self):
        start_date = datetime.datetime.combine(self.date_from.date().toPyDate(), datetime.time.min)
        end_date = datetime.datetime.combine(self.date_to.date().toPyDate(), datetime.time.max)
        
        count = self.table.rowCount()
        msg = f"هل أنت متأكد من تصفير السجل؟\nسيتم اعتبار {count} عملية قد سُلمت للإدارة ولن تظهر في الكشف الحالي للموظف."
        
        if ModernDialog(self, "تأكيد تسليم المبالغ", msg, is_confirm=True).exec():
            try:
                # جلب الأقساط غير المسواة حالياً ضمن الفلتر
                payments = self.db.query(db_mod.Payment).filter(
                    db_mod.Payment.staff_id == self.staff_id,
                    db_mod.Payment.paid_date >= start_date,
                    db_mod.Payment.paid_date <= end_date,
                    db_mod.Payment.is_staff_settled == False
                ).all()
                
                for p in payments:
                    p.is_staff_settled = True
                
                self.db.commit()
                self.load_data()
                ModernDialog(self, "نجاح", "تم تصفير السجل بنجاح.").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"فشل التصفير: {e}").exec()

    def export_to_pdf(self):
        try:
            # جلب البيانات المفلترة بنفس المنطق المستخدم في الجدول
            start_date = datetime.datetime.combine(self.date_from.date().toPyDate(), datetime.time.min)
            end_date = datetime.datetime.combine(self.date_to.date().toPyDate(), datetime.time.max)

            payments = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.staff_id == self.staff_id,
                db_mod.Payment.paid_date >= start_date,
                db_mod.Payment.paid_date <= end_date
            ).order_by(db_mod.Payment.paid_date.desc()).all()

            if not payments:
                ModernDialog(self, "تنبيه", "لا توجد عمليات تحصيل لتصديرها في هذه الفترة").exec()
                return

            staff = self.db.get(db_mod.Staff, self.staff_id)
            filename, _ = QFileDialog.getSaveFileName(
                self, "حفظ كشف تحصيلات الموظف (PDF)", 
                f"staff_report_{staff.name}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf", 
                "PDF Files (*.pdf)"
            )
            if not filename: return

            c = canvas.Canvas(filename, pagesize=A4)
            width, height = A4
            
            font_path = "C:/Windows/Fonts/arial.ttf"
            try: pdfmetrics.registerFont(TTFont('ArabicFont', font_path)); c.setFont('ArabicFont', 10)
            except: c.setFont('Helvetica', 10)

            # تصميم الهيدر (Header)
            c.setFillColor(colors.HexColor("#0a3d0e"))
            c.rect(0, height - 80, width, 80, fill=1)
            c.setFillColor(colors.white)
            c.setFont('ArabicFont', 18)
            c.drawCentredString(width/2, height - 40, reshape_text(f"كشف تحصيلات الموظف: {staff.name}"))
            c.setFont('ArabicFont', 10)
            date_range = f"الفترة من: {start_date.strftime('%Y-%m-%d')} إلى: {end_date.strftime('%Y-%m-%d')}"
            c.drawCentredString(width/2, height - 60, reshape_text(date_range))
            
            c.setFillColor(colors.black)
            y = height - 120
            headers = ["اسم المشترك", "المبلغ المحصل", "تاريخ العملية", "ملاحظات"]
            col_x = [40, 200, 300, 420] 
            
            c.setFillColor(colors.HexColor("#f1f5f9"))
            c.rect(35, y - 5, width - 70, 20, fill=1)
            c.setFillColor(colors.black)
            for i, h in enumerate(headers): c.drawString(col_x[i], y, reshape_text(h))
            
            y -= 25
            total_sum = 0
            for idx, p in enumerate(payments):
                if y < 60:
                    c.showPage()
                    y = height - 60
                    try: c.setFont('ArabicFont', 10)
                    except: pass
                
                if idx % 2 == 1:
                    c.setFillColor(colors.HexColor("#f8fafc"))
                    c.rect(35, y - 5, width - 70, 18, fill=1)
                
                c.setFillColor(colors.black)
                sub = self.db.get(db_mod.Subscriber, p.subscriber_id)
                c.drawString(col_x[0], y, reshape_text((sub.name if sub else "غير معروف")[:30]))
                c.drawString(col_x[1], y, f"{p.amount:,.2f} ر.ي")
                c.drawString(col_x[2], y, p.paid_date.strftime("%Y-%m-%d %H:%M"))
                c.drawString(col_x[3], y, reshape_text((p.note or "-")[:25]))
                
                total_sum += p.amount
                y -= 20
            
            c.line(35, y + 10, width - 35, y + 10)
            c.setFont('ArabicFont', 12)
            c.drawString(col_x[0], y, reshape_text(f"إجمالي المبالغ المحصلة: {total_sum:,.2f} ر.ي"))
            
            c.save()
            ModernDialog(self, "نجاح", f"تم تصدير كشف التحصيلات بنجاح.").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء تصدير PDF: {e}").exec()

