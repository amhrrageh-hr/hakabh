from sqlalchemy import func
from sqlalchemy.orm import Session
import os
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
import datetime
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
from gui.utils import reshape_text, register_arabic_font

class ModernDialog(QDialog):
    def __init__(self, parent, title, message, is_confirm=False, is_input=False, initial_value=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(400)
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

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تسجيل دخول الإدارة")
        self.setFixedWidth(420)
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
        self.setFixedWidth(420)
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

class DrawAnimationDialog(QDialog):
    def __init__(self, parent, qualified_by_category, draw_name, db):
        super().__init__(parent)
        self.setWindowTitle(draw_name)
        self.setFixedSize(900, 700)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setStyleSheet("background-color: #052109; color: white;")
        self.db = db
        self.draw_name = draw_name
        self.qualified_by_category = qualified_by_category
        self.categories = list(qualified_by_category.keys())
        self.current_cat_index = 0
        self.winners = []
        
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.setSpacing(40)
        
        self.cat_label = QLabel("")
        self.cat_label.setStyleSheet("font-size: 38px; color: #4ade80; font-weight: bold;")
        self.cat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.cat_label)
        
        self.wheel_container = QFrame()
        self.wheel_container.setFixedSize(600, 300)
        self.wheel_container.setStyleSheet("border: 10px solid #2e7d32; border-radius: 40px; background-color: #0a3d0e;")
        container_layout = QVBoxLayout(self.wheel_container)
        
        self.wheel_label = QLabel("---")
        self.wheel_label.setStyleSheet("font-size: 100px; font-weight: 900; color: #ffffff;")
        self.wheel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.wheel_label)
        
        self.layout.addWidget(self.wheel_container, 0, Qt.AlignmentFlag.AlignCenter)
        
        self.status_label = QLabel("استعد للسحب...")
        self.status_label.setStyleSheet("font-size: 24px; color: #94a3b8;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_wheel)
        self.animation_step = 0
        self.animation_duration = 50
        
        QTimer.singleShot(2000, self.start_category_draw)

    def start_category_draw(self):
        if self.current_cat_index >= len(self.categories):
            self.show_final_report()
            return
            
        cat_name = self.categories[self.current_cat_index]
        self.cat_label.setText(f"سحب فئة: {cat_name}")
        self.status_label.setText("جاري تدوير عجلة الحظ...")
        self.wheel_container.setStyleSheet("border: 10px solid #2e7d32; border-radius: 40px; background-color: #0a3d0e;")
        self.wheel_label.setStyleSheet("font-size: 100px; font-weight: 900; color: #ffffff;")
        
        self.animation_step = 0
        self.timer.setInterval(60)
        self.timer.start()

    def update_wheel(self):
        cat_name = self.categories[self.current_cat_index]
        subs = self.qualified_by_category[cat_name]
        random_sub = random.choice(subs)
        self.wheel_label.setText(random_sub.subscriber_number)
        
        self.animation_step += 1
        if self.animation_step > 35:
            self.timer.setInterval(self.timer.interval() + 25)
            
        if self.animation_step >= self.animation_duration:
            self.timer.stop()
            self.conclude_category_draw(random_sub)

    def conclude_category_draw(self, winner_sub):
        cat_name = self.categories[self.current_cat_index]
        self.winners.append((cat_name, winner_sub))
        
        self.wheel_container.setStyleSheet("border: 12px solid #facc15; border-radius: 40px; background-color: #1e293b;")
        self.wheel_label.setStyleSheet("font-size: 110px; font-weight: 900; color: #facc15;")
        winner_name = winner_sub.name or "غير محدد"
        self.status_label.setText(f"🎉 مبروك للفائز: {winner_name} (رقم: {winner_sub.subscriber_number})")
        
        # Calculate active cycle
        active_p = self.db.query(db_mod.Payment).filter(
            db_mod.Payment.subscriber_id == winner_sub.id,
            db_mod.Payment.due_date <= datetime.datetime.now()
        ).order_by(db_mod.Payment.due_date.desc()).first()
        cycle_num = active_p.cycle_number if active_p else 1
        
        new_w = db_mod.Winner(
            subscriber_number=winner_sub.subscriber_number, 
            draw_type=f"{self.draw_name} - {cat_name}", 
            draw_date=datetime.datetime.now(),
            cycle_number=cycle_num
        )
        self.db.add(new_w); self.db.commit()
        
        QTimer.singleShot(4000, self.next_category)

    def next_category(self):
        self.current_cat_index += 1
        self.start_category_draw()

    def show_final_report(self):
        for i in reversed(range(self.layout.count())):
            if self.layout.itemAt(i).widget(): self.layout.itemAt(i).widget().setParent(None)
        
        title = QLabel("🏆 التقرير النهائي للفائزين بالسحب"); title.setStyleSheet("font-size: 34px; color: #4ade80; font-weight: bold; margin-bottom: 20px;"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); self.layout.addWidget(title)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setStyleSheet("background: transparent; border: none;"); scroll_content = QWidget(); scroll_layout = QVBoxLayout(scroll_content)
        
        for cat, sub in self.winners:
            card = QFrame(); card.setStyleSheet("background-color: #1e293b; border-radius: 15px; border: 1px solid #334155; margin: 10px; padding: 20px;")
            h_lay = QVBoxLayout(card)
            info = QLabel(f"الفئة: {cat}\nالاسم: {sub.name or '-'}\nرقم المشترك / الحساب: {sub.subscriber_number}\nالهاتف: {sub.phone or '-'}")
            info.setStyleSheet("font-size: 19px; color: white; line-height: 1.6;")
            h_lay.addWidget(info); scroll_layout.addWidget(card)
        
        scroll_layout.addStretch(); scroll.setWidget(scroll_content); self.layout.addWidget(scroll)
        btn_close = QPushButton("إغلاق والعودة للسجل"); btn_close.setObjectName("PrimaryBtn"); btn_close.setFixedWidth(300); btn_close.setFixedHeight(50); btn_close.clicked.connect(self.accept); self.layout.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignCenter)

class SubscriberEditDialog(QDialog):
    def __init__(self, parent, sub):
        super().__init__(parent)
        self.setWindowTitle("تعديل بيانات المشترك")
        self.setFixedWidth(450)
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

class CategoryEditDialog(QDialog):
    def __init__(self, parent, cat):
        super().__init__(parent)
        self.setWindowTitle("تعديل بيانات الفئة")
        self.setFixedWidth(400)
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
        
        self.btn_save = QPushButton("حفظ التغييرات")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.clicked.connect(self.accept)
class CreateGroupBatchDialog(QDialog):
    def __init__(self, parent, cat=None):
        super().__init__(parent)
        self.setWindowTitle("فتح مجموعة / دفعة جديدة للفئة")
        self.setFixedWidth(460)
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
        self.setFixedWidth(440)
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
        self.setFixedWidth(450)
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
    def __init__(self, parent, payment=None, max_inst=24, max_cycles=10, staff_list=None):
        super().__init__(parent)
        self.setWindowTitle("بيانات العملية المالية" if not payment else "تعديل العملية المالية")
        self.setFixedWidth(400)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.ent_amount = QLineEdit()
        self.ent_amount.setText(str(payment.amount) if payment else "")
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
        if payment:
            self.ent_date.setDate(QDate(payment.due_date.year, payment.due_date.month, payment.due_date.day))
        else:
            self.ent_date.setDate(QDate.currentDate())
        form.addRow("التاريخ:", self.ent_date)
        
        self.cb_paid = QComboBox()
        self.cb_paid.addItems(["غير مدفوع", "مدفوع"])
        if payment and payment.is_paid: self.cb_paid.setCurrentIndex(1)
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
        self.btn_save.clicked.connect(self.accept)
        layout.addWidget(self.btn_save)

class AddSubscriberDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("إضافة مشترك جديد")
        self.resize(500, 450)
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
        
        self.cb_cat = QComboBox()
        self.cb_cat.addItem("اختر الفئة...", None)
        for cat in db.query(db_mod.Category).all():
            self.cb_cat.addItem(cat.name, cat.id)
        self.cb_cat.currentIndexChanged.connect(self.load_numbers)
        form.addRow("الفئة:", self.cb_cat)
        
        self.cb_num = QComboBox()
        self.cb_num.addItem("اختر الرقم...", None)
        form.addRow("رقم المشترك:", self.cb_num)
        
        self.ent_pwd = QLineEdit()
        self.ent_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.ent_pwd.setPlaceholderText("كلمة المرور (6 أحرف على الأقل)")
        form.addRow("كلمة المرور للموقع:", self.ent_pwd)
        
        layout.addWidget(form_frame)
        
        self.btn_save = QPushButton("إضافة المشترك")
        self.btn_save.setObjectName("PrimaryBtn"); self.btn_save.setFixedHeight(45)
        self.btn_save.clicked.connect(self.validate_and_accept)
        layout.addWidget(self.btn_save)

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

    def validate_and_accept(self):
        if not self.ent_name.text() or not self.ent_phone.text() or not self.cb_cat.currentData() or not self.cb_num.currentData() or not self.ent_pwd.text():
            QMessageBox.warning(self, "خطأ", "يرجى ملء جميع الحقول")
            return
        if len(self.ent_pwd.text().strip()) < 6:
            QMessageBox.warning(self, "خطأ", "يجب أن تكون كلمة المرور 6 أحرف على الأقل")
            return
        self.accept()

class AddStaffDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("إنشاء حساب موظف جديد")
        self.setFixedWidth(400)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        title = QLabel("إضافة موظف جديد")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2e7d32; margin-bottom: 10px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.ent_name = QLineEdit()
        self.ent_phone = QLineEdit()
        self.ent_staff_id = QLineEdit()
        self.ent_pwd = QLineEdit()
        self.ent_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["مدير", "محاسب", "موظف", "مشاهد"])

        form.addRow("اسم الموظف:", self.ent_name)
        form.addRow("رقم الهاتف:", self.ent_phone)
        form.addRow("رقم الموظف الخاص:", self.ent_staff_id)
        form.addRow("الصلاحية:", self.role_combo)
        form.addRow("كلمة السر:", self.ent_pwd)
        layout.addLayout(form)

        self.btn_save = QPushButton("إنشاء الحساب")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.setFixedHeight(40)
        self.btn_save.clicked.connect(self.validate)
        layout.addWidget(self.btn_save)

    def validate(self):
        if not self.ent_name.text() or not self.ent_staff_id.text() or not self.ent_pwd.text():
            QMessageBox.warning(self, "تنبيه", "يرجى ملء جميع الحقول الإجبارية")
            return
        self.accept()

class BatchPaymentDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("القيد المتعدد - إضافة دفعة لمجموعة")
        self.resize(600, 700)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Filter by Category
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("تصفية حسب الفئة:"))
        self.cb_cat = QComboBox()
        self.cb_cat.addItem("الكل", None)
        for cat in db.query(db_mod.Category).all():
            self.cb_cat.addItem(cat.name, cat.id)
        self.cb_cat.currentIndexChanged.connect(self.load_subscribers)
        filter_layout.addWidget(self.cb_cat)
        layout.addLayout(filter_layout)
        
        # Selection Bar (Header + Select/Deselect All Buttons)
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
        
        # Subscriber List with Selection
        self.list_subs = QListWidget()
        layout.addWidget(self.list_subs)
        
        # Payment Details Form
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
        
        # Reset ranges
        max_i = 24
        max_c = 10
        
        # يعرض المشتركين المقبولين فقط
        query = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted")
        if cat_id:
            cat = self.db.get(db_mod.Category, cat_id)
            if cat:
                max_i = cat.max_installments
                max_c = cat.max_cycles
            
            cat_name = self.cb_cat.currentText()
            query = query.filter(db_mod.Subscriber.category == cat_name)
        
        # Update UI ranges
        self.cb_inst.clear()
        self.cb_inst.addItems([str(i) for i in range(1, max_i + 1)])
        self.cb_cycle.clear()
        self.cb_cycle.addItems([str(i) for i in range(1, max_c + 1)])
        
        subs = query.order_by(db_mod.Subscriber.name).all()
        for s in subs:
            # حساب القسط الحالي المستحق لكل مشترك
            next_unpaid = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == s.id,
                db_mod.Payment.is_paid == False
            ).order_by(db_mod.Payment.cycle_number.asc(), db_mod.Payment.installment_number.asc()).first()
            
            if next_unpaid:
                status_hint = f" | القسط التالي: د{next_unpaid.cycle_number}/ق{next_unpaid.installment_number}"
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
        ids = []
        for i in range(self.list_subs.count()):
            item = self.list_subs.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def submit_batch_payment(self):
        selected_ids = self.get_selected_ids()
        if not selected_ids:
            ModernDialog(self, "تنبيه", "يرجى اختيار مشترك واحد على الأقل").exec()
            return
        
        try:
            amount_str = self.ent_amount.text().strip()
            if not amount_str:
                ModernDialog(self, "خطأ", "يرجى إدخال المبلغ").exec()
                return
            amount = float(amount_str)
            if amount <= 0:
                ModernDialog(self, "خطأ", "يجب أن يكون المبلغ أكبر من صفر").exec()
                return

            due_date = datetime.datetime.combine(self.ent_date.date().toPyDate(), datetime.time.min)
            inst = int(self.cb_inst.currentText())
            cycle = int(self.cb_cycle.currentText())
            note = self.ent_note.text().strip()

            staff = getattr(self.parent(), 'logged_in_staff', None)
            staff_id = staff.id if staff else None

            skipped = 0
            updated = 0
            created = 0

            for sid in selected_ids:
                sub = self.db.get(db_mod.Subscriber, sid)
                if not sub:
                    continue

                cat = self.db.query(db_mod.Category).filter(
                    db_mod.Category.name == sub.category
                ).first()
                cat_amount = cat.amount if (cat and cat.amount and cat.amount > 0) else amount
                max_c = cat.max_cycles if cat else 99
                max_i = cat.max_installments if cat else 99

                remaining = amount

                def combine_notes(existing_note, user_note, auto_msg):
                    parts = []
                    if existing_note and str(existing_note).strip():
                        parts.append(str(existing_note).strip())
                    if user_note and str(user_note).strip():
                        u_str = str(user_note).strip()
                        if u_str not in parts:
                            parts.append(u_str)
                    if auto_msg and str(auto_msg).strip():
                        a_str = str(auto_msg).strip()
                        if not any(a_str in p for p in parts):
                            parts.append(a_str)
                    return " | ".join(parts)

                def build_staff_message(base_msg):
                    if staff_id:
                        staff_obj = self.db.get(db_mod.Staff, staff_id)
                        if staff_obj and staff_obj.name:
                            return f"{base_msg} (القيد المتعدد - الموظف: {staff_obj.name})"
                    return f"{base_msg} (القيد المتعدد)"

                # 1. Distribute among existing unpaid targets first (FIFO)
                targets = self.db.query(db_mod.Payment).filter(
                    db_mod.Payment.subscriber_id == sid,
                    db_mod.Payment.is_paid == False
                ).order_by(db_mod.Payment.cycle_number.asc(), db_mod.Payment.installment_number.asc()).all()

                last_processed_c = 0
                last_processed_i = 0

                for p in targets:
                    if remaining <= 0:
                        break
                    
                    staff_obj = self.db.get(db_mod.Staff, staff_id) if staff_id else None
                    s_name = staff_obj.name if staff_obj else None

                    if remaining < p.amount:
                        balance = p.amount - remaining
                        p.amount = remaining
                        p.is_paid = True
                        p.paid_date = due_date
                        p.staff_id = staff_id
                        p.is_staff_settled = False
                        p.note = db_mod.build_installment_note(is_paid=True, due_date=p.due_date, paid_date=due_date, user_note=note, staff_name=s_name, is_partial=True)

                        new_unpaid = db_mod.Payment(
                            subscriber_id=sid,
                            amount=balance,
                            due_date=p.due_date,
                            is_paid=False,
                            cycle_number=p.cycle_number,
                            installment_number=p.installment_number,
                            note=db_mod.build_installment_note(is_paid=False, due_date=p.due_date, is_partial=True)
                        )
                        self.db.add(new_unpaid)
                        remaining = 0
                        updated += 1
                    else:
                        pay_now = p.amount
                        p.is_paid = True
                        p.paid_date = due_date
                        p.staff_id = staff_id
                        p.is_staff_settled = False
                        p.note = db_mod.build_installment_note(is_paid=True, due_date=p.due_date, paid_date=due_date, user_note=note, staff_name=s_name)
                        remaining -= pay_now
                        updated += 1

                    last_processed_c = p.cycle_number
                    last_processed_i = p.installment_number

                # 2. If balance remains, continue forward creation/update
                if remaining > 0:
                    if last_processed_c > 0:
                        curr_c, curr_i = last_processed_c, last_processed_i + 1
                        if curr_i > max_i:
                            curr_i = 1
                            curr_c += 1
                    else:
                        curr_c, curr_i = cycle, inst

                    safety_counter = 0
                    max_safety = max_c * max_i

                    while remaining > 0 and curr_c <= max_c and safety_counter < max_safety:
                        safety_counter += 1

                        p = self.db.query(db_mod.Payment).filter(
                            db_mod.Payment.subscriber_id == sid,
                            db_mod.Payment.cycle_number == curr_c,
                            db_mod.Payment.installment_number == curr_i
                        ).first()

                        if p and p.is_paid:
                            curr_i += 1
                            if curr_i > max_i:
                                curr_i = 1
                                curr_c += 1
                            continue

                        pay_now = min(remaining, cat_amount)
                        is_partial = (pay_now < cat_amount)
                        staff_obj = self.db.get(db_mod.Staff, staff_id) if staff_id else None
                        s_name = staff_obj.name if staff_obj else None
                        p_due = p.due_date if p else due_date
                        note_text = db_mod.build_installment_note(is_paid=True, due_date=p_due, paid_date=due_date, user_note=note, staff_name=s_name, is_partial=is_partial)

                        if p:
                            p.amount = pay_now
                            p.is_paid = True
                            p.paid_date = due_date
                            p.staff_id = staff_id
                            p.is_staff_settled = False
                            p.note = note_text
                            updated += 1
                        else:
                            new_p = db_mod.Payment(
                                subscriber_id=sid,
                                amount=pay_now,
                                due_date=due_date,
                                paid_date=due_date,
                                is_paid=True,
                                installment_number=curr_i,
                                cycle_number=curr_c,
                                note=note_text,
                                staff_id=staff_id,
                                is_staff_settled=False
                            )
                            self.db.add(new_p)
                            created += 1

                        if is_partial:
                            new_unpaid = db_mod.Payment(
                                subscriber_id=sid,
                                amount=cat_amount - pay_now,
                                due_date=due_date,
                                is_paid=False,
                                cycle_number=curr_c,
                                installment_number=curr_i,
                                note="متبقي من سداد جزئي"
                            )
                            self.db.add(new_unpaid)
                            remaining = 0
                        else:
                            remaining -= pay_now

                        curr_i += 1
                        if curr_i > max_i:
                            curr_i = 1
                            curr_c += 1

            self.db.commit()

            msg_parts = []
            if created:  msg_parts.append(f"تم إنشاء {created} قسط جديد")
            if updated:  msg_parts.append(f"تم تحديث {updated} قسط موجود")
            if skipped:  msg_parts.append(f"تم تجاوز {skipped} (مسدد مسبقاً أو خارج الحدود)")

            ModernDialog(self, "نجاح", " | ".join(msg_parts) if msg_parts else "تم التسجيل بنجاح").exec()

            # إعادة تحميل قائمة المشتركين في الواجهة لتحديث القسط التالي
            self.load_subscribers()

            # تحديث شاشة المشتركين الأساسية خلف النافذة
            if hasattr(self.parent(), 'load_subscribers'):
                self.parent().load_subscribers()

        except ValueError:
            ModernDialog(self, "خطأ", "يرجى إدخال مبلغ صحيح").exec()
        except Exception as e:
            self.db.rollback()
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التسجيل: {e}").exec()

class AccountDetailsDialog(QDialog):
    def __init__(self, parent, sub_id, db):
        super().__init__(parent)
        self.sub_id = sub_id
        self.db = db
        sub = db.get(db_mod.Subscriber, sub_id)
        
        self.setWindowTitle(f"كشف حساب - {sub.name}")
        self.resize(850, 600)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        header = QHBoxLayout()
        title = QLabel(f"كشف الحساب: {sub.name}")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        
        btn_add = QPushButton("قيد يدوي")
        btn_add.setObjectName("PrimaryBtn")
        btn_add.setFixedWidth(100)
        btn_add.clicked.connect(self.add_payment)
        
        btn_exp_ex = QPushButton("إكسل")
        btn_exp_ex.setFixedWidth(70)
        btn_exp_ex.clicked.connect(self.export_history_excel)
        
        btn_exp_pdf = QPushButton("PDF")
        btn_exp_pdf.setFixedWidth(70)
        btn_exp_pdf.setObjectName("DangerBtn")
        btn_exp_pdf.clicked.connect(self.export_history_pdf)
        
        btn_del_multi = QPushButton("حذف المختار")
        btn_del_multi.setObjectName("DangerBtn")
        btn_del_multi.setFixedWidth(110)
        btn_del_multi.clicked.connect(self.delete_selected_payments)
        
        header.addStretch()
        header.addWidget(btn_exp_ex)
        header.addWidget(btn_exp_pdf)
        header.addWidget(btn_add)
        header.addWidget(btn_del_multi)
        layout.addLayout(header)

        # شريط ملخص الحساب العلوي
        summary_lay = QHBoxLayout()
        summary_lay.setSpacing(15)
        
        self.lbl_total_paid = self.create_summary_card(summary_lay, "إجمالي المسدد", "#10b981")
        self.lbl_total_remaining = self.create_summary_card(summary_lay, "المبالغ المتبقية", "#ef4444")
        self.lbl_paid_count = self.create_summary_card(summary_lay, "الأقساط المنجزة", "#3b82f6")
        layout.addLayout(summary_lay)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "تاريخ تسديد القسط المستحق",
            "تاريخ تسديد القسط الفعلي",
            "المبلغ",
            "القسط",
            "الدورة",
            "الحالة",
            "الملاحظة"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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
        card.setFixedHeight(85)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(15, 10, 15, 10)
        vbox.setSpacing(5)
        
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #64748b; font-size: 12px; font-weight: bold;")
        t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(t_lbl)
        
        v_lbl = QLabel("0.00 ر.ي")
        v_lbl.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 800;")
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

    def load_payments(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all() # Ensure fresh data
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
        staff_obj = self.db.get(db_mod.Staff, staff_id) if staff_id else None
        s_name = staff_obj.name if staff_obj else None

        if not is_paid or total_amount <= 0 or cat_amount <= 0:
            return False 
            
        remaining = total_amount
        
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

            while remaining > 0 and curr_c <= max_c:
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
                p_due = p.due_date if p else date
                new_note = db_mod.build_installment_note(is_paid=True, due_date=p_due, paid_date=date, user_note=note, staff_name=s_name, is_partial=is_partial)

                new_paid = db_mod.Payment(
                    subscriber_id=self.sub_id,
                    amount=pay_now,
                    due_date=date,
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
                    # إنشاء سجل "متبقي" غير مدفوع في حالة السداد الجزئي المستقبلي
                    new_unpaid = db_mod.Payment(
                        subscriber_id=self.sub_id,
                        amount=cat_amount - pay_now,
                        due_date=date,
                        is_paid=False,
                        cycle_number=curr_c,
                        installment_number=curr_i,
                        note="متبقي من دفع جزئي"
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
        cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
        cat_amount = cat.amount if cat else 0
        max_c = cat.max_cycles if cat else 10
        max_i = cat.max_installments if cat else 24

        staff_list = self.db.query(db_mod.Staff).all()
        
        dialog = PaymentDialog(self, max_cycles=max_c, max_inst=max_i, staff_list=staff_list)
        if dialog.exec():
            try:
                entered_amount = float(dialog.ent_amount.text())
                is_paid = (dialog.cb_paid.currentIndex() == 1)
                cycle = int(dialog.cb_cycle.currentText())
                inst = int(dialog.cb_inst.currentText())
                date = datetime.datetime.combine(dialog.ent_date.date().toPyDate(), datetime.time.min)
                note = dialog.ent_note.text()
                staff_id = dialog.cb_staff.currentData()

                if is_paid and cat_amount > 0:
                    self.process_smart_payment(entered_amount, cycle, inst, date, is_paid, note, cat_amount, max_c, max_i, staff_id=staff_id)
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
                        is_staff_settled=False if is_paid else None
                    )
                    self.db.add(new_p)
                    self.db.commit()
                
                self.load_payments()
            except Exception as e:
                ModernDialog(self, "خطأ", f"بيانات غير صحيحة: {e}").exec()

    def edit_payment(self, pid):
        p = self.db.get(db_mod.Payment, pid)
        sub = self.db.get(db_mod.Subscriber, self.sub_id)
        cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
        cat_amount = cat.amount if cat else 0
        max_c = cat.max_cycles if cat else 10
        max_i = cat.max_installments if cat else 24

        staff_list = self.db.query(db_mod.Staff).all()
        
        dialog = PaymentDialog(self, p, max_cycles=max_c, max_inst=max_i, staff_list=staff_list)
        if dialog.exec():
            try:
                entered_amount = float(dialog.ent_amount.text())
                is_paid = (dialog.cb_paid.currentIndex() == 1)
                cycle = int(dialog.cb_cycle.currentText())
                inst = int(dialog.cb_inst.currentText())
                date = datetime.datetime.combine(dialog.ent_date.date().toPyDate(), datetime.time.min)
                note = dialog.ent_note.text()
                staff_id = dialog.cb_staff.currentData()

                if is_paid and cat_amount > 0:
                    # تعديل مباشر للقسط الموجود - لا نستخدم process_smart_payment
                    # لأنه يُنشئ سداداً جديداً إضافياً فيتضاعف المبلغ في الإجمالي
                    p.amount = entered_amount
                    p.due_date = date
                    p.is_paid = is_paid
                    p.paid_date = date if is_paid else None
                    p.installment_number = inst
                    p.cycle_number = cycle
                    p.note = note
                    p.staff_id = staff_id
                    p.is_staff_settled = False
                    self.db.commit()
                else:
                    p.amount = entered_amount
                    p.due_date = date
                    p.is_paid = is_paid
                    p.paid_date = date if is_paid else None
                    p.installment_number = inst
                    p.cycle_number = cycle
                    p.note = note
                    p.staff_id = staff_id
                    self.db.commit()
                
                self.load_payments()
            except Exception as e:
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
        
        act_del_multi = QAction("حذف العمليات المختارة", self)
        act_del_multi.triggered.connect(self.delete_selected_payments)
        
        menu.addAction(act_edit)
        menu.addAction(act_del)
        menu.addSeparator()
        menu.addAction(act_del_multi)
        menu.exec(QCursor.pos())

    def delete_payment(self, pid):
        if ModernDialog(self, "تأكيد", "هل تريد حذف هذه العملية؟", is_confirm=True).exec():
            p = self.db.get(db_mod.Payment, pid)
            if p:
                self.db.delete(p)
                self.db.commit()
                self.load_payments()

    def delete_selected_payments(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            ModernDialog(self, "تنبيه", "يرجى اختيار عملية واحدة على الأقل").exec()
            return
            
        count = len(selected_rows)
        if ModernDialog(self, "تأكيد", f"هل تريد حذف {count} عملية مختارة؟", is_confirm=True).exec():
            try:
                for index in selected_rows:
                    pid = self.table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
                    p = self.db.get(db_mod.Payment, pid)
                    if p:
                        self.db.delete(p)
                self.db.commit()
                self.load_payments()
                ModernDialog(self, "نجاح", f"تم حذف {count} عملية بنجاح").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء الحذف: {e}").exec()

class StaffActivityDialog(QDialog):
    def __init__(self, parent, staff_id, db):
        super().__init__(parent)
        self.staff_id = staff_id
        self.db = db
        staff = db.get(db_mod.Staff, staff_id)
        
        self.setWindowTitle(f"سجل تحصيلات الموظف - {staff.name}")
        self.resize(800, 550)
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

    def load_payments(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all() # Ensure fresh data
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

            date_cell = p.due_date.strftime("%Y-%m-%d") if p.due_date else "-"
            items = [
                QTableWidgetItem(date_cell),
                QTableWidgetItem(f"{p.amount:,.2f}"),
                QTableWidgetItem(str(p.installment_number)),
                QTableWidgetItem(str(p.cycle_number)),
                QTableWidgetItem("مدفوع" if p.is_paid else "غير مدفوع"),
                QTableWidgetItem(p.note or "-")
            ]
            
            items[4].setForeground(QColor("#2e7d32" if p.is_paid else "#ef4444"))

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
        # دالة مساعدة لدمج الملاحظات بشكل نظيف
        def append_note(original, new_msg):
            prefix = f"{original.strip()} | " if original and original.strip() else ""
            return f"{prefix}{new_msg}"

        def build_staff_message(base_msg):
            if staff_id:
                staff = self.db.get(db_mod.Staff, staff_id)
                if staff and staff.name:
                    return f"{base_msg} من الموقع من موظف {staff.name}"
            return f"{base_msg} من الموقع"

        if not is_paid or total_amount <= 0 or cat_amount <= 0:
            return False 
            
        remaining = total_amount
        
        # 1. Collect all potential payment targets:
        # - Existing unpaid records (Arrears & Future)
        # - The one specifically selected (if not already in the DB or unpaid)
        
        # Get all unpaid records for this subscriber
        targets = self.db.query(db_mod.Payment).filter(
            db_mod.Payment.subscriber_id == self.sub_id,
            db_mod.Payment.is_paid == False
        ).order_by(db_mod.Payment.cycle_number.asc(), db_mod.Payment.installment_number.asc()).all()
        
        # Check if the selected (cycle, inst) is already in targets. 
        # If not, and it's not paid, we might need to create it or handle it.
        selected_exists = any(t.cycle_number == cycle and t.installment_number == inst for t in targets)
        
        if not selected_exists:
            # Check if it exists as PAID
            p_selected = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == self.sub_id,
                db_mod.Payment.cycle_number == cycle,
                db_mod.Payment.installment_number == inst
            ).first()
            
            if not p_selected:
                # It doesn't exist at all. We will handle it in the "forward" creation loop if needed.
                pass
            elif not p_selected.is_paid:
                # Should have been in 'targets'. (Safety check)
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
                if (p.due_date and p.due_date < date) or p.cycle_number < cycle or (p.cycle_number == cycle and p.installment_number < inst):
                    p.note = append_note(note, build_staff_message("تم سداد جزء من القسط المتأخر"))
                else:
                    p.note = append_note(note, "تم سداد جزء من القسط")

                # إنشاء سجل متبقي
                new_unpaid = db_mod.Payment(
                    subscriber_id=self.sub_id,
                    amount=balance,
                    due_date=p.due_date,
                    is_paid=False,
                    cycle_number=p.cycle_number,
                    installment_number=p.installment_number,
                    note="متبقي من سداد جزئي"
                )
                self.db.add(new_unpaid)
                remaining = 0
            else:
                pay_now = p.amount
                p.is_paid = True
                p.paid_date = date
                p.staff_id = staff_id
                p.is_staff_settled = False
                # إذا كان هذا سجل "متبقي" من سداد جزئي سابق، نسجل ملاحظة إتمام المتبقي
                existing_note = str(p.note or "")
                if "متبقي" in existing_note:
                    if (p.due_date and p.due_date < date) or p.cycle_number < cycle or (p.cycle_number == cycle and p.installment_number < inst):
                        p.note = append_note(note, build_staff_message("تم سداد باقي القسط الجزئي المتأخر"))
                    else:
                        p.note = append_note(note, "تم سداد باقي القسط الجزئي")
                elif (p.due_date and p.due_date < date) or p.cycle_number < cycle or (p.cycle_number == cycle and p.installment_number < inst):
                    p.note = append_note(note, build_staff_message("تم سداد قسط متأخر"))
                else:
                    p.note = append_note(note, "تم سداد القسط")
                remaining -= pay_now
            last_processed_c = p.cycle_number
            last_processed_i = p.installment_number

        # 3. If balance remains, continue forward creation/update
        if remaining > 0:
            # Determine where to start. 
            # If we processed targets, start from the next one after the last target.
            # Otherwise, start from the selected (cycle, inst).
            
            if last_processed_c > 0:
                curr_c, curr_i = last_processed_c, last_processed_i
                # Move to next
                curr_i += 1
                if curr_i > max_i:
                    curr_i = 1; curr_c += 1
            else:
                curr_c, curr_i = cycle, inst

            while remaining > 0 and curr_c <= max_c:
                # Check if exists (might have been missed or is a paid record we should skip)
                p = self.db.query(db_mod.Payment).filter(
                    db_mod.Payment.subscriber_id == self.sub_id,
                    db_mod.Payment.cycle_number == curr_c,
                    db_mod.Payment.installment_number == curr_i
                ).first()
                
                if p and p.is_paid:
                    # Already paid, move to next
                    curr_i += 1
                    if curr_i > max_i: curr_i = 1; curr_c += 1
                    continue
                
                pay_now = min(remaining, cat_amount)

                # تحديد نص الملاحظة حسب نوع السداد (حالي، مقدم، جزئي)
                if pay_now < cat_amount:
                    new_note = append_note(note, "تم سداد جزء من القسط")
                else:
                    if curr_c == cycle and curr_i == inst:
                        new_note = append_note(note, "تم سداد القسط")
                    else:
                        new_note = append_note(note, "قسط مقدم")

                new_paid = db_mod.Payment(
                    subscriber_id=self.sub_id,
                    amount=pay_now,
                    due_date=date,
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
                    # إنشاء سجل "متبقي" غير مدفوع في حالة السداد الجزئي المستقبلي
                    new_unpaid = db_mod.Payment(
                        subscriber_id=self.sub_id,
                        amount=cat_amount - pay_now,
                        due_date=date,
                        is_paid=False,
                        cycle_number=curr_c,
                        installment_number=curr_i,
                        note="متبقي من دفع جزئي"
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
        cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
        cat_amount = cat.amount if cat else 0
        max_c = cat.max_cycles if cat else 10
        max_i = cat.max_installments if cat else 24

        staff_list = self.db.query(db_mod.Staff).all()
        
        dialog = PaymentDialog(self, max_cycles=max_c, max_inst=max_i, staff_list=staff_list)
        if dialog.exec():
            try:
                entered_amount = float(dialog.ent_amount.text())
                is_paid = (dialog.cb_paid.currentIndex() == 1)
                cycle = int(dialog.cb_cycle.currentText())
                inst = int(dialog.cb_inst.currentText())
                date = datetime.datetime.combine(dialog.ent_date.date().toPyDate(), datetime.time.min)
                note = dialog.ent_note.text()
                staff_id = dialog.cb_staff.currentData()

                if is_paid and cat_amount > 0:
                    self.process_smart_payment(entered_amount, cycle, inst, date, is_paid, note, cat_amount, max_c, max_i, staff_id=staff_id)
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
                        is_staff_settled=False if is_paid else None
                    )
                    self.db.add(new_p)
                    self.db.commit()
                
                self.load_payments()
            except Exception as e:
                ModernDialog(self, "خطأ", f"بيانات غير صحيحة: {e}").exec()

    def edit_payment(self, pid):
        p = self.db.get(db_mod.Payment, pid)
        sub = self.db.get(db_mod.Subscriber, self.sub_id)
        cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
        cat_amount = cat.amount if cat else 0
        max_c = cat.max_cycles if cat else 10
        max_i = cat.max_installments if cat else 24

        staff_list = self.db.query(db_mod.Staff).all()
        
        dialog = PaymentDialog(self, p, max_cycles=max_c, max_inst=max_i, staff_list=staff_list)
        if dialog.exec():
            try:
                entered_amount = float(dialog.ent_amount.text())
                is_paid = (dialog.cb_paid.currentIndex() == 1)
                cycle = int(dialog.cb_cycle.currentText())
                inst = int(dialog.cb_inst.currentText())
                date = datetime.datetime.combine(dialog.ent_date.date().toPyDate(), datetime.time.min)
                note = dialog.ent_note.text()
                staff_id = dialog.cb_staff.currentData()

                if is_paid and cat_amount > 0:
                    # تعديل مباشر للقسط الموجود - لا نستخدم process_smart_payment
                    # لأنه يُنشئ سداداً جديداً إضافياً فيتضاعف المبلغ في الإجمالي
                    p.amount = entered_amount
                    p.due_date = date
                    p.is_paid = is_paid
                    p.paid_date = date if is_paid else None
                    p.installment_number = inst
                    p.cycle_number = cycle
                    p.note = note
                    p.staff_id = staff_id
                    p.is_staff_settled = False
                    self.db.commit()
                else:
                    p.amount = entered_amount
                    p.due_date = date
                    p.is_paid = is_paid
                    p.paid_date = date if is_paid else None
                    p.installment_number = inst
                    p.cycle_number = cycle
                    p.note = note
                    p.staff_id = staff_id
                    self.db.commit()
                
                self.load_payments()
            except Exception as e:
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
        
        act_del_multi = QAction("حذف العمليات المختارة", self)
        act_del_multi.triggered.connect(self.delete_selected_payments)
        
        menu.addAction(act_edit)
        menu.addAction(act_del)
        menu.addSeparator()
        menu.addAction(act_del_multi)
        menu.exec(QCursor.pos())

    def delete_payment(self, pid):
        if ModernDialog(self, "تأكيد", "هل تريد حذف هذه العملية؟", is_confirm=True).exec():
            p = self.db.get(db_mod.Payment, pid)
            if p:
                self.db.delete(p)
                self.db.commit()
                self.load_payments()

    def delete_selected_payments(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            ModernDialog(self, "تنبيه", "يرجى اختيار عملية واحدة على الأقل").exec()
            return
            
        count = len(selected_rows)
        if ModernDialog(self, "تأكيد", f"هل تريد حذف {count} عملية مختارة؟", is_confirm=True).exec():
            try:
                for index in selected_rows:
                    pid = self.table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
                    p = self.db.get(db_mod.Payment, pid)
                    if p:
                        self.db.delete(p)
                self.db.commit()
                self.load_payments()
                ModernDialog(self, "نجاح", f"تم حذف {count} عملية بنجاح").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء الحذف: {e}").exec()

class StaffActivityDialog(QDialog):
    def __init__(self, parent, staff_id, db):
        super().__init__(parent)
        self.staff_id = staff_id
        self.db = db
        staff = db.get(db_mod.Staff, staff_id)
        
        self.setWindowTitle(f"سجل تحصيلات الموظف - {staff.name}")
        self.resize(800, 550)
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
