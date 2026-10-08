import sys
import warnings
import os
import subprocess
import threading
import re
import datetime
import random
import time
import shutil
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QStackedWidget, QFrame, QScrollArea, 
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QDialog, QFormLayout, QRadioButton, QButtonGroup,
    QCheckBox,QAbstractItemView, QMenu, QTextEdit, QTabWidget,
    QListWidget, QListWidgetItem, QDateEdit, QGridLayout,
    QFileDialog, QSystemTrayIcon
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject, QThread, QDate, QTimer, QPoint
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette, QCursor
from sqlalchemy.orm import Session
from sqlalchemy import func
import database as db_mod

# كتم تحذير pkg_resources الخاص بمكتبة win10toast لتجنب الإزعاج في سطر الأوامر
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")

import security
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Imported GUI Modules ---
from gui.styles import HAKBAH_LIGHT, HAKBAH_DARK
from gui.utils import reshape_text, ServerWorker
from gui.dialogs import (
    ModernDialog, DrawAnimationDialog, SubscriberEditDialog, CategoryEditDialog,
    PaymentDialog, AddSubscriberDialog, BatchPaymentDialog, AccountDetailsDialog,
    LoginDialog, SetupAdminDialog
)
from gui.pages.dashboard import DashboardMixin
from gui.pages.subscribers import SubscribersMixin
from gui.pages.settings import SettingsMixin
from gui.pages.capital import CapitalMixin
from gui.pages.reports import ReportsMixin
from gui.pages.draw import DrawMixin
from gui.pages.cycles import CyclesMixin
from gui.pages.messaging import MessagingMixin
from gui.pages.staff import StaffMixin

class AdminApp(QMainWindow, DashboardMixin, SubscribersMixin, SettingsMixin, CapitalMixin, ReportsMixin, DrawMixin, CyclesMixin, MessagingMixin, StaffMixin):
    def __init__(self, staff=None):
        super().__init__()
        self.logged_in_staff = staff
        self.setWindowTitle("لوحة تحكم هكبة المليون - Hakbah million")
        self.resize(1300, 850)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        # تعيين أيقونة البرنامج وتحميلها مرة واحدة بشكل آمن
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        # البحث عن الأيقونة في المسارات المحتملة
        possible_icon_paths = [
            os.path.join(base_path, "static", "logo.png"),
            os.path.join(base_path, "logo.png")
        ]
        icon_path = next((path for path in possible_icon_paths if os.path.exists(path)), None)
        self.app_icon = QIcon(icon_path) if icon_path else QIcon()

        if os.path.exists(icon_path):
            # حل مشكلة عدم ظهور الأيقونة في شريط مهام ويندوز عند التشغيل عبر Python
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("hakbah.million.admin.v1")

        self.setWindowIcon(self.app_icon)

        self.db = db_mod.SessionLocal()
        self.public_url = ""
        
        # تأكد من إغلاق الجلسة عند إغلاق البرنامج
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.access_granted = False

        if not self.prompt_admin_access():
            return

        self.access_granted = True

        self.setup_ui()
        self.apply_styles()
        self.update_logged_in_user()
        self.show_dashboard()
        
        # تشغيل فحص الأقساط المتأخرة تلقائياً عند بدء البرنامج وكل ساعة
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_unpaid_installments)
        self.sync_timer.start(3600000) # 3600000 مللي ثانية = 1 ساعة
        QTimer.singleShot(2000, self.sync_unpaid_installments) # تشغيل أول مرة بعد ثانيتين من الفتح

        try:
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(self.app_icon)
            self.tray_icon.show()
        except Exception:
            self.tray_icon = None

    def closeEvent(self, event):
        self.db.close()
        super().closeEvent(event)

    def apply_styles(self):
        theme_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "admin_theme").first()
        theme = theme_setting.value if theme_setting else "dark"
        self.setStyleSheet(HAKBAH_DARK if theme == "dark" else HAKBAH_LIGHT)

    def get_setting_bool(self, key, default=False):
        setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
        if not setting:
            return default
        return str(setting.value).lower() in ("1", "true", "yes", "on")

    def update_logged_in_user(self):
        if hasattr(self, 'lbl_current_user'):
            if self.logged_in_staff:
                self.lbl_current_user.setText(f"مرحباً، {self.logged_in_staff.name or self.logged_in_staff.staff_id_code}")
            else:
                self.lbl_current_user.setText("")

    def prompt_admin_access(self):
        if self.logged_in_staff:
            return True

        # Allow skipping admin prompt in development/debug by setting env var
        try:
            if os.environ.get("SKIP_ADMIN_PROMPT", "0").lower() in ("1", "true", "yes"):
                return True
        except Exception:
            pass

        db = db_mod.SessionLocal()
        try:
            # Attempt to check for staff, but handle failure gracefully on first run
            has_staff = db.query(db_mod.Staff).first() is not None
            pw_setting = db.query(db_mod.Setting).filter(db_mod.Setting.key == "require_login_password").first()
            require_password = (pw_setting and pw_setting.value == "1")
        except Exception as e:
            # If tables don't exist yet, assume we need to create the first admin
            print(f"Initial DB check failed (this is normal on first run): {e}")
            has_staff = False
            require_password = True
        finally:
            db.close()

        # إذا لم يكن هناك موظفون بعد، أنشئ حساب المدير الأول
        if not has_staff:
            setup_dialog = SetupAdminDialog()
            if setup_dialog.exec() != QDialog.DialogCode.Accepted:
                return False

            admin_data = setup_dialog.admin_data
            new_staff = db_mod.Staff(
                name=admin_data["name"],
                staff_id_code=admin_data["staff_id_code"],
                password=security.hash_password(admin_data["password"]),
                role="مدير"
            )
            self.db.add(new_staff)
            # Make sure to set the default setting for future runs just in case
            setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "require_login_password").first()
            if not setting:
                self.db.add(db_mod.Setting(key="require_login_password", value="0"))
            self.db.commit()
            self.logged_in_staff = new_staff
            return True

        # إذا كانت كلمة المرور مُلغاة، تجاوز واجهة تسجيل الدخول وادخل كمدير
        if not require_password:
            inner_db = db_mod.SessionLocal()
            try:
                admin = inner_db.query(db_mod.Staff).filter(db_mod.Staff.role == "مدير").first()
                if not admin:
                    admin = inner_db.query(db_mod.Staff).first()
                self.logged_in_staff = admin
            except Exception:
                self.logged_in_staff = None
            finally:
                inner_db.close()
            return True

        login_dialog = LoginDialog()
        if login_dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        self.logged_in_staff = login_dialog.staff
        return True

    def set_theme(self, theme_name):
        theme_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "admin_theme").first()
        if not theme_setting:
            self.db.add(db_mod.Setting(key="admin_theme", value=theme_name))
        else:
            theme_setting.value = theme_name
        self.db.commit()
        self.apply_styles()
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(20, 40, 20, 20)
        sidebar_layout.setSpacing(15)

        logo = QLabel("هكبة المليون")
        logo.setStyleSheet("font-size: 26px; font-weight: 800; color: #ffffff; margin-bottom: 30px;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo)

        self.nav_btns = {}
        nav_items = [
            ("الإحصائيات", self.show_dashboard), 
            ("المشتركين", self.show_subscribers), 
            ("إدارة الدورات والأقساط", self.show_cycles),
            ("إدارة رأس المال", self.show_capital_management),
            ("إدارة السحوبات", self.show_draw_management),
            ("إدارة الرسائل والتوعية", self.show_messaging_management),
            ("الموظفين", self.show_staff_management),
            ("أداة التقارير", self.show_reports),
            ("الإعدادات", self.show_main_settings)
        ]
        
        for text, nav_func in nav_items:
            btn = QPushButton(text)
            btn.clicked.connect(nav_func)
            sidebar_layout.addWidget(btn)
            self.nav_btns[text] = btn

        sidebar_layout.addStretch()
        
        btn_exit = QPushButton("خروج من البرنامج")
        btn_exit.setObjectName("DangerBtn")
        btn_exit.clicked.connect(self.close)
        sidebar_layout.addWidget(btn_exit)

        main_layout.addWidget(self.sidebar)

        # Right Side (Content + Header)
        right_side_container = QWidget()
        right_side_layout = QVBoxLayout(right_side_container)
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side_layout.setSpacing(0)

        # Header Bar
        self.header_bar = QFrame()
        self.header_bar.setFixedHeight(50)
        self.header_bar.setStyleSheet("background-color: transparent; border-bottom: 1px solid #e2e8f0;")
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        self.btn_toggle_sidebar = QPushButton("☰")
        self.btn_toggle_sidebar.setFixedSize(40, 40)
        self.btn_toggle_sidebar.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                color: #64748b;
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                color: #3b82f6;
                background-color: #f1f5f9;
                border-radius: 5px;
            }
        """)
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        self.btn_toggle_sidebar.setCursor(Qt.CursorShape.PointingHandCursor)
        
        header_layout.addWidget(self.btn_toggle_sidebar)
        header_layout.addStretch()

        # Theme Switch Button
        self.btn_theme = QPushButton()
        self.btn_theme.setFixedSize(45, 45)
        self.btn_theme.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                color: #10b981;
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #d1fae5;
                border-radius: 8px;
            }
        """)
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)

        # Notifications Button
        self.btn_notifications = QPushButton("🔔")
        self.btn_notifications.setFixedHeight(45)
        self.btn_notifications.setMinimumWidth(45)
        self.btn_notifications.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                color: #10b981;
                background: transparent;
                border: none;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #d1fae5;
                border-radius: 8px;
            }
        """)
        self.btn_notifications.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_notifications.clicked.connect(self.show_notifications_menu)

        # Set initial icon for theme
        theme_setting_val = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "admin_theme").first()
        current_theme_val = theme_setting_val.value if theme_setting_val else "dark"
        self.btn_theme.setText("🌙" if current_theme_val == "light" else "☀️")

        header_layout.addWidget(self.btn_theme)
        header_layout.addWidget(self.btn_notifications)

        self.lbl_current_user = QLabel("")
        self.lbl_current_user.setObjectName("PageTitle")
        self.lbl_current_user.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self.lbl_current_user)
        
        right_side_layout.addWidget(self.header_bar)

        # Content Area
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("ContentFrame")
        right_side_layout.addWidget(self.content_stack, 1)
        
        main_layout.addWidget(right_side_container, 1)

        # Initialize Pages
        self.page_dashboard = self.init_dashboard_page()
        self.page_subscribers = self.init_subscribers_page()
        self.page_settings = self.init_settings_page()
        self.page_company_settings = self.init_company_settings_page()
        self.page_cycles = self.init_cycles_page()
        self.page_capital = self.init_capital_page()
        self.page_messaging = self.init_messaging_page()
        self.page_reports = self.init_reports_page()
        self.page_draw = self.init_draw_page()
        self.page_staff = self.init_staff_page()

        self.page_main_settings = self.init_main_settings_page()

        self.content_stack.addWidget(self.page_dashboard)
        self.content_stack.addWidget(self.page_subscribers)
        self.content_stack.addWidget(self.page_cycles)
        self.content_stack.addWidget(self.page_capital)
        self.content_stack.addWidget(self.page_reports)
        self.content_stack.addWidget(self.page_draw)
        self.content_stack.addWidget(self.page_messaging)
        self.content_stack.addWidget(self.page_staff)
        self.content_stack.addWidget(self.page_main_settings)
    def _update_nav_style(self, active_text):
        for text, btn in self.nav_btns.items():
            if text == active_text: btn.setObjectName("NavBtnActive")
            else: btn.setObjectName("")
            btn.style().unpolish(btn); btn.style().polish(btn)

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def auto_refresh_current_page(self):
        """تحديث الصفحة النشطة حالياً لضمان مزامنة بيانات الموقع"""
        self.db.rollback() # إنهاء المعاملة الحالية لبدء واحدة جديدة ترى بيانات الموقع
        self.db.expire_all() # تحديث الجلسة لقراءة أي تغييرات من موقع الويب فوراً
        current_page = self.content_stack.currentWidget()
        
        # نقوم بالتحديث فقط إذا كان المستخدم فاتحاً لصفحة الإحصائيات أو المشتركين
        if current_page == self.page_dashboard:
            self.refresh_stats()
        elif current_page == self.page_subscribers:
            self.load_subscribers()
        elif current_page == self.page_capital:
            self.refresh_capital_stats()
        
        self.check_for_admin_notifications()

    def check_for_admin_notifications(self):
        """Checks for unread admin notifications and displays them."""
        unread_notifs = self.db.query(db_mod.AdminNotification).filter(
            db_mod.AdminNotification.is_read == False
        ).order_by(db_mod.AdminNotification.created_at.asc()).all()

        unread_count = len(unread_notifs)
        if hasattr(self, 'btn_notifications'):
            if unread_count > 0:
                self.btn_notifications.setText(f"🔔 ({unread_count})")
            else:
                self.btn_notifications.setText("🔔")

        if not hasattr(self, 'notified_tray_ids'):
            self.notified_tray_ids = set()

        for notif in unread_notifs:
            if notif.id not in self.notified_tray_ids:
                # تخصيص عنوان التنبيه بناءً على نوعه
                title = "إشعار جديد - هكبة المليون"
                if notif.type == "new_subscriber":
                    title = "تسجيل جديد 👤"
                elif notif.type == "payment_received":
                    title = "سداد مالي جديد 💰"

                if self.tray_icon:
                    self.tray_icon.showMessage(
                        title,
                        notif.message,
                        QSystemTrayIcon.MessageIcon.Information,
                        5000
                    )
                self.notified_tray_ids.add(notif.id)

    def toggle_theme(self):
        theme_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "admin_theme").first()
        current = theme_setting.value if theme_setting else "dark"
        new_theme = "light" if current == "dark" else "dark"
        self.set_theme(new_theme)
        self.btn_theme.setText("🌙" if new_theme == "light" else "☀️")

    def show_notifications_menu(self):
        menu = QMenu(self)
        theme_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "admin_theme").first()
        is_dark = (theme_setting and theme_setting.value == "dark")
        
        bg_color = "#1e293b" if is_dark else "#ffffff"
        text_color = "#f1f5f9" if is_dark else "#1e293b"
        hover_bg = "#334155" if is_dark else "#f8fafc"
        border_color = "#475569" if is_dark else "#cbd5e1"
        
        menu.setStyleSheet(f"""
            QMenu {{ background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 5px; color: {text_color}; }}
            QMenu::item {{ padding: 10px 20px; font-size: 13px; font-family: Tajawal; border-bottom: 1px solid {border_color}; }}
            QMenu::item:selected {{ background-color: {hover_bg}; color: #3b82f6; }}
        """)
        
        # Load unread notifications only
        notifs = self.db.query(db_mod.AdminNotification).filter(
            db_mod.AdminNotification.is_read == False
        ).order_by(db_mod.AdminNotification.created_at.desc()).all()
        
        if not notifs:
            act = QAction("لا توجد إشعارات غير مقروءة حالياً", self)
            act.setEnabled(False)
            menu.addAction(act)
        else:
            for n in notifs:
                title = "إشعار"
                if n.type == "new_subscriber":
                    title = "👤 مشترك جديد"
                elif n.type == "payment_received":
                    title = "💰 دفعة مستلمة"
                
                short_msg = (n.message[:40] + '..') if len(n.message) > 40 else n.message
                act = QAction(f"🔴 {title}: {short_msg}", self)
                act.triggered.connect(lambda checked, notif_id=n.id: self.mark_notification_read(notif_id))
                menu.addAction(act)
                
            menu.addSeparator()
            mark_all = QAction("✔️ تحديد الكل كمقروء", self)
            mark_all.triggered.connect(self.mark_all_notifications_read)
            menu.addAction(mark_all)

        pos = self.btn_notifications.mapToGlobal(QPoint(0, self.btn_notifications.height()))
        menu.exec(pos)

    def mark_notification_read(self, notif_id):
        notif = self.db.get(db_mod.AdminNotification, notif_id)
        if notif:
            notif.is_read = True
            self.db.commit()
            self.check_for_admin_notifications()
            
    def mark_all_notifications_read(self):
        self.db.query(db_mod.AdminNotification).filter(db_mod.AdminNotification.is_read == False).update({"is_read": True})
        self.db.commit()
        self.check_for_admin_notifications()

    def show_dashboard(self): self.content_stack.setCurrentWidget(self.page_dashboard); self._update_nav_style("الإحصائيات"); self.refresh_stats()
    def show_subscribers(self): self.content_stack.setCurrentWidget(self.page_subscribers); self._update_nav_style("المشتركين"); self.load_subscribers()
    def show_cycles(self): self.content_stack.setCurrentWidget(self.page_cycles); self._update_nav_style("إدارة الدورات والأقساط"); self.refresh_cycles_cat_list()
    def show_messaging_management(self): self.content_stack.setCurrentWidget(self.page_messaging); self._update_nav_style("إدارة الرسائل والتوعية"); self.load_subscriber_messages()
    
    def init_main_settings_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Settings Sidebar
        self.settings_sidebar = QListWidget()
        self.settings_sidebar.setFixedWidth(250)
        self.settings_sidebar.setStyleSheet("""
            QListWidget {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 10px;
            }
            QListWidget::item {
                padding: 15px;
                margin-bottom: 5px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                color: #334155;
            }
            QListWidget::item:selected {
                background-color: #3b82f6;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #e2e8f0;
            }
        """)

        self.settings_sidebar.addItem("إعدادات الشركة")
        self.settings_sidebar.addItem("إعدادات الفئات")
        self.settings_sidebar.addItem("إعدادات الأمان")
        self.settings_sidebar.addItem("إعدادات الانضباط المالي")

        # Inner Stack
        self.settings_stack = QStackedWidget()
        self.settings_stack.addWidget(self.page_company_settings)
        self.settings_stack.addWidget(self.page_settings)
        self.settings_stack.addWidget(self._build_security_settings_page())
        self.settings_stack.addWidget(self._build_financial_discipline_settings_page())

        layout.addWidget(self.settings_sidebar)
        layout.addWidget(self.settings_stack, 1)

        self.settings_sidebar.currentRowChanged.connect(self.on_settings_tab_changed)

        return page

    def get_setting(self, key, default=""):
        setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
        return setting.value if setting else default

    def _set_setting(self, key, value):
        setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
        if setting:
            setting.value = str(value)
        else:
            self.db.add(db_mod.Setting(key=key, value=str(value)))

    def _build_security_settings_page(self):
        """بناء صفحة إعدادات الأمان وحماية النظام."""
        page = QScrollArea()
        page.setWidgetResizable(True)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(25)

        title = QLabel("🔒  إعدادات الأمان وحماية النظام")
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        # -------------------------------------------------------------
        # CARD 1: إعدادات التحقق وتسجيل الدخول
        # -------------------------------------------------------------
        card_login = QFrame()
        card_login.setObjectName("StatCard")
        c1_lay = QVBoxLayout(card_login)
        c1_lay.setSpacing(16)
        c1_lay.setContentsMargins(25, 25, 25, 25)

        c1_title = QLabel("🛡️  سياسات التحقق وتسجيل الدخول")
        c1_title.setObjectName("SectionTitle")
        c1_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #3b82f6;")
        c1_lay.addWidget(c1_title)

        desc1 = QLabel(
            "يمكنك التحكم في اشتراط كلمة المرور عند فتح البرنامج، بالإضافة إلى تحديد سياسة القفل التلقائي ومحاولات الدخول."
        )
        desc1.setWordWrap(True)
        desc1.setStyleSheet("font-size: 13px; color: #64748b; line-height: 18px;")
        c1_lay.addWidget(desc1)

        self.chk_require_login = QCheckBox("تفعيل التحقق بكلمة المرور عند فتح البرنامج")
        self.chk_require_login.setStyleSheet("font-size: 15px; font-weight: 600; padding: 4px 0;")
        c1_lay.addWidget(self.chk_require_login)

        form_sec = QFormLayout()
        form_sec.setSpacing(14)

        self.combo_session_timeout = QComboBox()
        self.combo_session_timeout.addItems(["معطل (بدون قفل)", "5 دقائق", "10 دقائق", "15 دقيقة", "30 دقيقة", "60 دقيقة"])
        form_sec.addRow("القفل التلقائي عند الخمول:", self.combo_session_timeout)

        self.combo_max_attempts = QComboBox()
        self.combo_max_attempts.addItems(["3 محاولات", "5 محاولات", "10 محاولات", "غير محدود"])
        form_sec.addRow("الحد الأقصى لمحاولات الدخول الخاطئة:", self.combo_max_attempts)

        c1_lay.addLayout(form_sec)

        btn_save_general_sec = QPushButton("حفظ سياسات الدخول والأمان")
        btn_save_general_sec.setObjectName("PrimaryBtn")
        btn_save_general_sec.setFixedHeight(40)
        btn_save_general_sec.clicked.connect(self.save_security_settings)
        c1_lay.addWidget(btn_save_general_sec)

        lay.addWidget(card_login)

        # -------------------------------------------------------------
        # CARD 2: تغيير كلمة مرور المسؤول
        # -------------------------------------------------------------
        card_pwd = QFrame()
        card_pwd.setObjectName("StatCard")
        c2_lay = QVBoxLayout(card_pwd)
        c2_lay.setSpacing(16)
        c2_lay.setContentsMargins(25, 25, 25, 25)

        c2_title = QLabel("🔑  تغيير كلمة مرور المدير / المسؤول")
        c2_title.setObjectName("SectionTitle")
        c2_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #10b981;")
        c2_lay.addWidget(c2_title)

        desc2 = QLabel("قم بتعيين كلمة مرور قوية لحماية حساب المسؤول من الوصول غير المصرح به.")
        desc2.setStyleSheet("font-size: 13px; color: #64748b;")
        c2_lay.addWidget(desc2)

        form_pwd = QFormLayout()
        form_pwd.setSpacing(14)

        self.txt_curr_pwd = QLineEdit()
        self.txt_curr_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_curr_pwd.setPlaceholderText("أدخل كلمة المرور الحالية")
        form_pwd.addRow("كلمة المرور الحالية:", self.txt_curr_pwd)

        self.txt_new_pwd = QLineEdit()
        self.txt_new_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_new_pwd.setPlaceholderText("أدخل كلمة المرور الجديدة (6 خانات على الأقل)")
        form_pwd.addRow("كلمة المرور الجديدة:", self.txt_new_pwd)

        self.txt_confirm_pwd = QLineEdit()
        self.txt_confirm_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_confirm_pwd.setPlaceholderText("أعد إدخال كلمة المرور الجديدة للتأكيد")
        form_pwd.addRow("تأكيد كلمة المرور:", self.txt_confirm_pwd)

        c2_lay.addLayout(form_pwd)

        btn_change_pwd = QPushButton("تحديث كلمة المرور الآن")
        btn_change_pwd.setObjectName("PrimaryBtn")
        btn_change_pwd.setStyleSheet("background-color: #10b981; color: white; font-weight: bold;")
        btn_change_pwd.setFixedHeight(40)
        btn_change_pwd.clicked.connect(self.change_admin_password)
        c2_lay.addWidget(btn_change_pwd)

        lay.addWidget(card_pwd)

        # -------------------------------------------------------------
        # CARD 3: إدارة المستخدمين والصلاحيات
        # -------------------------------------------------------------
        card_users = QFrame()
        card_users.setObjectName("StatCard")
        c3_lay = QVBoxLayout(card_users)
        c3_lay.setSpacing(14)
        c3_lay.setContentsMargins(25, 25, 25, 25)

        c3_title = QLabel("👥  إدارة صلاحيات المستخدمين والمشرفين")
        c3_title.setObjectName("SectionTitle")
        c3_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #6366f1;")
        c3_lay.addWidget(c3_title)

        lbl_users_info = QLabel(
            "يمكنك إضافة موظفين ومشرفين جدد، وتحديد صلاحيات الوصول إلى أقسام النظام أو تعديل كلمات المرور الخاصة بهم."
        )
        lbl_users_info.setWordWrap(True)
        lbl_users_info.setStyleSheet("font-size: 13px; color: #64748b;")
        c3_lay.addWidget(lbl_users_info)

        btn_goto_users = QPushButton("الانتقال إلى شاشة المستخدمين والصلاحيات ↗")
        btn_goto_users.setObjectName("SecondaryBtn")
        btn_goto_users.setStyleSheet("background-color: #f1f5f9; color: #1e293b; border: 1px solid #cbd5e1; font-weight: bold;")
        btn_goto_users.setFixedHeight(38)
        btn_goto_users.clicked.connect(self.goto_users_permissions_tab)
        c3_lay.addWidget(btn_goto_users)

        lay.addWidget(card_users)

        lay.addStretch()
        page.setWidget(container)
        return page

    def load_security_settings(self):
        """تحميل حالة إعدادات الأمان من قاعدة البيانات."""
        require_login = self.get_setting_bool("require_login_password", default=False)
        self.chk_require_login.setChecked(require_login)

        timeout_val = self.get_setting("session_timeout_minutes", "معطل (بدون قفل)")
        idx = self.combo_session_timeout.findText(timeout_val)
        if idx >= 0:
            self.combo_session_timeout.setCurrentIndex(idx)

        attempts_val = self.get_setting("max_login_attempts", "5 محاولات")
        idx_att = self.combo_max_attempts.findText(attempts_val)
        if idx_att >= 0:
            self.combo_max_attempts.setCurrentIndex(idx_att)

    def save_security_settings(self):
        """حفظ إعدادات الأمان في قاعدة البيانات."""
        val = "1" if self.chk_require_login.isChecked() else "0"
        self._set_setting("require_login_password", val)
        self._set_setting("session_timeout_minutes", self.combo_session_timeout.currentText())
        self._set_setting("max_login_attempts", self.combo_max_attempts.currentText())
        self.db.commit()

        status = "مفعّلة" if self.chk_require_login.isChecked() else "مُلغاة"
        from gui.dialogs import ModernDialog
        ModernDialog(
            self,
            "نجاح",
            f"تم حفظ إعدادات الأمان بنجاح:\n"
            f"• التحقق عند فتح البرنامج: {status}\n"
            f"• القفل عند الخمول: {self.combo_session_timeout.currentText()}\n"
            f"• محاولات الدخول الخاطئة: {self.combo_max_attempts.currentText()}"
        ).exec()

    def change_admin_password(self):
        """تغيير كلمة المرور لحساب المدير/المشرف."""
        curr_pwd = self.txt_curr_pwd.text().strip()
        new_pwd = self.txt_new_pwd.text().strip()
        confirm_pwd = self.txt_confirm_pwd.text().strip()

        from gui.dialogs import ModernDialog

        if not new_pwd or not confirm_pwd:
            ModernDialog(self, "تنبيه", "يرجى إدخال كلمة المرور الجديدة وتأكيدها.").exec()
            return

        if len(new_pwd) < 6:
            ModernDialog(self, "تنبيه", "يجب أن تتكون كلمة المرور الجديدة من 6 خانات على الأقل.").exec()
            return

        if new_pwd != confirm_pwd:
            ModernDialog(self, "خطأ", "كلمة المرور الجديدة وتأكيدها غير متطابقين.").exec()
            return

        # البحث عن حساب المشرف/المدير
        admin_user = None
        if self.logged_in_staff:
            admin_user = self.db.query(db_mod.Staff).filter(db_mod.Staff.id == self.logged_in_staff.id).first()
        if not admin_user:
            admin_user = self.db.query(db_mod.Staff).filter(db_mod.Staff.role == "مدير").first() or self.db.query(db_mod.Staff).first()

        if not admin_user:
            ModernDialog(self, "خطأ", "لم يتم العثور على حساب مسؤول لتحديث كلمة المرور.").exec()
            return

        # التحقق من كلمة المرور الحالية إن وجدت
        if admin_user.password:
            if not curr_pwd:
                ModernDialog(self, "تنبيه", "يرجى كتابة كلمة المرور الحالية للتحقق.").exec()
                return
            if not security.verify_password(curr_pwd, admin_user.password):
                ModernDialog(self, "خطأ", "كلمة المرور الحالية غير صحيحة!").exec()
                return

        # حفظ كلمة المرور مشفرة
        admin_user.password = security.hash_password(new_pwd)
        self.db.commit()

        self.txt_curr_pwd.clear()
        self.txt_new_pwd.clear()
        self.txt_confirm_pwd.clear()

        ModernDialog(self, "نجاح", f"تم تحديث كلمة المرور للمستخدم ({admin_user.name or admin_user.staff_id_code}) بنجاح.").exec()

    def goto_users_permissions_tab(self):
        """الانتقال لتبويب المستخدمين والصلاحيات."""
        self.settings_sidebar.setCurrentRow(0)
        if hasattr(self, 'company_settings_tabs'):
            self.company_settings_tabs.setCurrentIndex(1)

    def on_settings_tab_changed(self, index):
        self.settings_stack.setCurrentIndex(index)
        if index == 0:
            self.load_company_settings()
        elif index == 1:
            self.refresh_cat_list()
        elif index == 2:
            self.load_security_settings()
        elif index == 3:
            self.load_financial_discipline_settings()

    def _build_financial_discipline_settings_page(self):
        """بناء صفحة إعدادات الانضباط المالي لسطح المكتب."""
        page = QScrollArea()
        page.setWidgetResizable(True)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(25)

        title = QLabel("⚙️  إعدادات الانضباط المالي")
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        # Card
        card = QFrame()
        card.setObjectName("StatCard")
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(18)
        card_lay.setContentsMargins(25, 25, 25, 25)

        card_title = QLabel("تخصيص حدود وقواعد الانضباط المالي")
        card_title.setObjectName("SectionTitle")
        card_title.setStyleSheet("font-size: 16px; color: #3b82f6;")
        card_lay.addWidget(card_title)

        desc = QLabel(
            "يمكنك التحكم في عدد الأقساط المتأخرة لتحديد حالة المشترك:\n"
            "• المشترك الذي لديه أقساط متأخرة تساوي أو تتجاوز حد التأخر يصبح حالته (متأخر 🔴).\n"
            "• المشترك الذي لديه أقساط متأخرة تساوي أو تتجاوز حد الإيقاف يصبح حالته (موقوف ⚫) ويُستبعد تلقائياً من القرعة والسحوبات."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #64748b; line-height: 20px;")
        card_lay.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(15)
        
        self.txt_late_threshold = QLineEdit()
        self.txt_late_threshold.setPlaceholderText("مثال: 1")
        
        self.txt_suspended_threshold = QLineEdit()
        self.txt_suspended_threshold.setPlaceholderText("مثال: 3")
        
        form.addRow("حد التأخر (عدد الأقساط المتأخرة):", self.txt_late_threshold)
        form.addRow("حد الإيقاف والاستبعاد (عدد الأقساط المتأخرة):", self.txt_suspended_threshold)
        
        card_lay.addLayout(form)

        btn_save = QPushButton("حفظ إعدادات الانضباط المالي")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setFixedHeight(42)
        btn_save.clicked.connect(self.save_financial_discipline_settings)
        card_lay.addWidget(btn_save)

        lay.addWidget(card)
        lay.addStretch()
        page.setWidget(container)
        return page

    def load_financial_discipline_settings(self):
        late_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "discipline_late_threshold").first()
        late_val = late_setting.value if late_setting else "1"
        self.txt_late_threshold.setText(late_val)

        susp_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "discipline_suspended_threshold").first()
        susp_val = susp_setting.value if susp_setting else "3"
        self.txt_suspended_threshold.setText(susp_val)

    def save_financial_discipline_settings(self):
        late_val = self.txt_late_threshold.text().strip()
        susp_val = self.txt_suspended_threshold.text().strip()

        if not late_val.isdigit() or not susp_val.isdigit():
            from gui.dialogs import ModernDialog
            ModernDialog(self, "خطأ", "يجب إدخال قيم رقمية صحيحة.").exec()
            return

        for key, val in [("discipline_late_threshold", late_val), ("discipline_suspended_threshold", susp_val)]:
            setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
            if setting:
                setting.value = val
            else:
                self.db.add(db_mod.Setting(key=key, value=val))
        
        self.db.commit()
        from gui.dialogs import ModernDialog
        ModernDialog(self, "نجاح", "تم حفظ إعدادات الانضباط المالي بنجاح.").exec()


    def show_main_settings(self):
        self.content_stack.setCurrentWidget(self.page_main_settings)
        self._update_nav_style("الإعدادات")
        self.on_settings_tab_changed(self.settings_sidebar.currentRow())

    def show_reports(self): 
        self.content_stack.setCurrentWidget(self.page_reports)
        self._update_nav_style("أداة التقارير")
        self.refresh_reports_sub_list()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    db_mod.init_db() # ضمان تهيئة قاعدة البيانات قبل أي شيء آخر
    try:
        app.setFont(QFont("Tajawal", 10))
    except Exception:
        pass
    window = AdminApp()
    if window.access_granted:
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)
