import sys
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
    QFileDialog
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject, QThread, QDate, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette, QCursor
from sqlalchemy.orm import Session
from sqlalchemy import func
import database as db_mod
import security
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
import arabic_reshaper
from bidi.algorithm import get_display

def reshape_text(text):
    if not text: return ""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

# Global Styling - Hakbah Premium Light Theme
HAKBAH_LIGHT = """
QMainWindow { background-color: #f7f9fc; }
QWidget { color: #1e293b; font-family: 'Tajawal', sans-serif; }

/* Sidebar */
#Sidebar { background-color: #0a3d0e; border-left: none; min-width: 250px; }
#Sidebar QLabel { color: #ffffff; }
#Sidebar QPushButton { 
    background-color: transparent; 
    border: none; 
    border-radius: 8px; 
    padding: 12px; 
    text-align: right; 
    font-size: 14px; 
    font-weight: 500; 
    color: #e0e0e0; 
}
#Sidebar QPushButton:hover { background-color: #1b5e20; color: white; }
#Sidebar QPushButton#NavBtnActive { background-color: #2e7d32; color: white; font-weight: bold; }

/* Content Area */
#ContentFrame { background-color: #f7f9fc; }
QLabel#PageTitle { color: #1b5e20; font-size: 28px; font-weight: bold; }
QLabel#SectionTitle { color: #1b5e20; font-size: 20px; font-weight: bold; }

/* Cards */
QFrame#StatCard { background-color: #ffffff; border-radius: 15px; border: 1px solid #e2e8f0; }
QLabel#StatTitle { color: #64748b; font-size: 14px; }
QLabel#StatValue { font-size: 28px; font-weight: bold; }

/* Tables */
QTableWidget { 
    background-color: #ffffff; 
    border: 1px solid #e2e8f0; 
    border-radius: 10px; 
    gridline-color: #f1f5f9; 
    font-size: 13px; 
    selection-background-color: #f0fdf4; 
    selection-color: #1b5e20; 
    color: #1e293b; 
}
QTableWidget QTableCornerButton::section { background-color: #f8fafc; }
QHeaderView::section { 
    background-color: #f8fafc; 
    color: #1b5e20; 
    padding: 10px; 
    border: none; 
    font-weight: bold; 
    border-bottom: 2px solid #f1f5f9; 
}

/* Inputs */
QLineEdit, QComboBox { 
    background-color: #ffffff; 
    border: 1px solid #e2e8f0; 
    border-radius: 8px; 
    padding: 10px; 
    color: #1e293b; 
}
QLineEdit:focus { border: 1px solid #2e7d32; }

/* Buttons */
QPushButton#PrimaryBtn { background-color: #2e7d32; color: white; border-radius: 8px; padding: 10px; font-weight: bold; }
QPushButton#PrimaryBtn:hover { background-color: #1b5e20; }

QPushButton#DangerBtn { background-color: #ef4444; color: white; border-radius: 8px; padding: 10px; }
QPushButton#DangerBtn:hover { background-color: #dc2626; }

QMenu { background-color: #ffffff; border: 1px solid #e2e8f0; color: #1e293b; }
QMenu::item:selected { background-color: #f1f5f9; color: #1b5e20; }
QDialog { background-color: #ffffff; }
QScrollArea { background-color: transparent; border: none; }
QScrollArea > QWidget > QWidget { background-color: transparent; }
QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 10px; background-color: white; margin-top: -1px; }
QTabBar::tab { background-color: #f1f5f9; padding: 12px 25px; border-top-left-radius: 10px; border-top-right-radius: 10px; margin-right: 4px; color: #64748b; font-weight: 500; }
QTabBar::tab:selected { background-color: white; color: #1b5e20; font-weight: bold; border: 1px solid #e2e8f0; border-bottom: 2px solid white; }
QScrollBar:vertical { border: none; background: #f1f5f9; width: 10px; margin: 0px; }
QScrollBar::handle:vertical { background: #cbd5e1; min-height: 20px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { border: none; background: #f1f5f9; height: 10px; margin: 0px; }
QScrollBar::handle:horizontal { background: #cbd5e1; min-width: 20px; border-radius: 5px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
"""

# Global Styling - Hakbah Premium Dark Theme
HAKBAH_DARK = """
QMainWindow { background-color: #0f172a; }
QWidget { color: #f1f5f9; font-family: 'Tajawal', sans-serif; }

/* Sidebar */
#Sidebar { background-color: #052109; border-left: none; min-width: 250px; }
#Sidebar QLabel { color: #ffffff; }
#Sidebar QPushButton { 
    background-color: transparent; 
    border: none; 
    border-radius: 8px; 
    padding: 12px; 
    text-align: right; 
    font-size: 14px; 
    font-weight: 500; 
    color: #94a3b8; 
}
#Sidebar QPushButton:hover { background-color: #1b5e20; color: white; }
#Sidebar QPushButton#NavBtnActive { background-color: #2e7d32; color: white; font-weight: bold; }

/* Content Area */
#ContentFrame { background-color: #0f172a; }
QLabel#PageTitle { color: #4ade80; font-size: 28px; font-weight: bold; }
QLabel#SectionTitle { color: #4ade80; font-size: 20px; font-weight: bold; }

/* Cards */
QFrame#StatCard { background-color: #1e293b; border-radius: 15px; border: 1px solid #334155; }
QLabel#StatTitle { color: #94a3b8; font-size: 14px; }
QLabel#StatValue { color: #ffffff; font-size: 28px; font-weight: bold; }

/* Tables */
QTableWidget { 
    background-color: #1e293b; 
    border: 1px solid #334155; 
    border-radius: 10px; 
    gridline-color: #334155; 
    font-size: 13px; 
    selection-background-color: #1b5e20; 
    selection-color: white; 
    color: #f1f5f9; 
}
QTableWidget QTableCornerButton::section { background-color: #1e293b; }
QHeaderView::section { 
    background-color: #0f172a; 
    color: #4ade80; 
    padding: 10px; 
    border: none; 
    font-weight: bold; 
    border-bottom: 2px solid #334155; 
}

/* Inputs */
QLineEdit, QComboBox { 
    background-color: #1e293b; 
    border: 1px solid #334155; 
    border-radius: 8px; 
    padding: 10px; 
    color: #ffffff; 
}
QLineEdit:focus { border: 1px solid #4ade80; }

/* Buttons */
QPushButton#PrimaryBtn { background-color: #2e7d32; color: white; border-radius: 8px; padding: 10px; font-weight: bold; }
QPushButton#PrimaryBtn:hover { background-color: #1b5e20; }

QPushButton#DangerBtn { background-color: #ef4444; color: white; border-radius: 8px; padding: 10px; }
QPushButton#DangerBtn:hover { background-color: #dc2626; }

QMenu { background-color: #1e293b; border: 1px solid #334155; color: #ffffff; }
QMenu::item:selected { background-color: #2e7d32; color: white; }
QDialog { background-color: #111827; }
QScrollArea { background-color: transparent; border: none; }
QScrollArea > QWidget > QWidget { background-color: transparent; }
QTabWidget::pane { border: 1px solid #334155; border-radius: 10px; background-color: #1e293b; margin-top: -1px; }
QTabBar::tab { background-color: #0f172a; padding: 12px 25px; border-top-left-radius: 10px; border-top-right-radius: 10px; margin-right: 4px; color: #94a3b8; font-weight: 500; }
QTabBar::tab:selected { background-color: #1e293b; color: #4ade80; font-weight: bold; border: 1px solid #334155; border-bottom: 2px solid #1e293b; }
QScrollBar:vertical { border: none; background: #0f172a; width: 10px; margin: 0px; }
QScrollBar::handle:vertical { background: #334155; min-height: 20px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #475569; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { border: none; background: #0f172a; height: 10px; margin: 0px; }
QScrollBar::handle:horizontal { background: #334155; min-width: 20px; border-radius: 5px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
"""

class ServerWorker(QObject):
    link_found = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            # Creation flags for Windows to hide the console window
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            # 1. Start main.py (Web Server) in the background
            subprocess.Popen([sys.executable, "main.py"], creationflags=creation_flags)

            # 2. Start cloudflared (Tunnel)
            cloudflared_path = os.path.join(os.getcwd(), "cloudflared.exe")
            if not os.path.exists(cloudflared_path):
                self.error_occurred.emit("ملف cloudflared.exe غير موجود!")
                return

            process = subprocess.Popen(
                [cloudflared_path, "tunnel", "--url", "http://localhost:8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                creationflags=creation_flags
            )

            for line in process.stdout:
                match = re.search(r'https://[a-zA-Z0-9.-]+\.trycloudflare\.com', line)
                if match:
                    self.link_found.emit(match.group(0))
                    break
        except Exception as e:
            self.error_occurred.emit(str(e))

class QueryWorker(QObject):
    """عامل خلفي لجلب البيانات من قاعدة البيانات لتجنب تجميد الواجهة"""
    finished = pyqtSignal(list, str) # تعيد قائمة النتائج واسم الفئة

    def run_query(self, db_session, category_name=None):
        query = db_session.query(db_mod.Subscriber)
        if category_name and category_name != "الكل":
            query = query.filter(db_mod.Subscriber.category == category_name)
        subs = query.all()
        self.finished.emit(subs, category_name or "الكل")

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

class DrawAnimationDialog(QDialog):
    def __init__(self, parent, qualified_by_category, draw_name, db):
        super().__init__(parent)
        self.setWindowTitle(reshape_text(draw_name))
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
        
        self.status_label = QLabel(reshape_text("استعد للسحب..."))
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
        self.cat_label.setText(reshape_text(f"سحب فئة: {cat_name}"))
        self.status_label.setText(reshape_text("جاري تدوير عجلة الحظ..."))
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
        self.wheel_label.setStyleSheet("font-size: 130px; font-weight: 900; color: #facc15;")
        self.status_label.setText(reshape_text(f"مبروك للفائز: {winner_sub.name}"))
        
        new_w = db_mod.Winner(subscriber_number=winner_sub.subscriber_number, draw_type=f"{self.draw_name} - {cat_name}", draw_date=datetime.datetime.now())
        self.db.add(new_w); self.db.commit()
        
        QTimer.singleShot(4000, self.next_category)

    def next_category(self):
        self.current_cat_index += 1
        self.start_category_draw()

    def show_final_report(self):
        for i in reversed(range(self.layout.count())):
            if self.layout.itemAt(i).widget(): self.layout.itemAt(i).widget().setParent(None)
        
        title = QLabel(reshape_text("التقرير النهائي للفائزين")); title.setStyleSheet("font-size: 36px; color: #4ade80; font-weight: bold; margin-bottom: 20px;"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); self.layout.addWidget(title)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setStyleSheet("background: transparent; border: none;"); scroll_content = QWidget(); scroll_layout = QVBoxLayout(scroll_content)
        
        for cat, sub in self.winners:
            card = QFrame(); card.setStyleSheet("background-color: #1e293b; border-radius: 15px; border: 1px solid #334155; margin: 10px; padding: 20px;")
            h_lay = QVBoxLayout(card); info = QLabel(reshape_text(f"الفئة: {cat}\nاسم الفائز: {sub.name}\nرقم الحساب: {sub.subscriber_number}"))
            info.setStyleSheet("font-size: 20px; color: white;"); h_lay.addWidget(info); scroll_layout.addWidget(card)
        
        scroll_layout.addStretch(); scroll.setWidget(scroll_content); self.layout.addWidget(scroll)
        btn_close = QPushButton(reshape_text("إغلاق والعودة")); btn_close.setObjectName("PrimaryBtn"); btn_close.setFixedWidth(300); btn_close.setFixedHeight(50); btn_close.clicked.connect(self.accept); self.layout.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignCenter)

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
        layout.addWidget(QLabel("المبلغ الشهري:"))
        layout.addWidget(self.ent_amount)
        
        self.btn_save = QPushButton("حفظ التغييرات")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.clicked.connect(self.accept)
        layout.addWidget(self.btn_save)

class PaymentDialog(QDialog):
    def __init__(self, parent, payment=None, max_inst=24, max_cycles=10):
        super().__init__(parent)
        self.setWindowTitle("بيانات العملية المالية" if not payment else "تعديل العملية المالية")
        self.setFixedWidth(400)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.ent_amount = QLineEdit()
        self.ent_amount.setText(str(payment.amount) if payment else "")
        form.addRow("المبلغ:", self.ent_amount)
        
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
        if not self.ent_name.text() or not self.ent_phone.text() or not self.cb_cat.currentData() or not self.cb_num.currentData():
            QMessageBox.warning(self, "خطأ", "يرجى ملء جميع الحقول")
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
        
        # Subscriber List with Selection
        layout.addWidget(QLabel("اختر المشتركين:"))
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
        
        self.btn_save = QPushButton("تسجيل القيد للمختارين")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.setFixedHeight(45)
        self.btn_save.clicked.connect(self.accept)
        layout.addWidget(self.btn_save)
        
        self.load_subscribers()

    def load_subscribers(self):
        self.list_subs.clear()
        cat_id = self.cb_cat.currentData()
        
        # Reset ranges
        max_i = 24
        max_c = 10
        
        query = self.db.query(db_mod.Subscriber)
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
        
        subs = query.all()
        for s in subs:
            item = QListWidgetItem(f"{s.name} ({s.phone})")
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list_subs.addItem(item)

    def get_selected_ids(self):
        ids = []
        for i in range(self.list_subs.count()):
            item = self.list_subs.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

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
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["التاريخ", "المبلغ", "القسط", "الدورة", "الحالة", "الملاحظة"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
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
        try:
            sub = self.db.get(db_mod.Subscriber, self.sub_id)
            payments = self.db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == self.sub_id).all()
            data = [{
                "التاريخ": p.due_date.strftime("%Y-%m-%d"),
                "المبلغ": p.amount,
                "القسط": p.installment_number,
                "الدورة": p.cycle_number,
                "الحالة": "مدفوع" if p.is_paid else "غير مدفوع",
                "الملاحظة": p.note
            } for p in payments]
            df = pd.DataFrame(data)
            filename = f"statement_{sub.phone}.xlsx"
            df.to_excel(filename, index=False)
            ModernDialog(self, "نجاح", f"تم تصدير {filename} بنجاح").exec()
        except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()

    def export_history_pdf(self):
        try:
            sub = self.db.get(db_mod.Subscriber, self.sub_id)
            payments = self.db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == self.sub_id).all()
            filename = f"statement_{sub.phone}.pdf"
            c = canvas.Canvas(filename, pagesize=A4)
            width, height = A4
            
            font_path = "C:/Windows/Fonts/arial.ttf"
            try: pdfmetrics.registerFont(TTFont('ArabicFont', font_path)); c.setFont('ArabicFont', 10)
            except: c.setFont('Helvetica', 10)

            c.drawString(width/2 - 100, height - 50, reshape_text(f"كشف حساب: {sub.name}"))
            y = height - 100
            headers = ["التاريخ", "المبلغ", "القسط", "الدورة", "الحالة", "الملاحظة"]
            for i, h in enumerate(headers): c.drawString(40 + i*80, y, reshape_text(h))
            y -= 20
            
            for p in payments:
                if y < 50: c.showPage(); y = height - 50
                c.drawString(40, y, p.due_date.strftime("%Y-%m-%d"))
                c.drawString(120, y, f"{p.amount:,.2f}")
                c.drawString(200, y, str(p.installment_number))
                c.drawString(280, y, str(p.cycle_number))
                c.drawString(360, y, reshape_text("مدفوع" if p.is_paid else "غير مدفوع"))
                c.drawString(440, y, reshape_text(p.note or "-"))
                y -= 20
            c.save()
            ModernDialog(self, "نجاح", f"تم تصدير {filename} بنجاح").exec()
        except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()

    def load_payments(self):
        payments = self.db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == self.sub_id).order_by(db_mod.Payment.due_date.asc()).all()
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
            is_arrear = not p.is_paid and p.due_date < now
            is_partial_balance = p.note and ("(متبقي من" in p.note)
            
            bg_color = None
            if is_arrear:
                bg_color = QColor("#fee2e2") # أحمر فاتح للمتأخرات
            elif is_partial_balance:
                bg_color = QColor("#fff7ed") # برتقالي فاتح للمتبقي من سداد جزئي

            items = [
                QTableWidgetItem(p.due_date.strftime("%Y-%m-%d")),
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

    def process_smart_payment(self, total_amount, cycle, inst, date, is_paid, note, cat_amount, max_c, max_i):
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
                # سداد جزئي لمتأخرة موجودة
                balance = p.amount - remaining
                p.amount = remaining
                p.is_paid = True
                p.paid_date = date
                p.note = (note or "") + " تم سداد جزء من القسط"

                # حفظ المتبقي
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
                existing_note = str(p.note or "")
                if "متبقي" in existing_note:
                    p.note = (note or "") + " تم سداد باقي القسط الجزئي"
                elif p.cycle_number < cycle or (p.cycle_number == cycle and p.installment_number < inst):
                    p.note = (note or "") + " تم سداد القسط المتاخر"
                else:
                    p.note = (note or "") + " تم سداد القسط"
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

                if pay_now < cat_amount:
                    new_note = (note or "") + " تم سداد جزء من القسط"
                else:
                    if curr_c == cycle and curr_i == inst:
                        new_note = (note or "") + " تم سداد القسط"
                    else:
                        new_note = (note or "") + " قسط مقدم"

                new_p = db_mod.Payment(
                    subscriber_id=self.sub_id,
                    amount=pay_now,
                    due_date=date,
                    paid_date=date,
                    is_paid=True,
                    cycle_number=curr_c,
                    installment_number=curr_i,
                    note=new_note
                )
                self.db.add(new_p)

                if pay_now < cat_amount:
                    # إنشاء سجل المتبقي في التوزيع المستقبلي
                    self.db.add(db_mod.Payment(
                        subscriber_id=self.sub_id,
                        amount=cat_amount - pay_now,
                        due_date=date,
                        is_paid=False,
                        cycle_number=curr_c,
                        installment_number=curr_i,
                        note="متبقي من دفع جزئي"
                    ))
                    remaining = 0
                else:
                    remaining -= pay_now

                curr_i += 1
                if curr_i > max_i: curr_i = 1; curr_c += 1
        
        self.db.commit()
        return True

    def add_payment(self):
        sub = self.db.get(db_mod.Subscriber, self.sub_id)
        cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
        cat_amount = cat.amount if cat else 0
        max_c = cat.max_cycles if cat else 10
        max_i = cat.max_installments if cat else 24
        
        dialog = PaymentDialog(self, max_cycles=max_c, max_inst=max_i)
        if dialog.exec():
            try:
                entered_amount = float(dialog.ent_amount.text())
                is_paid = (dialog.cb_paid.currentIndex() == 1)
                cycle = int(dialog.cb_cycle.currentText())
                inst = int(dialog.cb_inst.currentText())
                date = datetime.datetime.combine(dialog.ent_date.date().toPyDate(), datetime.time.min)
                note = dialog.ent_note.text()

                if is_paid and cat_amount > 0:
                    self.process_smart_payment(entered_amount, cycle, inst, date, is_paid, note, cat_amount, max_c, max_i)
                else:
                    new_p = db_mod.Payment(
                        subscriber_id=self.sub_id,
                        amount=entered_amount,
                        due_date=date,
                        is_paid=is_paid,
                        paid_date=date if is_paid else None,
                        installment_number=inst,
                        cycle_number=cycle,
                        note=note
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
        
        dialog = PaymentDialog(self, p, max_cycles=max_c, max_inst=max_i)
        if dialog.exec():
            try:
                entered_amount = float(dialog.ent_amount.text())
                is_paid = (dialog.cb_paid.currentIndex() == 1)
                cycle = int(dialog.cb_cycle.currentText())
                inst = int(dialog.cb_inst.currentText())
                date = datetime.datetime.combine(dialog.ent_date.date().toPyDate(), datetime.time.min)
                note = dialog.ent_note.text()

                if is_paid and cat_amount > 0:
                    self.process_smart_payment(entered_amount, cycle, inst, date, is_paid, note, cat_amount, max_c, max_i)
                else:
                    p.amount = entered_amount
                    p.due_date = date
                    p.is_paid = is_paid
                    p.paid_date = date if is_paid else None
                    p.installment_number = inst
                    p.cycle_number = cycle
                    p.note = note
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

class AdminApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("لوحة تحكم هكبة المليون - Premium PyQt6 Edition")
        self.resize(1300, 850)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        db_mod.init_db()
        self.db = db_mod.SessionLocal()
        self.public_url = ""
        
        self.setup_ui()
        self.apply_styles()
        self.show_dashboard()
        
        # تشغيل فحص الأقساط المتأخرة تلقائياً عند بدء البرنامج وكل ساعة
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_unpaid_installments)
        self.sync_timer.start(3600000) # 3600000 مللي ثانية = 1 ساعة
        QTimer.singleShot(2000, self.sync_unpaid_installments) # تشغيل أول مرة بعد ثانيتين من الفتح

    def apply_styles(self):
        theme_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "admin_theme").first()
        theme = theme_setting.value if theme_setting else "dark"
        self.setStyleSheet(HAKBAH_DARK if theme == "dark" else HAKBAH_LIGHT)

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
            ("إدارة القرعة", self.show_draw_management),
            ("أداة التقارير", self.show_reports),
            ("إعدادات الفئات", self.show_settings),
            ("إعدادات الرسائل", self.show_messaging)
        ]
        
        for text, func in nav_items:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            sidebar_layout.addWidget(btn)
            self.nav_btns[text] = btn

        sidebar_layout.addStretch()
        
        btn_exit = QPushButton("خروج من البرنامج")
        btn_exit.setObjectName("DangerBtn")
        btn_exit.clicked.connect(self.close)
        sidebar_layout.addWidget(btn_exit)

        main_layout.addWidget(self.sidebar)

        # Content Area
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("ContentFrame")
        main_layout.addWidget(self.content_stack, 1)

        # Initialize Pages
        self.page_dashboard = self.init_dashboard_page()
        self.page_subscribers = self.init_subscribers_page()
        self.page_settings = self.init_settings_page()
        self.page_cycles = self.init_cycles_page()
        self.page_capital = self.init_capital_page()
        self.page_messaging = self.init_messaging_page()
        self.page_reports = self.init_reports_page()
        self.page_draw = self.init_draw_page()

        self.content_stack.addWidget(self.page_dashboard)
        self.content_stack.addWidget(self.page_subscribers)
        self.content_stack.addWidget(self.page_settings)
        self.content_stack.addWidget(self.page_cycles)
        self.content_stack.addWidget(self.page_capital)
        self.content_stack.addWidget(self.page_messaging)
        self.content_stack.addWidget(self.page_reports)
        self.content_stack.addWidget(self.page_draw)

    def _update_nav_style(self, active_text):
        for text, btn in self.nav_btns.items():
            if text == active_text: btn.setObjectName("NavBtnActive")
            else: btn.setObjectName("")
            btn.style().unpolish(btn); btn.style().polish(btn)

    def init_dashboard_page(self):
        page = QScrollArea()
        page.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        title = QLabel("إحصائيات النظام")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Server Control
        server_card = QFrame(); server_card.setObjectName("StatCard")
        server_layout = QVBoxLayout(server_card); server_layout.setContentsMargins(30, 30, 30, 30)

        self.btn_start_server = QPushButton("تشغيل الموقع ونظام الربط (Cloudflare)")
        self.btn_start_server.setObjectName("PrimaryBtn")
        self.btn_start_server.setFixedHeight(55)
        self.btn_start_server.clicked.connect(self.start_web_server)
        server_layout.addWidget(self.btn_start_server)

        self.lbl_public_link = QLabel("رابط الموقع: سيظهر هنا بعد التشغيل")
        self.lbl_public_link.setStyleSheet("color: #94a3b8; font-size: 15px; margin-top: 10px;")
        server_layout.addWidget(self.lbl_public_link)

        self.btn_copy_link = QPushButton("نسخ الرابط العام")
        self.btn_copy_link.setFixedWidth(150)
        self.btn_copy_link.setObjectName("PrimaryBtn")
        self.btn_copy_link.clicked.connect(self.copy_link)
        self.btn_copy_link.hide()
        server_layout.addWidget(self.btn_copy_link)
        layout.addWidget(server_card)

        # Reg Toggle
        reg_card = QFrame(); reg_card.setObjectName("StatCard")
        reg_layout = QHBoxLayout(reg_card); reg_layout.setContentsMargins(20, 20, 20, 20)
        reg_layout.addWidget(QLabel("حالة التسجيل في الموقع"))
        self.reg_switch = QCheckBox()
        reg_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "registration_open").first()
        self.reg_switch.setChecked(True if reg_setting and reg_setting.value == "true" else False)
        self.reg_switch.stateChanged.connect(self.toggle_reg)
        reg_layout.addStretch(); reg_layout.addWidget(self.reg_switch)
        layout.addWidget(reg_card)

        # Stats
        self.stats_grid = QHBoxLayout(); self.stats_grid.setSpacing(20)
        layout.addLayout(self.stats_grid)

        layout.addStretch(); page.setWidget(container)
        return page

    def start_web_server(self):
        self.lbl_public_link.setText("جاري تشغيل الموقع واستخراج الرابط... يرجى الانتظار")
        self.btn_start_server.setEnabled(False)
        self.thread = QThread()
        self.worker = ServerWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.link_found.connect(self._on_server_link_found)
        self.worker.error_occurred.connect(self._on_server_error)
        self.thread.start()

    def _on_server_link_found(self, url):
        self.public_url = url
        self.lbl_public_link.setText(f"الرابط العام: {url}")
        self.btn_copy_link.show()
        ModernDialog(self, "نجاح", "الموقع متاح الآن للمشتركين").exec()

    def _on_server_error(self, err):
        self.btn_start_server.setEnabled(True)
        ModernDialog(self, "خطأ", f"حدث خطأ: {err}").exec()

    def copy_link(self):
        QApplication.clipboard().setText(self.public_url)
        ModernDialog(self, "نجاح", "تم نسخ الرابط").exec()

    def toggle_reg(self):
        val = "true" if self.reg_switch.isChecked() else "false"
        self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "registration_open").update({"value": val})
        self.db.commit()

    def refresh_stats(self):
        self.db.expire_all()
        for i in reversed(range(self.stats_grid.count())): self.stats_grid.itemAt(i).widget().setParent(None)
        items = [("إجمالي المشتركين", self.db.query(db_mod.Subscriber).count(), "#2e7d32")]
        colors = ["#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444"]
        for i, cat in enumerate(self.db.query(db_mod.Category).all()):
            count = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == cat.name).count()
            items.append((cat.name, count, colors[i % len(colors)]))

        for title, value, color in items:
            card = QFrame(); card.setObjectName("StatCard"); card.setMinimumHeight(120)
            vbox = QVBoxLayout(card); vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t_lbl = QLabel(title); t_lbl.setObjectName("StatTitle"); t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(t_lbl)
            v_lbl = QLabel(str(value)); v_lbl.setObjectName("StatValue"); v_lbl.setStyleSheet(f"color: {color};"); v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(v_lbl)
            self.stats_grid.addWidget(card)

    def init_subscribers_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(40, 40, 40, 40); layout.setSpacing(20)
        header = QHBoxLayout(); title = QLabel("إدارة المشتركين"); title.setObjectName("PageTitle"); header.addWidget(title)
        
        btn_batch = QPushButton("القيد المتعدد")
        btn_batch.setFixedWidth(150)
        btn_batch.setObjectName("PrimaryBtn")
        btn_batch.clicked.connect(self.open_batch_payment)
        
        btn_add = QPushButton("إضافة مشترك جديد")
        btn_add.setObjectName("PrimaryBtn")
        btn_add.setFixedHeight(35)
        btn_add.clicked.connect(self.add_new_subscriber)
        header.addWidget(btn_add)
        
        btn_refresh = QPushButton("تحديث البيانات")
        btn_refresh.setFixedWidth(150)
        btn_refresh.setObjectName("PrimaryBtn")
        btn_refresh.clicked.connect(self.load_subscribers)
        
        btn_excel = QPushButton("تصدير Excel")
        btn_excel.setFixedWidth(120)
        btn_excel.setObjectName("PrimaryBtn")
        btn_excel.clicked.connect(self.export_subscribers_excel)
        
        btn_pdf = QPushButton("تصدير PDF")
        btn_pdf.setFixedWidth(120)
        btn_pdf.setObjectName("DangerBtn")
        btn_pdf.clicked.connect(self.export_subscribers_pdf)
        
        header.addStretch()
        header.addWidget(btn_excel)
        header.addWidget(btn_pdf)
        header.addWidget(btn_batch)
        header.addWidget(btn_refresh)
        layout.addLayout(header)
        
        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs)
        return page

    def load_subscribers(self):
        """تحميل المشتركين باستخدام خيط خلفي لتحسين الأداء"""
        self.db.expire_all()
        self.setUpdatesEnabled(False) # تعطيل الرسم مؤقتاً لتسريع العملية
        try:
            self.sub_tabs.clear()
            # جلب الفئات أولاً
            categories = self.db.query(db_mod.Category).all()
            
            # إضافة تبويب "الكل"
            subs_all = self.db.query(db_mod.Subscriber).all()
            self.sub_tabs.addTab(self.create_sub_cards_view(subs_all), "الكل")
            
            # إضافة تبويبات الفئات
            for cat in categories:
                subs = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == cat.name).all()
                self.sub_tabs.addTab(self.create_sub_cards_view(subs), cat.name)
        finally:
            self.setUpdatesEnabled(True) # إعادة تفعيل الرسم

    def create_sub_cards_view(self, subs):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")
        
        if not subs:
            container = QWidget()
            lay = QVBoxLayout(container)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel("لا يوجد مشتركين في هذه الفئة حالياً")
            lbl.setFont(QFont("Tajawal", 12))
            lbl.setStyleSheet("color: #64748b; padding: 40px;")
            lay.addWidget(lbl)
            scroll.setWidget(container)
            return scroll
            
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        grid = QGridLayout(container)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(20)
        
        # تحسين الأداء: استخدام الحد الأدنى من التخطيطات
        # يفضل في المستقبل الانتقال لـ QListView مع Custom Delegate
        container.setUpdatesEnabled(False)
        
        columns = 3  # 3 columns grid
        for idx, s in enumerate(subs):
            row = idx // columns
            col = idx % columns
            
            card = self.create_subscriber_card(s)
            grid.addWidget(card, row, col)
            
        # Add stretch row and column to align elements nicely
        grid.setRowStretch(grid.rowCount(), 1)
        
        container.setUpdatesEnabled(True)
        
        scroll.setWidget(container)
        return scroll

    def create_subscriber_card(self, s):
        card = QFrame()
        card.setObjectName("StatCard")
        card.setMinimumHeight(240)
        card.setMinimumWidth(280)
        card.setStyleSheet("""
            QFrame#StatCard {
                background: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(226, 232, 240, 0.8);
                border-radius: 16px;
            }
            QFrame#StatCard:hover {
                background: rgba(255, 255, 255, 0.95);
                border: 1px solid #3b82f6;
            }
        """)
        
        card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pos: self.show_subscriber_card_context_menu(pos, s.id))
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header Row: Avatar + Name & Category Pill
        header_lay = QHBoxLayout()
        header_lay.setSpacing(12)
        
        # Circular Avatar with Initials
        avatar = QLabel()
        avatar.setFixedSize(48, 48)
        # Extract initials
        parts = s.name.strip().split()
        initials = "".join([p[0] for p in parts if p][:2]) if parts else "م"
        avatar.setText(initials)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Tajawal", 12, QFont.Weight.Bold))
        
        # High-end dynamic gradients
        gradient_list = [
            ("qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #3b82f6, stop:1 #1d4ed8)", "white"),
            ("qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #10b981, stop:1 #047857)", "white"),
            ("qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #8b5cf6, stop:1 #6d28d9)", "white"),
            ("qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #f59e0b, stop:1 #b45309)", "white"),
            ("qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #ec4899, stop:1 #be185d)", "white")
        ]
        gradient, text_color = gradient_list[s.id % len(gradient_list)]
        avatar.setStyleSheet(f"""
            background: {gradient};
            color: {text_color};
            border-radius: 24px;
        """)
        header_lay.addWidget(avatar)
        
        # Name and Phone
        info_lay = QVBoxLayout()
        info_lay.setSpacing(3)
        
        name_lbl = QLabel(s.name)
        name_lbl.setFont(QFont("Tajawal", 12, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #1e293b;")
        info_lay.addWidget(name_lbl)
        
        phone_lbl = QLabel(s.phone)
        phone_lbl.setFont(QFont("Tajawal", 9))
        phone_lbl.setStyleSheet("color: #64748b;")
        info_lay.addWidget(phone_lbl)
        
        header_lay.addLayout(info_lay)
        header_lay.addStretch()
        
        # Category Pill
        cat_pill = QLabel(s.category or "بدون فئة")
        cat_pill.setFont(QFont("Tajawal", 8, QFont.Weight.Bold))
        cat_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cat_pill.setStyleSheet("""
            background: #e0f2fe;
            color: #0369a1;
            padding: 4px 10px;
            border-radius: 10px;
        """)
        header_lay.addWidget(cat_pill)
        
        layout.addLayout(header_lay)
        
        # Divider Line
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("background-color: #f1f5f9; max-height: 1px;")
        layout.addWidget(divider)
        
        # Stats Details
        stats_lay = QGridLayout()
        stats_lay.setSpacing(8)
        
        lbl_acc_title = QLabel("رقم الحساب:")
        lbl_acc_title.setFont(QFont("Tajawal", 9))
        lbl_acc_title.setStyleSheet("color: #94a3b8;")
        stats_lay.addWidget(lbl_acc_title, 0, 0)
        
        lbl_acc_val = QLabel(s.subscriber_number or "-")
        lbl_acc_val.setFont(QFont("Tajawal", 10, QFont.Weight.Bold))
        lbl_acc_val.setStyleSheet("color: #334155;")
        stats_lay.addWidget(lbl_acc_val, 0, 1)
        
        paid_count = self.db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == s.id, db_mod.Payment.is_paid == True).count()
        lbl_paid_title = QLabel("الأقساط المسددة:")
        lbl_paid_title.setFont(QFont("Tajawal", 9))
        lbl_paid_title.setStyleSheet("color: #94a3b8;")
        stats_lay.addWidget(lbl_paid_title, 1, 0)
        
        lbl_paid_val = QLabel(f"{paid_count} أقساط")
        lbl_paid_val.setFont(QFont("Tajawal", 10, QFont.Weight.Bold))
        lbl_paid_val.setStyleSheet("color: #10b981;")
        stats_lay.addWidget(lbl_paid_val, 1, 1)
        
        total_paid = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.subscriber_id == s.id, db_mod.Payment.is_paid == True).scalar() or 0
        lbl_total_title = QLabel("إجمالي المدفوع:")
        lbl_total_title.setFont(QFont("Tajawal", 9))
        lbl_total_title.setStyleSheet("color: #94a3b8;")
        stats_lay.addWidget(lbl_total_title, 2, 0)
        
        lbl_total_val = QLabel(f"{total_paid:,.2f} ر.ي")
        lbl_total_val.setFont(QFont("Tajawal", 10, QFont.Weight.Bold))
        lbl_total_val.setStyleSheet("color: #1e3a8a;")
        stats_lay.addWidget(lbl_total_val, 2, 1)
        
        layout.addLayout(stats_lay)
        
        # Action Buttons Row
        actions_lay = QHBoxLayout()
        actions_lay.setSpacing(6)
        
        btn_details = QPushButton("كشف حساب")
        btn_details.setObjectName("PrimaryBtn")
        btn_details.setFixedHeight(28)
        btn_details.setStyleSheet("font-size: 11px;")
        btn_details.clicked.connect(lambda checked, sid=s.id: self.open_account_details(sid))
        actions_lay.addWidget(btn_details, 2)
        
        btn_edit = QPushButton("تعديل")
        btn_edit.setObjectName("PrimaryBtn")
        btn_edit.setFixedHeight(28)
        btn_edit.setStyleSheet("font-size: 11px; background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1;")
        btn_edit.clicked.connect(lambda checked, sid=s.id: self.edit_subscriber(sid))
        actions_lay.addWidget(btn_edit, 1)
        
        btn_del = QPushButton("حذف")
        btn_del.setObjectName("DangerBtn")
        btn_del.setFixedHeight(28)
        btn_del.setStyleSheet("font-size: 11px;")
        btn_del.clicked.connect(lambda checked, sid=s.id: self.delete_subscriber(sid))
        actions_lay.addWidget(btn_del, 1)
        
        layout.addLayout(actions_lay)

        # تفعيل فتح كشف الحساب عند النقر المزدوج على البطاقة
        card.mouseDoubleClickEvent = lambda event: self.open_account_details(s.id)

        return card

    def show_subscriber_card_context_menu(self, pos, sid):
        menu = QMenu(self)
        
        act_edit = QAction("تعديل", self)
        act_edit.triggered.connect(lambda: self.edit_subscriber(sid))
        
        act_details = QAction("كشف حساب", self)
        act_details.triggered.connect(lambda: self.open_account_details(sid))
        
        act_del = QAction("حذف", self)
        act_del.triggered.connect(lambda: self.delete_subscriber(sid))
        
        menu.addAction(act_edit)
        menu.addAction(act_details)
        menu.addSeparator()
        menu.addAction(act_del)
        menu.exec(QCursor.pos())

    def edit_subscriber(self, sid):
        sub = self.db.get(db_mod.Subscriber, sid)
        dialog = SubscriberEditDialog(self, sub)
        if dialog.exec():
            try:
                sub.name = dialog.ent_name.text(); sub.phone = dialog.ent_phone.text(); sub.subscriber_number = dialog.ent_acc.text()
                if dialog.ent_pwd.text(): sub.password = security.hash_password(dialog.ent_pwd.text())
                self.db.commit(); self.load_subscribers()
                ModernDialog(self, "نجاح", "تم التعديل").exec()
            except Exception as e: self.db.rollback(); ModernDialog(self, "خطأ", str(e)).exec()

    def delete_subscriber(self, sid):
        if ModernDialog(self, "تأكيد", "حذف المشترك؟", is_confirm=True).exec():
            sub = self.db.get(db_mod.Subscriber, sid)
            if sub:
                num = self.db.query(db_mod.SubscriberNumber).filter(db_mod.SubscriberNumber.subscriber_id == sid).first()
                if num: num.is_reserved = False; num.subscriber_id = None
                self.db.delete(sub); self.db.commit(); self.load_subscribers()

    def add_new_subscriber(self):
        dlg = AddSubscriberDialog(self, self.db)
        if dlg.exec():
            try:
                name = dlg.ent_name.text()
                phone = dlg.ent_phone.text()
                cat_name = dlg.cb_cat.currentText()
                sub_num_text = dlg.cb_num.currentText()
                sub_num_id = dlg.cb_num.currentData()
                
                # 1. Create Subscriber
                new_sub = db_mod.Subscriber(
                    name=name,
                    phone=phone,
                    category=cat_name,
                    subscriber_number=sub_num_text,
                    status="accepted",
                    selected_number_id=sub_num_id
                )
                self.db.add(new_sub)
                self.db.flush() # To get ID
                
                # 2. Reserve the number
                sub_num_obj = self.db.get(db_mod.SubscriberNumber, sub_num_id)
                sub_num_obj.is_reserved = True
                sub_num_obj.subscriber_id = new_sub.id
                
                self.db.commit()
                self.load_subscribers()
                ModernDialog(self, "نجاح", f"تم إضافة المشترك {name} بنجاح").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"فشل الإضافة: {e}").exec()

    def open_account_details(self, sid):
        AccountDetailsDialog(self, sid, self.db).exec()

    def open_batch_payment(self):
        dialog = BatchPaymentDialog(self, self.db)
        if dialog.exec():
            selected_ids = dialog.get_selected_ids()
            if not selected_ids:
                ModernDialog(self, "تنبيه", "يرجى اختيار مشترك واحد على الأقل").exec()
                return
            
            try:
                amount = float(dialog.ent_amount.text())
                due_date = datetime.datetime.combine(dialog.ent_date.date().toPyDate(), datetime.time.min)
                inst = int(dialog.cb_inst.currentText())
                cycle = int(dialog.cb_cycle.currentText())
                note = dialog.ent_note.text()
                
                for sid in selected_ids:
                    new_p = db_mod.Payment(
                        subscriber_id=sid,
                        amount=amount,
                        due_date=due_date,
                        is_paid=True, # Batch entries are usually marked as paid
                        installment_number=inst,
                        cycle_number=cycle,
                        note=note
                    )
                    self.db.add(new_p)
                
                self.db.commit()
                ModernDialog(self, "نجاح", f"تم تسجيل القيد لـ {len(selected_ids)} مشترك بنجاح").exec()
                self.load_subscribers()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء التسجيل: {e}").exec()

    def show_sub_context_menu(self, pos, table):
        row = table.rowAt(pos.y())
        if row < 0: return
        
        sid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        
        act_edit = QAction("تعديل", self)
        act_edit.triggered.connect(lambda: self.edit_subscriber(sid))
        
        act_del = QAction("حذف", self)
        act_del.triggered.connect(lambda: self.delete_subscriber(sid))
        
        act_details = QAction("كشف حساب", self)
        act_details.triggered.connect(lambda: self.open_account_details(sid))
        
        menu.addAction(act_edit)
        menu.addAction(act_details)
        menu.addSeparator()
        menu.addAction(act_del)
        menu.exec(QCursor.pos())

    def init_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        title = QLabel("إعدادات الفئات والنظام")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        
        self.settings_tabs = QTabWidget()
        
        # --- TAB 1: Categories Management ---
        tab1 = QScrollArea(); tab1.setWidgetResizable(True)
        con1 = QWidget(); lay1 = QVBoxLayout(con1); lay1.setContentsMargins(20, 20, 20, 20); lay1.setSpacing(25)
        
        # Theme Switch
        theme_card = QFrame(); theme_card.setObjectName("StatCard"); theme_lay = QHBoxLayout(theme_card); theme_lay.setContentsMargins(20, 20, 20, 20)
        theme_lay.addWidget(QLabel("ثيم لوحة التحكم (داكن / فاتح):"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["الوضع الداكن", "الوضع الفاتح"])
        theme_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "admin_theme").first()
        if theme_setting and theme_setting.value == "light": self.theme_combo.setCurrentIndex(1)
        self.theme_combo.currentIndexChanged.connect(lambda i: self.set_theme("dark" if i == 0 else "light"))
        theme_lay.addStretch(); theme_lay.addWidget(self.theme_combo)
        lay1.addWidget(theme_card)
        
        # Add Category
        f1 = QFrame(); f1.setObjectName("StatCard"); v_lay1 = QVBoxLayout(f1)
        v_lay1.addWidget(QLabel("إضافة فئة جديدة"))
        form_cat = QFormLayout()
        self.en1 = QLineEdit(); self.en2 = QLineEdit(); form_cat.addRow("اسم الفئة:", self.en1); form_cat.addRow("المبلغ الشهري:", self.en2)
        v_lay1.addLayout(form_cat)
        ba = QPushButton("إضافة فئة"); ba.setObjectName("PrimaryBtn"); ba.clicked.connect(self.add_category); v_lay1.addWidget(ba)
        
        v_lay1.addWidget(QLabel("الفئات الحالية:"))
        self.table_cats = QTableWidget()
        self.table_cats.setColumnCount(3)
        self.table_cats.setHorizontalHeaderLabels(["اسم الفئة", "المبلغ", "إجراء"])
        self.table_cats.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_cats.setMinimumHeight(300)
        v_lay1.addWidget(self.table_cats)
        lay1.addWidget(f1)
        
        lay1.addStretch()
        tab1.setWidget(con1)
        self.settings_tabs.addTab(tab1, "إدارة الفئات")
        
        # --- TAB 2: Numbers Management ---
        tab2 = QScrollArea(); tab2.setWidgetResizable(True)
        con2 = QWidget(); lay2 = QVBoxLayout(con2); lay2.setContentsMargins(20, 20, 20, 20); lay2.setSpacing(25)
        
        f2 = QFrame(); f2.setObjectName("StatCard"); l2 = QVBoxLayout(f2)
        l2.addWidget(QLabel("توليد أرقام المشتركين"))
        num_form = QFormLayout()
        self.com = QComboBox(); self.com.currentIndexChanged.connect(self.refresh_numbers_list)
        self.en_prefix = QLineEdit(); self.en_prefix.setPlaceholderText("مثال: A-")
        self.en_start = QLineEdit(); self.en_start.setPlaceholderText("1")
        self.en_end = QLineEdit(); self.en_end.setPlaceholderText("100")
        num_form.addRow("اختر الفئة:", self.com)
        num_form.addRow("البادئة (Prefix):", self.en_prefix)
        num_form.addRow("من رقم:", self.en_start)
        num_form.addRow("إلى رقم:", self.en_end)
        l2.addLayout(num_form)
        bs = QPushButton("توليد وحفظ الأرقام"); bs.setObjectName("PrimaryBtn"); bs.clicked.connect(self.add_numbers); l2.addWidget(bs)
        
        l2.addWidget(QLabel("الأرقام المسجلة في هذه الفئة:"))
        self.table_nums = QTableWidget()
        self.table_nums.setColumnCount(3)
        self.table_nums.setHorizontalHeaderLabels(["الرقم", "الحالة", "إجراء"])
        self.table_nums.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_nums.setMinimumHeight(400)
        l2.addWidget(self.table_nums)
        lay2.addWidget(f2)
        
        lay2.addStretch()
        tab2.setWidget(con2)
        self.settings_tabs.addTab(tab2, "إدارة الأرقام")
        
        layout.addWidget(self.settings_tabs)
        self.refresh_cat_list()
        return page

    def refresh_cat_list(self):
        self.com.clear()
        cats = self.db.query(db_mod.Category).all()
        for c in cats: self.com.addItem(c.name, c.id)
        self.refresh_numbers_list()
        self.refresh_cat_table(cats)

    def refresh_cat_table(self, cats):
        self.table_cats.setRowCount(len(cats))
        for i, c in enumerate(cats):
            self.table_cats.setItem(i, 0, QTableWidgetItem(c.name))
            self.table_cats.setItem(i, 1, QTableWidgetItem(f"{c.amount:,.2f}"))
            
            # Action buttons container
            container = QWidget()
            btn_layout = QHBoxLayout(container)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(5)

            btn_edit = QPushButton("تعديل")
            btn_edit.setObjectName("PrimaryBtn")
            btn_edit.setStyleSheet("background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; font-size: 11px;")
            btn_edit.clicked.connect(lambda checked, cid=c.id: self.edit_category(cid))
            btn_layout.addWidget(btn_edit)

            btn_del = QPushButton("حذف")
            btn_del.setObjectName("DangerBtn")
            btn_del.setStyleSheet("font-size: 11px;")
            btn_del.clicked.connect(lambda checked, cid=c.id: self.delete_category(cid))
            btn_layout.addWidget(btn_del)

            self.table_cats.setCellWidget(i, 2, container)

    def refresh_numbers_list(self):
        cat_id = self.com.currentData()
        if not cat_id:
            self.table_nums.setRowCount(0)
            return
            
        nums = self.db.query(db_mod.SubscriberNumber).filter(db_mod.SubscriberNumber.category_id == cat_id).all()
        self.table_nums.setRowCount(len(nums))
        for i, n in enumerate(nums):
            self.table_nums.setItem(i, 0, QTableWidgetItem(n.number))
            
            status = "محجوز" if n.is_reserved else "متاح"
            st_item = QTableWidgetItem(status)
            if n.is_reserved: st_item.setForeground(QColor("#ef4444"))
            else: st_item.setForeground(QColor("#2e7d32"))
            self.table_nums.setItem(i, 1, st_item)
            
            btn_del = QPushButton("حذف")
            btn_del.setObjectName("DangerBtn")
            btn_del.setEnabled(not n.is_reserved)
            btn_del.clicked.connect(lambda checked, nid=n.id: self.delete_number(nid))
            self.table_nums.setCellWidget(i, 2, btn_del)

    def add_category(self):
        name = self.en1.text().strip()
        amount_str = self.en2.text().strip()
        
        if not name or not amount_str:
            ModernDialog(self, "خطأ", "يرجى ملء جميع الحقول").exec()
            return
            
        try:
            amount = float(amount_str)
            # Check if name exists
            exists = self.db.query(db_mod.Category).filter(db_mod.Category.name == name).first()
            if exists:
                ModernDialog(self, "خطأ", "هذا الاسم موجود بالفعل").exec()
                return
                
            self.db.add(db_mod.Category(name=name, amount=amount))
            self.db.commit()
            self.en1.clear(); self.en2.clear(); self.refresh_cat_list()
            ModernDialog(self, "نجاح", "تمت إضافة الفئة بنجاح").exec()
        except ValueError:
            ModernDialog(self, "خطأ", "المبلغ يجب أن يكون رقماً").exec()

    def edit_category(self, cid):
        cat = self.db.get(db_mod.Category, cid)
        if not cat: return
        
        dialog = CategoryEditDialog(self, cat)
        if dialog.exec():
            try:
                old_name = cat.name
                new_name = dialog.ent_name.text().strip()
                new_amount_str = dialog.ent_amount.text().strip()
                
                if not new_name or not new_amount_str:
                    ModernDialog(self, "خطأ", "يرجى ملء جميع الحقول").exec()
                    return
                    
                new_amount = float(new_amount_str)
                
                if new_name != old_name:
                    exists = self.db.query(db_mod.Category).filter(db_mod.Category.name == new_name).first()
                    if exists:
                        ModernDialog(self, "خطأ", "هذا الاسم موجود بالفعل").exec()
                        return
                    # Update all subscribers with the new category name string
                    self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == old_name).update({db_mod.Subscriber.category: new_name})
                
                cat.name = new_name
                cat.amount = new_amount
                self.db.commit()
                self.refresh_cat_list()
                ModernDialog(self, "نجاح", "تم تعديل الفئة بنجاح").exec()
            except ValueError:
                ModernDialog(self, "خطأ", "المبلغ يجب أن يكون رقماً").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ: {e}").exec()

    def delete_category(self, cid):
        # Check if category has subscribers
        cat = self.db.get(db_mod.Category, cid)
        if not cat: return
        
        sub_count = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == cat.name).count()
        if sub_count > 0:
            ModernDialog(self, "خطأ", f"لا يمكن حذف هذه الفئة لوجود {sub_count} مشترك فيها").exec()
            return
            
        if ModernDialog(self, "تأكيد", f"هل أنت متأكد من حذف الفئة '{cat.name}'؟ سيتم حذف جميع الأرقام المرتبطة بها أيضاً.", is_confirm=True).exec():
            # Delete numbers first
            self.db.query(db_mod.SubscriberNumber).filter(db_mod.SubscriberNumber.category_id == cid).delete()
            self.db.delete(cat)
            self.db.commit()
            self.refresh_cat_list()

    def add_numbers(self):
        cat_id = self.com.currentData()
        if not cat_id: return
        
        prefix = self.en_prefix.text().strip()
        try:
            start = int(self.en_start.text().strip())
            end = int(self.en_end.text().strip())
            
            if start > end:
                ModernDialog(self, "خطأ", "رقم البداية يجب أن يكون أصغر من رقم النهاية").exec()
                return
                
            count = 0
            for i in range(start, end + 1):
                num_str = f"{prefix}{i}"
                # Check if exists
                exists = self.db.query(db_mod.SubscriberNumber).filter(
                    db_mod.SubscriberNumber.category_id == cat_id,
                    db_mod.SubscriberNumber.number == num_str
                ).first()
                
                if not exists:
                    self.db.add(db_mod.SubscriberNumber(number=num_str, category_id=cat_id))
                    count += 1
            
            self.db.commit()
            self.refresh_numbers_list()
            ModernDialog(self, "نجاح", f"تمت إضافة {count} رقم جديد").exec()
            self.en_start.clear(); self.en_end.clear()
        except ValueError:
            ModernDialog(self, "خطأ", "يرجى إدخال أرقام صحيحة للبداية والنهاية").exec()

    def delete_number(self, nid):
        if ModernDialog(self, "تأكيد", "هل أنت متأكد من حذف هذا الرقم؟", is_confirm=True).exec():
            n = self.db.get(db_mod.SubscriberNumber, nid)
            if n and not n.is_reserved:
                self.db.delete(n)
                self.db.commit()
                self.refresh_numbers_list()

    def init_capital_page(self):
        page = QScrollArea()
        page.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        title = QLabel("إدارة رأس المال والتدفق المالي")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        
        # Stats Grid
        self.capital_stats_layout = QHBoxLayout()
        self.capital_stats_layout.setSpacing(20)
        layout.addLayout(self.capital_stats_layout)
        
        # Tabs
        self.capital_tabs = QTabWidget()
        layout.addWidget(self.capital_tabs)
        
        # Tab 1: Categories summary
        self.tab_cap_categories = QWidget()
        t1_layout = QVBoxLayout(self.tab_cap_categories)
        t1_layout.setContentsMargins(20, 20, 20, 20)
        t1_layout.setSpacing(20)
        
        t1_header = QHBoxLayout()
        t1_header.addWidget(QLabel("تحليل السيولة ورأس المال حسب الفئات"))
        t1_header.addStretch()
        btn_cat_cap_excel = QPushButton("تصدير Excel للفئات")
        btn_cat_cap_excel.setObjectName("PrimaryBtn")
        btn_cat_cap_excel.clicked.connect(self.export_categories_financial_excel)
        t1_header.addWidget(btn_cat_cap_excel)
        t1_layout.addLayout(t1_header)
        
        self.table_cap_categories = QTableWidget()
        self.table_cap_categories.setColumnCount(7)
        self.table_cap_categories.setHorizontalHeaderLabels([
            "اسم الفئة", "قيمة الاشتراك شهرياً", "عدد المشتركين", 
            "رأس المال المتوقع", "رأس المال المحصل", "المبالغ المتبقية", "نسبة التحصيل"
        ])
        self.table_cap_categories.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_cap_categories.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t1_layout.addWidget(self.table_cap_categories)
        
        self.capital_tabs.addTab(self.tab_cap_categories, "تحليل الفئات والسيولة")
        
        # Tab 2: Defaulters / Unpaid
        self.tab_cap_defaulters = QWidget()
        t2_layout = QVBoxLayout(self.tab_cap_defaulters)
        t2_layout.setContentsMargins(20, 20, 20, 20)
        t2_layout.setSpacing(20)
        
        t2_header = QHBoxLayout()
        t2_header.addWidget(QLabel("الفئة:"))
        self.cap_filter_cat = QComboBox()
        self.cap_filter_cat.currentIndexChanged.connect(self.refresh_capital_defaulters)
        t2_header.addWidget(self.cap_filter_cat)
        
        t2_header.addWidget(QLabel("بحث:"))
        self.cap_search_def = QLineEdit()
        self.cap_search_def.setPlaceholderText("ابحث باسم المشترك أو الهاتف...")
        self.cap_search_def.textChanged.connect(self.refresh_capital_defaulters)
        t2_header.addWidget(self.cap_search_def, 1)
        
        btn_def_excel = QPushButton("تصدير كشف المتأخرات")
        btn_def_excel.setObjectName("PrimaryBtn")
        btn_def_excel.clicked.connect(self.export_defaulters_excel)
        t2_header.addWidget(btn_def_excel)
        t2_layout.addLayout(t2_header)
        
        self.table_cap_defaulters = QTableWidget()
        self.table_cap_defaulters.setColumnCount(7)
        self.table_cap_defaulters.setHorizontalHeaderLabels([
            "المشترك", "الهاتف", "الفئة", "الدورة/القسط", "تاريخ الاستحقاق", "المبلغ المستحق", "إجراء سريع"
        ])
        self.table_cap_defaulters.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_cap_defaulters.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # تفعيل النقر المزدوج لفتح كشف الحساب من جدول المتأخرات
        self.table_cap_defaulters.cellDoubleClicked.connect(lambda r, c: self.open_account_details(self.table_cap_defaulters.item(r, 0).data(Qt.ItemDataRole.UserRole)))
        t2_layout.addWidget(self.table_cap_defaulters)
        
        self.capital_tabs.addTab(self.tab_cap_defaulters, "الأقساط غير المسددة (المتأخرات)")
        
        # Tab 3: General financial standing
        self.tab_cap_standing = QWidget()
        t3_layout = QVBoxLayout(self.tab_cap_standing)
        t3_layout.setContentsMargins(20, 20, 20, 20)
        t3_layout.setSpacing(20)
        
        t3_header = QHBoxLayout()
        t3_header.addWidget(QLabel("الموقف المالي للمشتركين:"))
        self.cap_search_standing = QLineEdit()
        self.cap_search_standing.setPlaceholderText("ابحث باسم المشترك أو الهاتف...")
        self.cap_search_standing.textChanged.connect(self.refresh_capital_standing)
        t3_header.addWidget(self.cap_search_standing, 1)
        t3_layout.addLayout(t3_header)
        
        self.table_cap_standing = QTableWidget()
        self.table_cap_standing.setColumnCount(6)
        self.table_cap_standing.setHorizontalHeaderLabels([
            "اسم المشترك", "الفئة", "رقم الحساب", "إجمالي المستحق", "إجمالي المسدد", "الرصيد المتبقي"
        ])
        self.table_cap_standing.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_cap_standing.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_cap_standing.cellDoubleClicked.connect(lambda r, c: self.open_account_details(self.table_cap_standing.item(r, 0).data(Qt.ItemDataRole.UserRole)))
        t3_layout.addWidget(self.table_cap_standing)
        
        self.capital_tabs.addTab(self.tab_cap_standing, "المواقف المالية للمشتركين")

        # Tab 4: Operational Expenses
        self.tab_cap_expenses = QWidget()
        t4_layout = QVBoxLayout(self.tab_cap_expenses)
        t4_layout.setContentsMargins(20, 20, 20, 20)
        t4_layout.setSpacing(20)
        
        t4_upper = QHBoxLayout()
        t4_upper.setSpacing(15)
        
        form_card = QFrame()
        form_card.setObjectName("StatCard")
        form_card.setMinimumHeight(150)
        form_lay = QGridLayout(form_card)
        form_lay.setContentsMargins(15, 15, 15, 15)
        form_lay.setSpacing(10)
        
        form_lay.addWidget(QLabel("إضافة نفقة تشغيلية جديدة:"), 0, 0, 1, 2)
        
        form_lay.addWidget(QLabel("البيان / الوصف:"), 1, 0)
        self.exp_title_input = QLineEdit()
        self.exp_title_input.setPlaceholderText("مثال: تكلفة رسائل SMS...")
        form_lay.addWidget(self.exp_title_input, 1, 1)
        
        form_lay.addWidget(QLabel("المبلغ (ر.ي):"), 1, 2)
        self.exp_amount_input = QLineEdit()
        self.exp_amount_input.setPlaceholderText("0.00")
        form_lay.addWidget(self.exp_amount_input, 1, 3)
        
        form_lay.addWidget(QLabel("التصنيف:"), 2, 0)
        self.exp_cat_combo = QComboBox()
        self.exp_cat_combo.addItems(["سيرفرات وتقنية", "رسائل SMS", "رواتب وأجور", "تسويق وإعلانات", "أخرى"])
        form_lay.addWidget(self.exp_cat_combo, 2, 1)
        
        form_lay.addWidget(QLabel("ملاحظات:"), 2, 2)
        self.exp_note_input = QLineEdit()
        self.exp_note_input.setPlaceholderText("اختياري...")
        form_lay.addWidget(self.exp_note_input, 2, 3)
        
        btn_add_exp = QPushButton("إضافة النفقة")
        btn_add_exp.setObjectName("PrimaryBtn")
        btn_add_exp.clicked.connect(self.add_new_expense)
        form_lay.addWidget(btn_add_exp, 2, 4)
        
        t4_upper.addWidget(form_card)
        t4_layout.addLayout(t4_upper)
        
        t4_header = QHBoxLayout()
        t4_header.addWidget(QLabel("جدول النفقات التشغيلية:"))
        
        self.exp_search_input = QLineEdit()
        self.exp_search_input.setPlaceholderText("ابحث باسم النفقة أو الملاحظات...")
        self.exp_search_input.textChanged.connect(self.refresh_capital_expenses)
        t4_header.addWidget(self.exp_search_input, 1)
        
        btn_exp_excel = QPushButton("تصدير كشف المصاريف")
        btn_exp_excel.setObjectName("PrimaryBtn")
        btn_exp_excel.clicked.connect(self.export_expenses_excel)
        t4_header.addWidget(btn_exp_excel)
        t4_layout.addLayout(t4_header)
        
        self.table_cap_expenses = QTableWidget()
        self.table_cap_expenses.setColumnCount(6)
        self.table_cap_expenses.setHorizontalHeaderLabels([
            "البيان / الوصف", "المبلغ (ر.ي)", "التصنيف", "التاريخ والوقت", "الملاحظات", "إجراء"
        ])
        self.table_cap_expenses.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_cap_expenses.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t4_layout.addWidget(self.table_cap_expenses)
        
        self.capital_tabs.addTab(self.tab_cap_expenses, "النفقات التشغيلية")
        
        page.setWidget(container)
        return page

    def show_capital_management(self):
        self.content_stack.setCurrentWidget(self.page_capital)
        self._update_nav_style("إدارة رأس المال")
        
        # Populate Category filters
        self.cap_filter_cat.blockSignals(True)
        self.cap_filter_cat.clear()
        self.cap_filter_cat.addItem("كل الفئات", None)
        for cat in self.db.query(db_mod.Category).all():
            self.cap_filter_cat.addItem(cat.name, cat.name)
        self.cap_filter_cat.blockSignals(False)
        
        self.refresh_capital_stats()
        self.refresh_capital_categories()
        self.refresh_capital_defaulters()
        self.refresh_capital_standing()
        self.refresh_capital_expenses()

    def sync_unpaid_installments(self):
        """تقوم هذه الدالة بإضافة أقساط غير مسددة تلقائياً للأيام التي مضت ولم يسدد فيها المشترك"""
        try:
            now_date = datetime.datetime.now().date()
            subscribers = self.db.query(db_mod.Subscriber).all()
            
            for sub in subscribers:
                # جلب بيانات الفئة لمعرفة تاريخ البدء والمبلغ
                cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
                if not cat or not cat.start_date:
                    continue
                
                # التحقق من آخر قسط مسجل لهذا المشترك
                last_p = self.db.query(db_mod.Payment).filter(
                    db_mod.Payment.subscriber_id == sub.id
                ).order_by(db_mod.Payment.due_date.desc()).first()
                
                # تحديد تاريخ بدء الفحص (إما تاريخ بدء الفئة أو اليوم التالي لآخر قسط)
                if last_p:
                    current_check = last_p.due_date.date() + datetime.timedelta(days=1)
                else:
                    # نبدأ من تاريخ بدء الفئة أو تاريخ انضمام المشترك (أيهما أحدث)
                    current_check = max(cat.start_date.date() if cat.start_date else now_date, sub.created_at.date() if sub.created_at else now_date)
                
                # إضافة أقساط "غير مسددة" لكل يوم مضى حتى تاريخ اليوم
                while current_check <= now_date:
                    total_days = (current_check - cat.start_date.date()).days
                    cycle = (total_days // cat.max_installments) + 1
                    inst = (total_days % cat.max_installments) + 1
                    
                    if cycle <= cat.max_cycles:
                        new_p = db_mod.Payment(
                            subscriber_id=sub.id,
                            amount=cat.amount,
                            due_date=datetime.datetime.combine(current_check, datetime.time.min),
                            is_paid=False,
                            cycle_number=cycle,
                            installment_number=inst,
                            note="قسط يومي غير مسدد"
                        )
                        self.db.add(new_p)
                    current_check += datetime.timedelta(days=1)
            
            self.db.commit()
        except Exception as e:
            print(f"Error during auto-sync: {e}")
            self.db.rollback()

    def refresh_capital_stats(self):
        self.db.expire_all()
        # Clear stats
        for i in reversed(range(self.capital_stats_layout.count())):
            widget = self.capital_stats_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
            
        # Queries
        # حساب رأس المال المتوقع بناءً على جميع السجلات المولدة للمشتركين المقبولين بدقة
        total_expected = self.db.query(func.sum(db_mod.Payment.amount)).join(db_mod.Subscriber).filter(
            db_mod.Subscriber.status == "accepted"
        ).scalar() or 0

        total_collected = self.db.query(func.sum(db_mod.Payment.amount)).join(db_mod.Subscriber).filter(
            db_mod.Subscriber.status == "accepted",
            db_mod.Payment.is_paid == True
        ).scalar() or 0

        total_remaining = total_expected - total_collected
        total_arrears = self.db.query(func.sum(db_mod.Payment.amount)).join(db_mod.Subscriber).filter(
            db_mod.Subscriber.status == "accepted",
            db_mod.Payment.is_paid == False, 
            db_mod.Payment.due_date < datetime.datetime.now()
        ).scalar() or 0
        total_expenses = self.db.query(func.sum(db_mod.Expense.amount)).scalar() or 0
        
        net_cash = total_collected - total_expenses
        
        stats = [
            ("رأس المال المستهدف (الإجمالي)", f"{total_expected:,.2f} ر.ي", "#3b82f6"),
            ("المبالغ المحصلة (الإيرادات)", f"{total_collected:,.2f} ر.ي", "#2e7d32"),
            ("إجمالي المبالغ المتبقية", f"{total_remaining:,.2f} ر.ي", "#f59e0b"),
            ("الأقساط المتأخرة (المستحقة)", f"{total_arrears:,.2f} ر.ي", "#ef4444"),
            ("صافي السيولة النقدية", f"{net_cash:,.2f} ر.ي", "#06b6d4" if net_cash >= 0 else "#ef4444")
        ]
        
        for title, value, color in stats:
            card = QFrame()
            card.setObjectName("StatCard")
            card.setMinimumHeight(120)
            vbox = QVBoxLayout(card)
            vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            t_lbl = QLabel(title)
            t_lbl.setObjectName("StatTitle")
            t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(t_lbl)
            
            v_lbl = QLabel(value)
            v_lbl.setObjectName("StatValue")
            v_lbl.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold;")
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(v_lbl)
            
            self.capital_stats_layout.addWidget(card)

    def refresh_capital_categories(self):
        categories = self.db.query(db_mod.Category).all()
        self.table_cap_categories.setRowCount(len(categories))
        
        for i, cat in enumerate(categories):
            subs_count = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == cat.name).all()
            sub_ids = [s.id for s in subs_count]
            
            subs_accepted = self.db.query(db_mod.Subscriber).filter(
                db_mod.Subscriber.category == cat.name,
                db_mod.Subscriber.status == "accepted"
            ).all()
            sub_ids = [s.id for s in subs_accepted]
            
            expected = 0
            collected = 0
            if sub_ids:
                expected = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.subscriber_id.in_(sub_ids)).scalar() or 0
                collected = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.subscriber_id.in_(sub_ids), db_mod.Payment.is_paid == True).scalar() or 0
            
            remaining = expected - collected

            ratio = (collected / expected * 100) if expected > 0 else 0
            
            self.table_cap_categories.setItem(i, 0, QTableWidgetItem(cat.name))
            self.table_cap_categories.setItem(i, 1, QTableWidgetItem(f"{cat.amount:,.2f}"))
            self.table_cap_categories.setItem(i, 2, QTableWidgetItem(str(len(sub_ids))))
            self.table_cap_categories.setItem(i, 3, QTableWidgetItem(f"{expected:,.2f}"))
            self.table_cap_categories.setItem(i, 4, QTableWidgetItem(f"{collected:,.2f}"))
            self.table_cap_categories.setItem(i, 5, QTableWidgetItem(f"{remaining:,.2f}"))
            
            ratio_item = QTableWidgetItem(f"{ratio:.1f}%")
            ratio_item.setForeground(QColor("#2e7d32" if ratio >= 80 else "#f59e0b" if ratio >= 50 else "#ef4444"))
            ratio_item.setFont(QFont("Tajawal", 9, QFont.Weight.Bold))
            self.table_cap_categories.setItem(i, 6, ratio_item)

    def refresh_capital_defaulters(self):
        # Query unpaid payments
        query = self.db.query(db_mod.Payment).join(db_mod.Subscriber).filter(
            db_mod.Payment.is_paid == False,
            db_mod.Payment.due_date < datetime.datetime.now())
        
        # Category filter
        sel_cat = self.cap_filter_cat.currentData()
        if sel_cat:
            query = query.filter(db_mod.Subscriber.category == sel_cat)
            
        # Search text filter
        search_txt = self.cap_search_def.text().strip()
        if search_txt:
            query = query.filter((db_mod.Subscriber.name.like(f"%{search_txt}%")) | (db_mod.Subscriber.phone.like(f"%{search_txt}%")))
            
        unpaid_payments = query.order_by(db_mod.Payment.due_date.asc()).all()
        self.table_cap_defaulters.setRowCount(len(unpaid_payments))
        
        for i, p in enumerate(unpaid_payments):
            sub = self.db.get(db_mod.Subscriber, p.subscriber_id)
            
            # تخزين معرف المشترك لتمكين النقر المزدوج
            name_item = QTableWidgetItem(sub.name)
            name_item.setData(Qt.ItemDataRole.UserRole, sub.id)
            
            items = [
                name_item,
                QTableWidgetItem(sub.phone),
                QTableWidgetItem(sub.category or "-"),
                QTableWidgetItem(f"دورة {p.cycle_number} - قسط {p.installment_number}"),
                QTableWidgetItem(p.due_date.strftime("%Y-%m-%d")),
                QTableWidgetItem(f"{p.amount:,.2f}")
            ]
            
            # تلوين جميع صفوف جدول المتأخرات لتمييزها
            bg_color = QColor("#fee2e2")
            for col, item in enumerate(items):
                item.setBackground(bg_color)
                self.table_cap_defaulters.setItem(i, col, item)
            
            # Action Button
            btn_pay = QPushButton("سداد سريع")
            btn_pay.setObjectName("PrimaryBtn")
            btn_pay.setStyleSheet("padding: 3px 8px; font-size: 11px;")
            btn_pay.clicked.connect(lambda checked, pid=p.id: self.quick_pay_payment(pid))
            self.table_cap_defaulters.setCellWidget(i, 6, btn_pay)

    def quick_pay_payment(self, pid):
        p = self.db.get(db_mod.Payment, pid)
        if not p: return
        sub = self.db.get(db_mod.Subscriber, p.subscriber_id)
        msg = f"هل تريد تأكيد سداد الدورة {p.cycle_number} - القسط {p.installment_number} للمشترك {sub.name} بمبلغ {p.amount:,.2f} ر.ي؟"
        if ModernDialog(self, "تأكيد السداد السريع", msg, is_confirm=True).exec():
            try:
                p.is_paid = True
                p.paid_date = datetime.datetime.now()
                self.db.commit()
                ModernDialog(self, "نجاح", "تم تسجيل السداد بنجاح").exec()
                
                # Refresh tables
                self.refresh_capital_stats()
                self.refresh_capital_categories()
                self.refresh_capital_defaulters()
                self.refresh_capital_standing()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء السداد: {e}").exec()

    def refresh_capital_standing(self):
        query = self.db.query(db_mod.Subscriber)
        
        search_txt = self.cap_search_standing.text().strip()
        if search_txt:
            query = query.filter((db_mod.Subscriber.name.like(f"%{search_txt}%")) | (db_mod.Subscriber.phone.like(f"%{search_txt}%")))
            
        subs = query.all()
        self.table_cap_standing.setRowCount(len(subs))
        
        for i, s in enumerate(subs):
            expected = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.subscriber_id == s.id).scalar() or 0
            collected = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.subscriber_id == s.id, db_mod.Payment.is_paid == True).scalar() or 0
            remaining = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.subscriber_id == s.id, db_mod.Payment.is_paid == False).scalar() or 0
            
            name_item = QTableWidgetItem(s.name)
            name_item.setData(Qt.ItemDataRole.UserRole, s.id)
            
            self.table_cap_standing.setItem(i, 0, name_item)
            self.table_cap_standing.setItem(i, 1, QTableWidgetItem(s.category or "-"))
            self.table_cap_standing.setItem(i, 2, QTableWidgetItem(s.subscriber_number or "-"))
            self.table_cap_standing.setItem(i, 3, QTableWidgetItem(f"{expected:,.2f}"))
            self.table_cap_standing.setItem(i, 4, QTableWidgetItem(f"{collected:,.2f}"))
            
            rem_item = QTableWidgetItem(f"{remaining:,.2f}")
            if remaining > 0:
                rem_item.setForeground(QColor("#ef4444"))
                rem_item.setFont(QFont("Tajawal", 9, QFont.Weight.Bold))
            self.table_cap_standing.setItem(i, 5, rem_item)

    def export_categories_financial_excel(self):
        try:
            categories = self.db.query(db_mod.Category).all()
            data = []
            for cat in categories:
                subs_count = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == cat.name).all()
                sub_ids = [s.id for s in subs_count]
                
                expected = 0
                collected = 0
                remaining = 0
                
                if sub_ids:
                    expected = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.subscriber_id.in_(sub_ids)).scalar() or 0
                    collected = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.subscriber_id.in_(sub_ids), db_mod.Payment.is_paid == True).scalar() or 0
                    remaining = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.subscriber_id.in_(sub_ids), db_mod.Payment.is_paid == False).scalar() or 0
                    
                ratio = (collected / expected * 100) if expected > 0 else 0
                
                data.append({
                    "اسم الفئة": cat.name,
                    "قيمة الاشتراك شهرياً": cat.amount,
                    "عدد المشتركين": len(sub_ids),
                    "رأس المال المتوقع": expected,
                    "رأس المال المحصل": collected,
                    "المبالغ المتبقية": remaining,
                    "نسبة التحصيل": f"{ratio:.1f}%"
                })
            
            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير سيولة الفئات", "categories_financial_report.xlsx", "Excel Files (*.xlsx)")
            if file_path:
                df.to_excel(file_path, index=False)
                ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {e}").exec()

    def export_defaulters_excel(self):
        try:
            query = self.db.query(db_mod.Payment).join(db_mod.Subscriber).filter(db_mod.Payment.is_paid == False)
            
            sel_cat = self.cap_filter_cat.currentData()
            if sel_cat:
                query = query.filter(db_mod.Subscriber.category == sel_cat)
                
            unpaid_payments = query.order_by(db_mod.Payment.due_date.asc()).all()
            
            data = []
            for p in unpaid_payments:
                sub = self.db.get(db_mod.Subscriber, p.subscriber_id)
                data.append({
                    "المشترك": sub.name,
                    "الهاتف": sub.phone,
                    "الفئة": sub.category or "-",
                    "الدورة والقسط": f"دورة {p.cycle_number} - قسط {p.installment_number}",
                    "تاريخ الاستحقاق": p.due_date.strftime("%Y-%m-%d"),
                    "المبلغ المستحق": p.amount
                })
                
            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير المتأخرات", "unpaid_installments_report.xlsx", "Excel Files (*.xlsx)")
            if file_path:
                df.to_excel(file_path, index=False)
                ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {e}").exec()

    def refresh_capital_expenses(self):
        query = self.db.query(db_mod.Expense)
        
        search_txt = self.exp_search_input.text().strip()
        if search_txt:
            query = query.filter((db_mod.Expense.title.like(f"%{search_txt}%")) | (db_mod.Expense.note.like(f"%{search_txt}%")))
            
        expenses = query.order_by(db_mod.Expense.date.desc()).all()
        self.table_cap_expenses.setRowCount(len(expenses))
        
        for i, e in enumerate(expenses):
            self.table_cap_expenses.setItem(i, 0, QTableWidgetItem(e.title))
            self.table_cap_expenses.setItem(i, 1, QTableWidgetItem(f"{e.amount:,.2f}"))
            self.table_cap_expenses.setItem(i, 2, QTableWidgetItem(e.category or "-"))
            self.table_cap_expenses.setItem(i, 3, QTableWidgetItem(e.date.strftime("%Y-%m-%d %H:%M")))
            self.table_cap_expenses.setItem(i, 4, QTableWidgetItem(e.note or "-"))
            
            # Delete Button
            btn_del = QPushButton("حذف")
            btn_del.setObjectName("DangerBtn")
            btn_del.setStyleSheet("padding: 3px 8px; font-size: 11px;")
            btn_del.clicked.connect(lambda checked, eid=e.id: self.delete_expense(eid))
            self.table_cap_expenses.setCellWidget(i, 5, btn_del)

    def add_new_expense(self):
        title = self.exp_title_input.text().strip()
        amount_str = self.exp_amount_input.text().strip()
        category = self.exp_cat_combo.currentText()
        note = self.exp_note_input.text().strip()
        
        if not title:
            ModernDialog(self, "خطأ", "يرجى إدخال اسم النفقة أو وصفها").exec()
            return
            
        try:
            amount = float(amount_str)
            if amount <= 0:
                ModernDialog(self, "خطأ", "يجب أن يكون مبلغ النفقة أكبر من صفر").exec()
                return
        except ValueError:
            ModernDialog(self, "خطأ", "يرجى إدخال مبلغ صحيح (رقم)").exec()
            return
            
        try:
            new_exp = db_mod.Expense(
                title=title,
                amount=amount,
                category=category,
                note=note if note else None,
                date=datetime.datetime.now()
            )
            self.db.add(new_exp)
            self.db.commit()
            
            # Clear inputs
            self.exp_title_input.clear()
            self.exp_amount_input.clear()
            self.exp_note_input.clear()
            
            ModernDialog(self, "نجاح", "تمت إضافة النفقة التشغيلية بنجاح").exec()
            
            # Refresh dashboard
            self.refresh_capital_stats()
            self.refresh_capital_expenses()
        except Exception as err:
            self.db.rollback()
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء الإضافة: {err}").exec()

    def delete_expense(self, eid):
        exp = self.db.get(db_mod.Expense, eid)
        if not exp: return
        
        msg = f"هل تريد تأكيد حذف النفقة التشغيلية: {exp.title} بمبلغ {exp.amount:,.2f} ر.ي؟"
        if ModernDialog(self, "تأكيد الحذف", msg, is_confirm=True).exec():
            try:
                self.db.delete(exp)
                self.db.commit()
                ModernDialog(self, "نجاح", "تم حذف سجل النفقة بنجاح").exec()
                
                # Refresh dashboard
                self.refresh_capital_stats()
                self.refresh_capital_expenses()
            except Exception as err:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء الحذف: {err}").exec()

    def export_expenses_excel(self):
        try:
            query = self.db.query(db_mod.Expense)
            
            search_txt = self.exp_search_input.text().strip()
            if search_txt:
                query = query.filter((db_mod.Expense.title.like(f"%{search_txt}%")) | (db_mod.Expense.note.like(f"%{search_txt}%")))
                
            expenses = query.order_by(db_mod.Expense.date.desc()).all()
            
            data = []
            for e in expenses:
                data.append({
                    "البيان / الوصف": e.title,
                    "المبلغ (ر.س)": e.amount,
                    "التصنيف": e.category or "-",
                    "التاريخ والوقت": e.date.strftime("%Y-%m-%d %H:%M"),
                    "الملاحظات": e.note or "-"
                })
                
            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ كشف النفقات التشغيلية", "operational_expenses_report.xlsx", "Excel Files (*.xlsx)")
            if file_path:
                df.to_excel(file_path, index=False)
                ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as err:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {err}").exec()

    def show_dashboard(self): self.content_stack.setCurrentWidget(self.page_dashboard); self._update_nav_style("الإحصائيات"); self.refresh_stats()
    def show_subscribers(self): self.content_stack.setCurrentWidget(self.page_subscribers); self._update_nav_style("المشتركين"); self.load_subscribers()
    def show_settings(self): self.content_stack.setCurrentWidget(self.page_settings); self._update_nav_style("إعدادات الفئات"); self.refresh_cat_list()
    def show_cycles(self): self.content_stack.setCurrentWidget(self.page_cycles); self._update_nav_style("إدارة الدورات والأقساط"); self.refresh_cycles_cat_list()
    def show_messaging(self): self.content_stack.setCurrentWidget(self.page_messaging); self._update_nav_style("إعدادات الرسائل"); self.load_messaging_settings()
    def show_reports(self): 
        self.content_stack.setCurrentWidget(self.page_reports)
        self._update_nav_style("أداة التقارير")
        self.refresh_reports_sub_list()
        self.refresh_uploaded_reports()

    def upload_new_report(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "اختر التقرير للرفع", "", "All Files (*);;PDF Files (*.pdf);;Excel Files (*.xlsx *.xls)")
        if file_path:
            try:
                upload_dir = "uploaded_reports"
                if not os.path.exists(upload_dir): os.makedirs(upload_dir)
                
                filename = os.path.basename(file_path)
                dest_path = os.path.join(upload_dir, filename)
                
                # Check for duplicates
                if os.path.exists(dest_path):
                    if not ModernDialog(self, "تنبيه", "هذا الملف موجود بالفعل، هل تريد استبداله؟", is_confirm=True).exec():
                        return
                
                shutil.copy2(file_path, dest_path)
                self.refresh_uploaded_reports()
                ModernDialog(self, "نجاح", f"تم رفع الملف {filename} بنجاح").exec()
            except Exception as e: ModernDialog(self, "خطأ", f"فشل الرفع: {e}").exec()

    def refresh_uploaded_reports(self):
        self.list_uploaded_reports.clear()
        upload_dir = "uploaded_reports"
        if os.path.exists(upload_dir):
            files = os.listdir(upload_dir)
            for f in files:
                item = QListWidgetItem(f)
                item.setIcon(QIcon.fromTheme("document-new"))
                self.list_uploaded_reports.addItem(item)

    def open_uploaded_file(self, filename):
        file_path = os.path.abspath(os.path.join("uploaded_reports", filename))
        if os.path.exists(file_path):
            try:
                if sys.platform == "win32": os.startfile(file_path)
                else: subprocess.run(["open", file_path] if sys.platform == "darwin" else ["xdg-open", file_path])
            except Exception as e: ModernDialog(self, "خطأ", f"فشل فتح الملف: {e}").exec()

    def show_upload_context_menu(self, pos):
        item = self.list_uploaded_reports.itemAt(pos)
        if not item: return
        
        filename = item.text()
        menu = QMenu(self)
        
        act_open = QAction("فتح الملف", self)
        act_open.triggered.connect(lambda: self.open_uploaded_file(filename))
        
        act_del = QAction("حذف الملف", self)
        act_del.triggered.connect(lambda: self.delete_uploaded_file(filename))
        
        menu.addAction(act_open)
        menu.addAction(act_del)
        menu.exec(QCursor.pos())

    def delete_uploaded_file(self, filename):
        if ModernDialog(self, "تأكيد", f"هل أنت متأكد من حذف الملف {filename} نهائياً؟", is_confirm=True).exec():
            try:
                os.remove(os.path.join("uploaded_reports", filename))
                self.refresh_uploaded_reports()
            except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()

    def init_reports_page(self):
        page = QScrollArea(); page.setWidgetResizable(True); container = QWidget(); layout = QVBoxLayout(container); layout.setContentsMargins(40, 40, 40, 40); layout.setSpacing(30)
        title = QLabel("أداة التقارير"); title.setObjectName("PageTitle"); layout.addWidget(title)

        # 1. Subscriber Report
        sub_card = QFrame(); sub_card.setObjectName("StatCard"); s_layout = QVBoxLayout(sub_card); s_layout.setSpacing(15)
        s_title = QLabel("كشف حساب مشترك"); s_title.setObjectName("SectionTitle"); s_layout.addWidget(s_title)
        
        row1 = QHBoxLayout()
        self.rep_sub_cb = QComboBox()
        self.rep_sub_cb.setEditable(True)
        self.rep_sub_cb.setPlaceholderText("اختر أو ابحث عن مشترك...")
        row1.addWidget(QLabel("المشترك:"))
        row1.addWidget(self.rep_sub_cb, 1)
        
        btn_sub_ex = QPushButton("تصدير Excel")
        btn_sub_ex.clicked.connect(lambda: self.generate_subscriber_report("excel"))
        btn_sub_pdf = QPushButton("تصدير PDF")
        btn_sub_pdf.setObjectName("DangerBtn")
        btn_sub_pdf.clicked.connect(lambda: self.generate_subscriber_report("pdf"))
        
        row1.addWidget(btn_sub_ex); row1.addWidget(btn_sub_pdf)
        s_layout.addLayout(row1)
        layout.addWidget(sub_card)

        # 2. Winners & Categories
        row2 = QHBoxLayout(); row2.setSpacing(20)
        
        win_card = QFrame(); win_card.setObjectName("StatCard"); w_layout = QVBoxLayout(win_card)
        w_layout.addWidget(QLabel("تقرير الفائزين")); w_layout.addStretch()
        btn_win = QPushButton("توليد تقرير الفائزين (Excel)"); btn_win.setObjectName("PrimaryBtn")
        btn_win.clicked.connect(self.generate_winners_report)
        w_layout.addWidget(btn_win)
        row2.addWidget(win_card)
        
        cat_card = QFrame(); cat_card.setObjectName("StatCard"); c_layout = QVBoxLayout(cat_card)
        c_layout.addWidget(QLabel("تقرير الفئات العام")); c_layout.addStretch()
        btn_cat = QPushButton("توليد تقرير الفئات (PDF)"); btn_cat.setObjectName("PrimaryBtn")
        btn_cat.clicked.connect(self.generate_categories_report)
        c_layout.addWidget(btn_cat)
        row2.addWidget(cat_card)
        
        layout.addLayout(row2)

        # 3. Custom Report
        cust_card = QFrame(); cust_card.setObjectName("StatCard"); cu_layout = QVBoxLayout(cust_card); cu_layout.setSpacing(15)
        cu_title = QLabel("تقرير مخصص / مفصل"); cu_title.setObjectName("SectionTitle"); cu_layout.addWidget(cu_title)
        
        form = QFormLayout()
        self.rep_date_start = QDateEdit(); self.rep_date_start.setCalendarPopup(True); self.rep_date_start.setDate(QDate.currentDate().addMonths(-1))
        self.rep_date_end = QDateEdit(); self.rep_date_end.setCalendarPopup(True); self.rep_date_end.setDate(QDate.currentDate())
        self.rep_status = QComboBox(); self.rep_status.addItems(["الكل", "مدفوع", "غير مدفوع"])
        self.rep_cat_filter = QComboBox()
        
        form.addRow("من تاريخ:", self.rep_date_start)
        form.addRow("إلى تاريخ:", self.rep_date_end)
        form.addRow("الحالة:", self.rep_status)
        form.addRow("الفئة:", self.rep_cat_filter)
        cu_layout.addLayout(form)
        
        btn_cust = QPushButton("توليد التقرير المخصص (Excel)"); btn_cust.setObjectName("PrimaryBtn"); btn_cust.setFixedHeight(45)
        btn_cust.clicked.connect(self.generate_custom_report)
        cu_layout.addWidget(btn_cust)
        
        layout.addWidget(cust_card)

        # 4. Upload Center
        up_card = QFrame(); up_card.setObjectName("StatCard"); up_layout = QVBoxLayout(up_card); up_layout.setSpacing(15)
        up_title = QLabel("مركز رفع التقارير والمستندات"); up_title.setObjectName("SectionTitle"); up_layout.addWidget(up_title)
        
        row_up = QHBoxLayout()
        btn_upload = QPushButton("رفع ملف جديد")
        btn_upload.setObjectName("PrimaryBtn")
        btn_upload.setFixedHeight(40)
        btn_upload.clicked.connect(self.upload_new_report)
        row_up.addWidget(btn_upload); row_up.addStretch()
        up_layout.addLayout(row_up)
        
        self.list_uploaded_reports = QListWidget()
        self.list_uploaded_reports.setMinimumHeight(150)
        self.list_uploaded_reports.itemDoubleClicked.connect(lambda item: self.open_uploaded_file(item.text()))
        self.list_uploaded_reports.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_uploaded_reports.customContextMenuRequested.connect(self.show_upload_context_menu)
        up_layout.addWidget(self.list_uploaded_reports)
        
        layout.addWidget(up_card)

        layout.addStretch(); page.setWidget(container); return page

    def refresh_reports_sub_list(self):
        self.rep_sub_cb.clear()
        subs = self.db.query(db_mod.Subscriber).all()
        for s in subs: self.rep_sub_cb.addItem(f"{s.name} ({s.phone})", s.id)
        
        self.rep_cat_filter.clear()
        self.rep_cat_filter.addItem("الكل", None)
        for c in self.db.query(db_mod.Category).all(): self.rep_cat_filter.addItem(c.name, c.name)

    def generate_subscriber_report(self, fmt):
        sid = self.rep_sub_cb.currentData()
        if not sid: return
        
        try:
            sub = self.db.get(db_mod.Subscriber, sid)
            payments = self.db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sid).order_by(db_mod.Payment.due_date.asc()).all()
            
            total_paid = sum(p.amount for p in payments if p.is_paid)
            total_due = sum(p.amount for p in payments if not p.is_paid)
            
            if fmt == "excel":
                default_name = f"statement_{sub.phone}.xlsx"
                file_path, _ = QFileDialog.getSaveFileName(self, "حفظ كشف الحساب (Excel)", default_name, "Excel Files (*.xlsx)")
                if not file_path: return

                data = []
                for p in payments:
                    data.append({
                        "التاريخ": p.due_date.strftime("%Y-%m-%d"),
                        "المبلغ": p.amount,
                        "القسط": p.installment_number,
                        "الدورة": p.cycle_number,
                        "الحالة": "مدفوع" if p.is_paid else "غير مدفوع",
                        "الملاحظة": p.note or "-"
                    })
                
                df = pd.DataFrame(data)
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Statement', index=False, startrow=5)
                    workbook = writer.book
                    worksheet = writer.sheets['Statement']

                    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#2e7d32', 'color': 'white', 'border': 1, 'align': 'center'})
                    title_fmt = workbook.add_format({'bold': True, 'font_size': 18, 'color': '#2e7d32'})
                    stat_fmt = workbook.add_format({'bold': True})

                    worksheet.write(0, 0, f"كشف حساب تفصيلي: {sub.name}", title_fmt)
                    worksheet.write(2, 0, f"الهاتف: {sub.phone}", stat_fmt)
                    worksheet.write(2, 2, f"الفئة: {sub.category}", stat_fmt)
                    worksheet.write(3, 0, f"المبلغ المسدد: {total_paid:,.2f} ر.ي", stat_fmt)
                    worksheet.write(3, 2, f"المبلغ المتبقي: {total_due:,.2f} ر.ي", stat_fmt)

                    for col_num, value in enumerate(df.columns.values):
                        worksheet.write(5, col_num, value, header_fmt)
                        column_len = max(df[value].astype(str).str.len().max(), len(value) + 2)
                        worksheet.set_column(col_num, col_num, column_len)

                ModernDialog(self, "نجاح", f"تم حفظ التقرير بنجاح في:\n{file_path}").exec()
            else:
                default_name = f"statement_{sub.phone}.pdf"
                file_path, _ = QFileDialog.getSaveFileName(self, "حفظ كشف الحساب (PDF)", default_name, "PDF Files (*.pdf)")
                if not file_path: return

                c = canvas.Canvas(file_path, pagesize=A4); width, height = A4
                try: pdfmetrics.registerFont(TTFont('ArabicFont', "C:/Windows/Fonts/arial.ttf")); c.setFont('ArabicFont', 10)
                except: c.setFont('Helvetica', 10)

                # Header Banner
                c.setFillColor(colors.HexColor("#0a3d0e"))
                c.rect(0, height - 70, width, 70, fill=1)
                c.setFillColor(colors.white)
                c.setFont('ArabicFont', 18)
                c.drawCentredString(width/2, height - 40, reshape_text(f"كشف حساب المشترك: {sub.name}"))
                
                c.setFillColor(colors.black)
                c.setFont('ArabicFont', 10)
                c.drawString(50, height - 90, reshape_text(f"الهاتف: {sub.phone} | الفئة: {sub.category} | رقم العضوية: {sub.subscriber_number}"))
                c.drawString(50, height - 105, reshape_text(f"إجمالي المدفوع: {total_paid:,.2f} ر.ي | إجمالي المتبقي: {total_due:,.2f} ر.ي"))
                c.line(50, height - 110, width - 50, height - 110)

                y = height - 140
                headers = ["التاريخ", "المبلغ", "قسط", "دورة", "الحالة", "الملاحظة"]
                col_x = [50, 130, 200, 240, 290, 380]
                c.setFillColor(colors.HexColor("#f1f5f9"))
                c.rect(45, y - 5, width - 90, 18, fill=1)
                c.setFillColor(colors.black)
                for i, h in enumerate(headers): c.drawString(col_x[i], y, reshape_text(h))
                y -= 25
                for idx, p in enumerate(payments):
                    if y < 50:
                        c.showPage()
                        y = height - 50
                        try:
                            c.setFont('ArabicFont', 10)
                        except:
                            pass
                    if idx % 2 == 1:
                        c.setFillColor(colors.HexColor("#f8fafc"))
                        c.rect(45, y - 5, width - 90, 18, fill=1)
                    c.setFillColor(colors.black)
                    c.drawString(col_x[0], y, p.due_date.strftime("%Y-%m-%d"))
                    c.drawString(col_x[1], y, f"{p.amount:,.2f}")
                    c.drawString(col_x[2], y, str(p.installment_number))
                    c.drawString(col_x[3], y, str(p.cycle_number))
                    c.drawString(col_x[4], y, reshape_text("مدفوع" if p.is_paid else "غير مدفوع"))
                    nt = p.note or "-"
                    if len(nt) > 35: nt = nt[:32] + "..."
                    c.drawString(col_x[5], y, reshape_text(nt))
                    y -= 20
                c.save()
                ModernDialog(self, "نجاح", f"تم حفظ التقرير بنجاح في:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", str(e)).exec()

    def generate_winners_report(self):
        """Generates an Excel report of all winners."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, reshape_text("حفظ تقرير الفائزين"), "winners_report.xlsx", reshape_text("Excel Files (*.xlsx)"))
            if not file_path: return
            
            winners = self.db.query(db_mod.Winner).order_by(db_mod.Winner.draw_date.desc()).all()
            data = [{
                reshape_text("رقم المشترك الفائز"): w.subscriber_number,
                reshape_text("تاريخ السحب"): w.draw_date.strftime("%Y-%m-%d %H:%M"),
                reshape_text("نوع الجائزة"): w.draw_type or reshape_text("سحب عام")
            } for w in winners]
            df = pd.DataFrame(data)
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name=reshape_text('الفائزون'), index=False)
                workbook = writer.book
                worksheet = writer.sheets[reshape_text('الفائزون')]
                
                # Adjust column widths
                for i, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(i, i, max_len)

            ModernDialog(self, reshape_text("نجاح"), reshape_text(f"تم تصدير التقرير بنجاح إلى:\n{file_path}")).exec()
        except Exception as e: ModernDialog(self, reshape_text("خطأ"), str(e)).exec()

    def generate_categories_report(self):
        """Generates a PDF summary report of categories."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, reshape_text("حفظ ملخص الفئات"), "categories_summary.pdf", reshape_text("PDF Files (*.pdf)"))
            if not file_path: return

            c = canvas.Canvas(file_path, pagesize=A4); width, height = A4
            try: pdfmetrics.registerFont(TTFont('ArabicFont', "C:/Windows/Fonts/arial.ttf")); c.setFont('ArabicFont', 12)
            except: c.setFont('Helvetica', 12)
            
            c.drawString(width/2 - 50, height - 50, reshape_text("ملخص الفئات والمبالغ"))
            y = height - 100
            
            cats = self.db.query(db_mod.Category).all()
            headers = [reshape_text("اسم الفئة"), reshape_text("المبلغ الشهري"), reshape_text("عدد المشتركين"), reshape_text("إجمالي المبالغ")]
            col_x = [50, 180, 310, 440]
            for i, h in enumerate(headers): c.drawString(col_x[i], y, h)
            y -= 30
            
            for cat in cats:
                count = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == cat.name).count()
                total = count * cat.amount
                c.drawString(col_x[0], y, reshape_text(cat.name))
                c.drawString(col_x[1], y, f"{cat.amount:,.2f}")
                c.drawString(col_x[2], y, str(count))
                c.drawString(col_x[3], y, f"{total:,.2f}")
                y -= 25
            c.save()
            ModernDialog(self, reshape_text("نجاح"), reshape_text(f"تم تصدير التقرير بنجاح إلى:\n{file_path}")).exec()
        except Exception as e: ModernDialog(self, reshape_text("خطأ"), str(e)).exec()

    def generate_custom_report(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير الفائزين", "winners_report.xlsx", "Excel Files (*.xlsx)")
            if not file_path: return
            
            winners = self.db.query(db_mod.Winner).all()
            data = [{"رقم المشترك الفائز": w.subscriber_number, "تاريخ السحب": w.draw_date.strftime("%Y-%m-%d %H:%M")} for w in winners]
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
            start_date = datetime.datetime.combine(self.rep_date_start.date().toPyDate(), datetime.time.min)
            end_date = datetime.datetime.combine(self.rep_date_end.date().toPyDate(), datetime.time.max)
            status = self.rep_status.currentText()
            cat_name = self.rep_cat_filter.currentData()
            
            query = self.db.query(db_mod.Payment).filter(db_mod.Payment.due_date.between(start_date, end_date))
            
            if status == "مدفوع": query = query.filter(db_mod.Payment.is_paid == True)
            elif status == "غير مدفوع": query = query.filter(db_mod.Payment.is_paid == False)
            
            if cat_name:
                query = query.join(db_mod.Subscriber).filter(db_mod.Subscriber.category == cat_name)
                
            payments = query.all()
            data = []
            for p in payments:
                sub = self.db.get(db_mod.Subscriber, p.subscriber_id)
                data.append({
                    "المشترك": sub.name if sub else "غير معروف",
                    "الفئة": sub.category if sub else "-",
                    "التاريخ": p.due_date.strftime("%Y-%m-%d"),
                    "المبلغ": p.amount,
                    "القسط": p.installment_number,
                    "الحالة": "مدفوع" if p.is_paid else "غير مدفوع",
                    "الملاحظة": p.note
                })
            
            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, reshape_text("حفظ التقرير المخصص"), "custom_payments_report.xlsx", reshape_text("Excel Files (*.xlsx)"))
            if not file_path: return
            
            df.to_excel(file_path, index=False)
            ModernDialog(self, reshape_text("نجاح"), reshape_text(f"تم تصدير التقرير بنجاح إلى:\n{file_path}")).exec()
        except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()

    def show_draw_management(self): 
        self.content_stack.setCurrentWidget(self.page_draw)
        self._update_nav_style("إدارة القرعة")
        self.load_recent_winners()
        self.refresh_draw_stats()

    def init_draw_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        title = QLabel("إدارة القرعة والجوائز")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        
        self.draw_tabs = QTabWidget()
        
        # --- TAB 1: Perform Draw ---
        tab1 = QScrollArea(); tab1.setWidgetResizable(True)
        con1 = QWidget(); lay1 = QVBoxLayout(con1); lay1.setContentsMargins(20, 20, 20, 20); lay1.setSpacing(25)
        
        # Statistics Section
        stats_frame = QFrame(); stats_frame.setObjectName("StatCard")
        self.draw_stats_layout = QVBoxLayout(stats_frame); self.draw_stats_layout.setSpacing(10)
        stats_title = QLabel("إحصائيات التأهل للسحب"); stats_title.setObjectName("SectionTitle"); stats_title.setStyleSheet("font-size: 16px; color: #4ade80;")
        self.draw_stats_layout.addWidget(stats_title)
        lay1.addWidget(stats_frame)

        draw_grid = QHBoxLayout(); draw_grid.setSpacing(20)
        draws = [
            ("القرعة الاسبوعية", "سحب عشوائي من المشتركين الذين أتموا سداد جميع أقساط الدورة الحالية.", "#2e7d32"),
            ("الجائزة التحفيزية", "سحب لتشجيع المشتركين الملتزمين بالسداد.", "#3b82f6"),
            ("الجائزة الكبرى", "سحب الجائزة الكبرى في نهاية الدورة.", "#ef4444")
        ]
        
        for name, desc, color in draws:
            card = QFrame(); card.setObjectName("StatCard"); card.setMinimumHeight(220)
            v_lay = QVBoxLayout(card); v_lay.setContentsMargins(20, 20, 20, 20); v_lay.setSpacing(15)
            
            t_lbl = QLabel(name); t_lbl.setObjectName("SectionTitle"); t_lbl.setStyleSheet(f"color: {color};"); t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d_lbl = QLabel(desc); d_lbl.setWordWrap(True); d_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); d_lbl.setStyleSheet("color: #94a3b8; font-size: 13px;")
            
            btn = QPushButton("بدء السحب الآن")
            btn.setObjectName("PrimaryBtn"); btn.setFixedHeight(45)
            btn.clicked.connect(lambda checked, n=name: self.perform_draw(n))
            
            v_lay.addWidget(t_lbl); v_lay.addWidget(d_lbl); v_lay.addStretch(); v_lay.addWidget(btn)
            draw_grid.addWidget(card)
        
        lay1.addLayout(draw_grid); lay1.addStretch()
        tab1.setWidget(con1)
        self.draw_tabs.addTab(tab1, "إجراء السحب")
        
        # --- TAB 2: Winners Log ---
        tab2 = QWidget(); lay2 = QVBoxLayout(tab2); lay2.setContentsMargins(20, 20, 20, 20)
        
        winners_card = QFrame(); winners_card.setObjectName("StatCard"); win_layout = QVBoxLayout(winners_card); win_layout.setContentsMargins(10, 10, 10, 10)
        
        self.table_recent_winners = QTableWidget()
        self.table_recent_winners.setColumnCount(3)
        self.table_recent_winners.setHorizontalHeaderLabels(["رقم المشترك", "تاريخ السحب", "نوع الجائزة"])
        self.table_recent_winners.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_recent_winners.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_recent_winners.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_recent_winners.customContextMenuRequested.connect(self.show_winner_context_menu)
        win_layout.addWidget(self.table_recent_winners)
        
        lay2.addWidget(winners_card)
        self.draw_tabs.addTab(tab2, "سجل الفائزين")
        
        layout.addWidget(self.draw_tabs)
        return page

    def refresh_draw_stats(self):
        # Clear previous stats
        for i in reversed(range(self.draw_stats_layout.count())): 
            item = self.draw_stats_layout.itemAt(i)
            if item.widget(): item.widget().setParent(None)
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget(): child.widget().setParent(None)
        
        # Grid layout for better responsiveness
        grid = QGridLayout(); grid.setSpacing(15)
        self.draw_stats_layout.addLayout(grid)
        
        categories = self.db.query(db_mod.Category).all()
        cols = 2 # Show 2 cards per row
        today = datetime.datetime.now()

        for idx, cat in enumerate(categories):
            # Find the active cycle based on today's date
            active_p = self.db.query(db_mod.Payment).join(db_mod.Subscriber).filter(
                db_mod.Subscriber.category == cat.name,
                db_mod.Payment.due_date <= today
            ).order_by(db_mod.Payment.due_date.desc()).first()
            current_cycle = active_p.cycle_number if active_p else 1
            
            subs_in_cat = self.db.query(db_mod.Subscriber).filter(
                db_mod.Subscriber.category == cat.name,
                db_mod.Subscriber.status == "accepted"
            ).all()
            
            completed_cycle_count = 0
            incentive_count = 0
            
            for sub in subs_in_cat:
                payments = self.db.query(db_mod.Payment).filter(
                    db_mod.Payment.subscriber_id == sub.id, 
                    db_mod.Payment.cycle_number == current_cycle
                ).all()
                if not payments: continue
                
                # فحص اكتمال الدورة بناءً على إجمالي المبالغ (يدعم نظام تقسيم الأقساط)
                total_expected_for_cycle = cat.amount * cat.max_installments
                total_paid_in_cycle = sum(p.amount for p in payments if p.is_paid)
                
                # يعتبر المشترك أتم الدورة إذا سدد كامل المبلغ المطلوب ولم يتبقَ أي جزء (سجل) غير مدفوع
                # نستخدم هامش خطأ بسيط 0.01 للتعامل مع العملات العشرية
                is_cycle_finished = (total_paid_in_cycle >= total_expected_for_cycle - 0.01) and all(p.is_paid for p in payments)

                is_incentive = True
                has_paid_something = False
                
                for p in payments:
                    # Incentive Logic: 
                    # 1. If an installment is due today or in the past, it MUST be paid.
                    # 2. It must be paid ON TIME (date comparison).
                    # 3. If any installment (even future ones) is marked as paid late, incentive is lost.
                    
                    if p.due_date.date() <= today.date():
                        if not p.is_paid:
                            is_incentive = False
                        else:
                            has_paid_something = True
                            if p.paid_date and p.paid_date.date() > p.due_date.date():
                                is_incentive = False
                    else:
                        # Future installments
                        if p.is_paid:
                            has_paid_something = True
                            if p.paid_date and p.paid_date.date() > p.due_date.date():
                                is_incentive = False
                
                if is_cycle_finished:
                    completed_cycle_count += 1
                if is_incentive and has_paid_something:
                    incentive_count += 1
            
            # Create a Premium Category Card
            cat_card = QFrame(); cat_card.setObjectName("StatCard")
            v_lay = QVBoxLayout(cat_card); v_lay.setSpacing(15)
            
            header = QLabel(f"📊 {cat.name}"); header.setObjectName("SectionTitle"); header.setStyleSheet("font-size: 16px;")
            cycle_info = QLabel(f"الدورة الحالية: {current_cycle}"); cycle_info.setStyleSheet("color: #64748b; font-size: 11px;")
            v_lay.addWidget(header); v_lay.addWidget(cycle_info)
            
            stats_row = QHBoxLayout()
            
            # Weekly Stat
            w_vbox = QVBoxLayout()
            w_val = QLabel(str(completed_cycle_count)); w_val.setStyleSheet("font-size: 24px; font-weight: 800; color: #2e7d32;")
            w_lbl = QLabel("أتموا الدورة"); w_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
            w_vbox.addWidget(w_val); w_vbox.addWidget(w_lbl)
            
            # Incentive Stat
            i_vbox = QVBoxLayout()
            i_val = QLabel(str(incentive_count)); i_val.setStyleSheet("font-size: 24px; font-weight: 800; color: #1b5e20;")
            i_lbl = QLabel("مؤهلين التحفيزية"); i_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
            i_vbox.addWidget(i_val); i_vbox.addWidget(i_lbl)
            
            stats_row.addLayout(w_vbox); stats_row.addStretch(); stats_row.addLayout(i_vbox)
            v_lay.addLayout(stats_row)
            
            cat_card.setMinimumWidth(300)
            grid.addWidget(cat_card, idx // cols, idx % cols)
        
        if not categories:
            self.draw_stats_layout.addWidget(QLabel("لا توجد فئات مسجلة حالياً."))

    def load_recent_winners(self):
        winners = self.db.query(db_mod.Winner).order_by(db_mod.Winner.draw_date.desc()).all()
        self.table_recent_winners.setRowCount(len(winners))
        for i, w in enumerate(winners):
            item = QTableWidgetItem(w.subscriber_number)
            item.setData(Qt.ItemDataRole.UserRole, w.id)
            self.table_recent_winners.setItem(i, 0, item)
            self.table_recent_winners.setItem(i, 1, QTableWidgetItem(w.draw_date.strftime("%Y-%m-%d %H:%M")))
            self.table_recent_winners.setItem(i, 2, QTableWidgetItem(w.draw_type or "سحب عام"))

    def show_winner_context_menu(self, pos):
        row = self.table_recent_winners.rowAt(pos.y())
        if row < 0: return
        
        wid = self.table_recent_winners.item(row, 0).data(Qt.ItemDataRole.UserRole)
        num = self.table_recent_winners.item(row, 0).text()
        
        menu = QMenu(self)
        act_del = QAction(f"حذف الفائز ({num})", self)
        act_del.triggered.connect(lambda: self.delete_winner(wid))
        menu.addAction(act_del)
        menu.exec(QCursor.pos())

    def delete_winner(self, wid):
        if ModernDialog(self, "تأكيد الحذف", "هل أنت متأكد من حذف هذا السجل من قائمة الفائزين؟", is_confirm=True).exec():
            try:
                winner = self.db.get(db_mod.Winner, wid)
                if winner:
                    self.db.delete(winner)
                    self.db.commit()
                    self.load_recent_winners()
                    ModernDialog(self, "نجاح", "تم حذف السجل بنجاح").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"فشل الحذف: {e}").exec()

    def generate_overall_financial_summary_report(self):
        """Generates an Excel report summarizing overall financial stats."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, reshape_text("حفظ ملخص مالي عام"), "overall_financial_summary.xlsx", reshape_text("Excel Files (*.xlsx)"))
            if not file_path: return

            total_expected = self.db.query(func.sum(db_mod.Payment.amount)).scalar() or 0
            total_collected = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.is_paid == True).scalar() or 0
            total_remaining = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.is_paid == False).scalar() or 0
            total_expenses = self.db.query(func.sum(db_mod.Expense.amount)).scalar() or 0
            net_cash = total_collected - total_expenses

            data = {
                reshape_text("البيان"): [
                    reshape_text("إجمالي رأس المال المتوقع"),
                    reshape_text("المبالغ المحصلة (الإيرادات)"),
                    reshape_text("النفقات التشغيلية (المصاريف)"),
                    reshape_text("صافي السيولة النقدية"),
                    reshape_text("الأقساط غير المسددة (المتأخرات)")
                ],
                reshape_text("المبلغ (ر.ي)"): [
                    total_expected,
                    total_collected,
                    total_expenses,
                    net_cash,
                    total_remaining
                ]
            }
            df = pd.DataFrame(data)

            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name=reshape_text('ملخص مالي'), index=False)
                workbook = writer.book
                worksheet = writer.sheets[reshape_text('ملخص مالي')]
                
                # Adjust column widths
                for i, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(i, i, max_len)

            ModernDialog(self, reshape_text("نجاح"), reshape_text(f"تم تصدير التقرير بنجاح إلى:\n{file_path}")).exec()
        except Exception as e:
            ModernDialog(self, reshape_text("خطأ"), str(e)).exec()

    def generate_subscriber_contact_list_report(self, fmt):
        """Generates a list of subscribers with contact info in Excel or PDF."""
        try:
            subs = self.db.query(db_mod.Subscriber).all()
            data = [{
                reshape_text("الاسم"): s.name,
                reshape_text("الهاتف"): s.phone,
                reshape_text("رقم الحساب"): s.subscriber_number,
                reshape_text("الفئة"): s.category
            } for s in subs]
            df = pd.DataFrame(data)

            if fmt == "excel":
                file_path, _ = QFileDialog.getSaveFileName(self, reshape_text("حفظ قائمة المشتركين (Excel)"), "subscriber_contact_list.xlsx", reshape_text("Excel Files (*.xlsx)"))
                if not file_path: return
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name=reshape_text('المشتركون'), index=False)
                    workbook = writer.book
                    worksheet = writer.sheets[reshape_text('المشتركون')]
                    for i, col in enumerate(df.columns):
                        max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                        worksheet.set_column(i, i, max_len)
            else: # PDF
                file_path, _ = QFileDialog.getSaveFileName(self, reshape_text("حفظ قائمة المشتركين (PDF)"), "subscriber_contact_list.pdf", reshape_text("PDF Files (*.pdf)"))
                if not file_path: return
                c = canvas.Canvas(file_path, pagesize=A4); width, height = A4
                try: pdfmetrics.registerFont(TTFont('ArabicFont', "C:/Windows/Fonts/arial.ttf")); c.setFont('ArabicFont', 10)
                except: c.setFont('Helvetica', 10)
                
                c.drawString(width/2 - 50, height - 50, reshape_text("قائمة المشتركين"))
                y = height - 100
                headers = [reshape_text("الاسم"), reshape_text("الهاتف"), reshape_text("رقم الحساب"), reshape_text("الفئة")]
                col_x = [50, 180, 310, 440]
                for i, h in enumerate(headers): c.drawString(col_x[i], y, h)
                c.line(50, y-5, width-50, y-5)
                y -= 25
                
                for s in subs:
                    if y < 50: c.showPage(); y = height - 50; c.setFont('ArabicFont', 10)
                    c.drawString(col_x[0], y, reshape_text(s.name or ""))
                    c.drawString(col_x[1], y, reshape_text(s.phone or ""))
                    c.drawString(col_x[2], y, reshape_text(s.subscriber_number or ""))
                    c.drawString(col_x[3], y, reshape_text(s.category or ""))
                    y -= 20
                c.save()

            ModernDialog(self, reshape_text("نجاح"), reshape_text(f"تم تصدير التقرير بنجاح إلى:\n{file_path}")).exec()
        except Exception as e:
            ModernDialog(self, reshape_text("خطأ"), str(e)).exec()

    def generate_expense_summary_report(self):
        """Generates an Excel report of expenses, with date and category filters."""
        try:
            start_date = datetime.datetime.combine(self.exp_rep_date_start.date().toPyDate(), datetime.time.min)
            end_date = datetime.datetime.combine(self.exp_rep_date_end.date().toPyDate(), datetime.time.max)
            expense_category = self.exp_rep_exp_cat_filter.currentText()

            query = self.db.query(db_mod.Expense).filter(db_mod.Expense.date.between(start_date, end_date))

            if expense_category != reshape_text("الكل"):
                query = query.filter(db_mod.Expense.category == expense_category)
            
            expenses = query.order_by(db_mod.Expense.date.desc()).all()
            
            data = []
            for e in expenses:
                data.append({
                    reshape_text("البيان / الوصف"): e.title,
                    reshape_text("المبلغ (ر.ي)"): e.amount,
                    reshape_text("التصنيف"): e.category or "-",
                    reshape_text("التاريخ والوقت"): e.date.strftime("%Y-%m-%d %H:%M"),
                    reshape_text("الملاحظات"): e.note or "-"
                })
            
            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, reshape_text("حفظ تقرير المصاريف"), "detailed_expenses_report.xlsx", reshape_text("Excel Files (*.xlsx)"))
            if not file_path: return
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name=reshape_text('المصاريف'), index=False)
                workbook = writer.book
                worksheet = writer.sheets[reshape_text('المصاريف')]
                
                # Add summary info
                worksheet.write(0, 0, reshape_text(f"تقرير المصاريف من: {start_date.strftime('%Y-%m-%d')} إلى: {end_date.strftime('%Y-%m-%d')}"))
                if expense_category != reshape_text("الكل"):
                    worksheet.write(1, 0, reshape_text(f"التصنيف المختار: {expense_category}"))
                
                total_amount = df[reshape_text("المبلغ (ر.ي)")].sum() if not df.empty else 0
                worksheet.write(len(df) + 3, 0, reshape_text("الإجمالي الكلي:"))
                worksheet.write(len(df) + 3, 1, total_amount)

                # Adjust column widths
                for i, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(i, i, max_len)

            ModernDialog(self, reshape_text("نجاح"), reshape_text(f"تم تصدير التقرير بنجاح إلى:\n{file_path}")).exec()
        except Exception as e:
            ModernDialog(self, reshape_text("خطأ"), str(e)).exec()

    def perform_draw(self, draw_name):
        # 1. Get accepted subscribers
        all_subs = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted").all()
        qualified_subs = []
        qualified_by_category = {}
        
        today = datetime.datetime.now()
        for sub in all_subs:
            # Determine the active cycle for this specific subscriber based on today's date
            active_p = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == sub.id,
                db_mod.Payment.due_date <= today
            ).order_by(db_mod.Payment.due_date.desc()).first()
            sub_current_cycle = active_p.cycle_number if active_p else 1

            payments = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == sub.id,
                db_mod.Payment.cycle_number == sub_current_cycle
            ).order_by(db_mod.Payment.installment_number.asc()).all()
            
            if not payments: continue
            
            cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
            max_inst = cat.max_installments if cat else 0

            # فحص الأهلية المحدث ليتوافق مع سجلات السداد الجزئي
            total_expected_for_cycle = (cat.amount * max_inst) if cat else 0
            total_paid_in_cycle = sum(p.amount for p in payments if p.is_paid)
            
            # الأهلية: سداد كامل المبلغ المطلوب للدورة + خلو السجلات من أي مبالغ غير مدفوعة
            is_cycle_finished = (total_paid_in_cycle >= total_expected_for_cycle - 0.01) and all(p.is_paid for p in payments)
            
            last_payment_date = payments[-1].due_date if payments else today
            is_date_reached = today >= last_payment_date

            is_incentive = True
            has_paid_something = False
            
            for p in payments:
                if p.due_date.date() <= today.date():
                    if not p.is_paid:
                        is_incentive = False
                    else:
                        has_paid_something = True
                        if p.paid_date and p.paid_date.date() > p.due_date.date():
                            is_incentive = False
                else:
                    if p.is_paid:
                        has_paid_something = True
                        if p.paid_date and p.paid_date.date() > p.due_date.date():
                            is_incentive = False
            
            if draw_name == "القرعة الاسبوعية":
                if is_cycle_finished and is_date_reached:
                    qualified_subs.append(sub)
                    if sub.category not in qualified_by_category: qualified_by_category[sub.category] = []
                    qualified_by_category[sub.category].append(sub)
            elif draw_name == "الجائزة التحفيزية":
                if is_incentive and has_paid_something:
                    qualified_subs.append(sub)
            else:
                # Grand Prize: Must have finished the cycle
                if is_cycle_finished and is_date_reached:
                    qualified_subs.append(sub)
        
        if not qualified_subs:
            ModernDialog(self, "تنبيه", f"لا يوجد مشتركون مستوفون لشروط {draw_name} حالياً").exec()
            return
            
        if draw_name == "القرعة الاسبوعية":
            if not ModernDialog(self, "تأكيد", f"هل أنت متأكد من بدء {draw_name}؟ (عدد الفئات المؤهلة: {len(qualified_by_category)})", is_confirm=True).exec():
                return
            
            # Use the new animated multi-category draw
            anim_dlg = DrawAnimationDialog(self, qualified_by_category, draw_name, self.db)
            anim_dlg.exec()
            self.load_recent_winners(); self.refresh_draw_stats()
            return

        if not ModernDialog(self, "تأكيد", f"هل أنت متأكد من بدء {draw_name}؟ (عدد المؤهلين: {len(qualified_subs)})", is_confirm=True).exec():
            return

        # Simple Shuffling Effect Dialog
        wait_dlg = QDialog(self); wait_dlg.setWindowTitle("جاري السحب..."); wait_dlg.setFixedWidth(300)
        v_lay = QVBoxLayout(wait_dlg); v_lay.setContentsMargins(30, 30, 30, 30)
        l_status = QLabel("جاري اختيار الفائز..."); l_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.addWidget(l_status)
        
        winner = random.choice(qualified_subs)
        
        # Save Winner
        new_w = db_mod.Winner(
            subscriber_number=winner.subscriber_number, 
            draw_type=draw_name,
            draw_date=datetime.datetime.now()
        )
        self.db.add(new_w)
        self.db.commit()
        
        # Show Result
        res_msg = f"مبروك للفائز في {draw_name}!\n\nالاسم: {winner.name}\nرقم الحساب: {winner.subscriber_number}\nرقم الهاتف: {winner.phone}"
        ModernDialog(self, "تم السحب بنجاح", res_msg).exec()
        
        self.load_recent_winners()
        self.refresh_draw_stats()

    def init_cycles_page(self):
        page = QScrollArea(); page.setWidgetResizable(True); container = QWidget(); layout = QVBoxLayout(container); layout.setContentsMargins(40, 40, 40, 40); layout.setSpacing(30)
        title = QLabel("إدارة الدورات والأقساط"); title.setObjectName("PageTitle"); layout.addWidget(title)
        
        f1 = QFrame(); f1.setObjectName("StatCard"); form = QFormLayout(f1); form.setSpacing(15)
        
        self.cyc_cat = QComboBox()
        self.cyc_cat.currentIndexChanged.connect(self.load_category_cycle_settings)
        self.cyc_count = QLineEdit(); self.cyc_count.setPlaceholderText("مثال: 2")
        self.cyc_inst_count = QLineEdit(); self.cyc_inst_count.setPlaceholderText("مثال: 12")
        
        self.cyc_start = QDateEdit(); self.cyc_start.setCalendarPopup(True); self.cyc_start.setDate(QDate.currentDate())
        self.cyc_end = QDateEdit(); self.cyc_end.setCalendarPopup(True); self.cyc_end.setDate(QDate.currentDate().addYears(1))
        
        # Auto-calculate end date
        self.cyc_start.dateChanged.connect(self.update_auto_end_date)
        self.cyc_count.textChanged.connect(lambda: self.update_auto_end_date())
        self.cyc_inst_count.textChanged.connect(lambda: self.update_auto_end_date())
        
        form.addRow("اختر الفئة:", self.cyc_cat)
        form.addRow("إجمالي عدد الدورات:", self.cyc_count)
        form.addRow("عدد الأقساط في كل دورة:", self.cyc_inst_count)
        form.addRow("تاريخ بداية أول دورة:", self.cyc_start)
        form.addRow("تاريخ نهاية آخر دورة:", self.cyc_end)
        
        btn_save_settings = QPushButton("حفظ الإعدادات لهذه الفئة فقط")
        btn_save_settings.setObjectName("PrimaryBtn")
        btn_save_settings.setFixedHeight(50)
        btn_save_settings.clicked.connect(self.save_cycle_settings)
        
        btn_gen = QPushButton("توليد جدول الأقساط لجميع المشتركين")
        btn_gen.setObjectName("PrimaryBtn")
        btn_gen.setFixedHeight(50)
        btn_gen.clicked.connect(self.generate_cycle_schedule)
        
        layout.addWidget(f1)
        layout.addWidget(btn_save_settings)
        layout.addWidget(btn_gen)
        
        info = QLabel("تنبيه: هذا الإجراء سيقوم بإنشاء سجلات دفع مستقبلية لجميع المشتركين في الفئة المختارة بناءً على الإعدادات أعلاه.")
        info.setStyleSheet("color: #94a3b8; font-size: 13px;")
        layout.addWidget(info)
        
        layout.addStretch(); page.setWidget(container); return page

    def refresh_cycles_cat_list(self):
        self.cyc_cat.clear()
        for c in self.db.query(db_mod.Category).all(): self.cyc_cat.addItem(c.name, c.id)

    def load_category_cycle_settings(self):
        cat_id = self.cyc_cat.currentData()
        if not cat_id: return
        cat = self.db.get(db_mod.Category, cat_id)
        if cat:
            self.cyc_count.setText(str(cat.max_cycles))
            self.cyc_inst_count.setText(str(cat.max_installments))
            if cat.start_date:
                self.cyc_start.setDate(QDate(cat.start_date.year, cat.start_date.month, cat.start_date.day))
            if cat.end_date:
                self.cyc_end.setDate(QDate(cat.end_date.year, cat.end_date.month, cat.end_date.day))

    def update_auto_end_date(self):
        try:
            c_text = self.cyc_count.text().strip()
            i_text = self.cyc_inst_count.text().strip()
            if not c_text or not i_text: return
            
            cycles = int(c_text)
            inst = int(i_text)
            start = self.cyc_start.date().toPyDate()
            
            total_inst = cycles * inst
            if total_inst > 0:
                # Daily Hakbah logic: 1 day per installment
                days = (total_inst - 1) * 1
                end = start + datetime.timedelta(days=days)
                self.cyc_end.setDate(QDate(end.year, end.month, end.day))
        except:
            pass

    def save_cycle_settings(self):
        cat_id = self.cyc_cat.currentData()
        if not cat_id: return
        
        try:
            cycles = int(self.cyc_count.text().strip())
            inst_per_cycle = int(self.cyc_inst_count.text().strip())
            
            cat = self.db.get(db_mod.Category, cat_id)
            cat.max_cycles = cycles
            cat.max_installments = inst_per_cycle
            cat.start_date = datetime.datetime.combine(self.cyc_start.date().toPyDate(), datetime.time.min)
            cat.end_date = datetime.datetime.combine(self.cyc_end.date().toPyDate(), datetime.time.min)
            self.db.commit()
            
            ModernDialog(self, "نجاح", f"تم حفظ إعدادات الفئة {cat.name} بنجاح").exec()
        except ValueError:
            ModernDialog(self, "خطأ", "يرجى إدخال أرقام صحيحة للدورات والأقساط").exec()

    def generate_cycle_schedule(self):
        cat_id = self.cyc_cat.currentData()
        if not cat_id: return
        
        try:
            cycles = int(self.cyc_count.text().strip())
            inst_per_cycle = int(self.cyc_inst_count.text().strip())
            start_date = self.cyc_start.date().toPyDate()
            
            total_installments = cycles * inst_per_cycle
            if total_installments < 1:
                ModernDialog(self, "خطأ", "يجب أن يكون إجمالي الأقساط قسطاً واحداً على الأقل").exec()
                return
            
            cat = self.db.get(db_mod.Category, cat_id)
            cat.max_cycles = cycles
            cat.max_installments = inst_per_cycle
            self.db.commit()
            
            subs = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == cat.name).all()
            
            if not subs:
                ModernDialog(self, "تنبيه", "لا يوجد مشتركون في هذه الفئة حالياً").exec()
                return
            
            if ModernDialog(self, "تأكيد", f"سيتم إنشاء {total_installments} سجل دفع (بمعدل قسط واحد يومياً) لكل مشترك. هل أنت متأكد؟", is_confirm=True).exec():
                total_created = 0
                for c_idx in range(1, cycles + 1):
                    for i_idx in range(1, inst_per_cycle + 1):
                        # Calculate global installment index
                        global_idx = (c_idx - 1) * inst_per_cycle + (i_idx - 1)
                        days_to_add = global_idx
                        
                        due_date = start_date + datetime.timedelta(days=days_to_add)
                        due_datetime = datetime.datetime.combine(due_date, datetime.time.min)
                        
                        for sub in subs:
                            exists = self.db.query(db_mod.Payment).filter(
                                db_mod.Payment.subscriber_id == sub.id,
                                db_mod.Payment.cycle_number == c_idx,
                                db_mod.Payment.installment_number == i_idx
                            ).first()
                            
                            if not exists:
                                new_p = db_mod.Payment(
                                    subscriber_id=sub.id,
                                    amount=cat.amount,
                                    due_date=due_datetime,
                                    is_paid=False,
                                    cycle_number=c_idx,
                                    installment_number=i_idx,
                                    note=f"دورة {c_idx} - قسط {i_idx}"
                                )
                                self.db.add(new_p)
                                total_created += 1
                
                self.db.commit()
                ModernDialog(self, "نجاح", f"تم توليد {total_created} سجل دفع بنجاح لـ {len(subs)} مشترك").exec()
        except ValueError:
            ModernDialog(self, "خطأ", "يرجى إدخال أرقام صحيحة للدورات والأقساط").exec()
        except Exception as e:
            self.db.rollback()
            ModernDialog(self, "خطأ", str(e)).exec()

    def init_messaging_page(self):
        page = QScrollArea(); page.setWidgetResizable(True); container = QWidget(); layout = QVBoxLayout(container); layout.setContentsMargins(40, 40, 40, 40); layout.setSpacing(30)
        title = QLabel("إعدادات نظام الرسائل والاشعارات"); title.setObjectName("PageTitle"); layout.addWidget(title)

        # Section 1: Gateway Settings
        gateway_card = QFrame(); gateway_card.setObjectName("StatCard"); g_layout = QVBoxLayout(gateway_card); g_layout.setSpacing(15)
        g_title = QLabel("إعدادات بوابة الإرسال (SMS Gateway)"); g_title.setObjectName("SectionTitle"); g_layout.addWidget(g_title)
        
        form = QFormLayout()
        self.msg_api_key = QLineEdit(); self.msg_gateway_url = QLineEdit(); self.msg_sender_id = QLineEdit()
        form.addRow("API Key:", self.msg_api_key); form.addRow("Gateway URL:", self.msg_gateway_url); form.addRow("Sender ID:", self.msg_sender_id)
        g_layout.addLayout(form)
        layout.addWidget(gateway_card)

        # Section 2: Templates
        temp_card = QFrame(); temp_card.setObjectName("StatCard"); t_layout = QVBoxLayout(temp_card); t_layout.setSpacing(15)
        t_title = QLabel("نماذج الرسائل التلقائية"); t_title.setObjectName("SectionTitle"); t_layout.addWidget(t_title)
        
        self.temp_welcome = QTextEdit(); self.temp_welcome.setMaximumHeight(80); self.temp_welcome.setPlaceholderText("رسالة الترحيب عند التسجيل...")
        self.temp_payment = QTextEdit(); self.temp_payment.setMaximumHeight(80); self.temp_payment.setPlaceholderText("تذكير موعد السداد...")
        self.temp_delivery = QTextEdit(); self.temp_delivery.setMaximumHeight(80); self.temp_delivery.setPlaceholderText("إشعار استلام القسط/التسليم...")
        self.temp_winner = QTextEdit(); self.temp_winner.setMaximumHeight(80); self.temp_winner.setPlaceholderText("إشعار الفوز في القرعة...")
        
        t_layout.addWidget(QLabel("رسالة الترحيب:")); t_layout.addWidget(self.temp_welcome)
        t_layout.addWidget(QLabel("تذكير السداد:")); t_layout.addWidget(self.temp_payment)
        t_layout.addWidget(QLabel("إشعار تسديد القسط:")); t_layout.addWidget(self.temp_delivery)
        t_layout.addWidget(QLabel("إشعار الفوز:")); t_layout.addWidget(self.temp_winner)
        layout.addWidget(temp_card)

        # Save Button
        btn_save = QPushButton("حفظ كافة إعدادات الرسائل"); btn_save.setObjectName("PrimaryBtn"); btn_save.setFixedHeight(50)
        btn_save.clicked.connect(self.save_messaging_settings)
        layout.addWidget(btn_save)

        # Section 3: Broadcast
        broad_card = QFrame(); broad_card.setObjectName("StatCard"); b_layout = QVBoxLayout(broad_card); b_layout.setSpacing(15)
        b_title = QLabel("إرسال رسالة جماعية (Broadcast)"); b_title.setObjectName("SectionTitle"); b_layout.addWidget(b_title)
        
        self.broad_text = QTextEdit(); self.broad_text.setPlaceholderText("اكتب نص الرسالة هنا لإرسالها لجميع المشتركين..."); self.broad_text.setMinimumHeight(120)
        b_layout.addWidget(self.broad_text)
        
        btn_broad = QPushButton("إرسال للجميع الآن"); btn_broad.setObjectName("PrimaryBtn"); btn_broad.setFixedHeight(50)
        btn_broad.clicked.connect(self.send_broadcast)
        b_layout.addWidget(btn_broad)
        layout.addWidget(broad_card)

        layout.addStretch(); page.setWidget(container); return page

    def load_messaging_settings(self):
        keys = ["msg_api_key", "msg_gateway_url", "msg_sender_id", "temp_welcome", "temp_payment", "temp_delivery", "temp_winner"]
        settings = {s.key: s.value for s in self.db.query(db_mod.Setting).filter(db_mod.Setting.key.in_(keys)).all()}
        
        self.msg_api_key.setText(settings.get("msg_api_key", ""))
        self.msg_gateway_url.setText(settings.get("msg_gateway_url", ""))
        self.msg_sender_id.setText(settings.get("msg_sender_id", ""))
        self.temp_welcome.setPlainText(settings.get("temp_welcome", "أهلاً بك في هكبة المليون، تم تسجيلك بنجاح."))
        self.temp_payment.setPlainText(settings.get("temp_payment", "عزيزي المشترك، نود تذكيرك بموعد قسط الهكبة."))
        self.temp_delivery.setPlainText(settings.get("temp_delivery", "شكراً لك، تم استلام مبلغ القسط الخاص بك بنجاح."))
        self.temp_winner.setPlainText(settings.get("temp_winner", "نبارك لك الفوز في قرعة هكبة المليون لهذا الشهر!"))

    def save_messaging_settings(self):
        data = {
            "msg_api_key": self.msg_api_key.text(),
            "msg_gateway_url": self.msg_gateway_url.text(),
            "msg_sender_id": self.msg_sender_id.text(),
            "temp_welcome": self.temp_welcome.toPlainText(),
            "temp_payment": self.temp_payment.toPlainText(),
            "temp_delivery": self.temp_delivery.toPlainText(),
            "temp_winner": self.temp_winner.toPlainText()
        }
        for k, v in data.items():
            s = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == k).first()
            if s: s.value = v
            else: self.db.add(db_mod.Setting(key=k, value=v))
        self.db.commit()
        ModernDialog(self, "نجاح", "تم حفظ إعدادات الرسائل بنجاح").exec()

    def send_broadcast(self):
        msg = self.broad_text.toPlainText().strip()
        if not msg:
            ModernDialog(self, "تنبيه", "يرجى كتابة نص الرسالة أولاً").exec()
            return
        
        count = self.db.query(db_mod.Subscriber).count()
        if ModernDialog(self, "تأكيد", f"هل أنت متأكد من إرسال هذه الرسالة إلى {count} مشترك؟", is_confirm=True).exec():
            # In a real app, you would loop and call an SMS API here
            ModernDialog(self, "نجاح", f"تم وضع {count} رسالة في قائمة الإرسال").exec()
            self.broad_text.clear()

    def export_subscribers_excel(self):
        try:
            subs = self.db.query(db_mod.Subscriber).all()
            data = [{"الاسم": s.name, "الهاتف": s.phone, "رقم الحساب": s.subscriber_number, "الفئة": s.category} for s in subs]
            df = pd.DataFrame(data)
            df.to_excel("subscribers_report.xlsx", index=False)
            ModernDialog(self, "نجاح", "تم تصدير ملف subscribers_report.xlsx بنجاح").exec()
        except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()

    def export_subscribers_pdf(self):
        try:
            subs = self.db.query(db_mod.Subscriber).all()
            filename = "subscribers_report.pdf"
            c = canvas.Canvas(filename, pagesize=A4)
            width, height = A4
            
            # Register Arabic Font (Try common Windows path)
            font_path = "C:/Windows/Fonts/arial.ttf"
            try:
                pdfmetrics.registerFont(TTFont('ArabicFont', font_path))
                c.setFont('ArabicFont', 12)
            except:
                c.setFont('Helvetica', 12)

            y = height - 50
            c.drawString(width/2 - 50, y, reshape_text("تقرير المشتركين"))
            y -= 30
            
            headers = ["الاسم", "الهاتف", "رقم الحساب", "الفئة"]
            for i, h in enumerate(headers):
                c.drawString(50 + i*130, y, reshape_text(h))
            y -= 20
            
            for s in subs:
                if y < 50:
                    c.showPage()
                    y = height - 50
                c.drawString(50, y, reshape_text(s.name or ""))
                c.drawString(180, y, reshape_text(s.phone or ""))
                c.drawString(310, y, reshape_text(s.subscriber_number or ""))
                c.drawString(440, y, reshape_text(s.category or ""))
                y -= 20
                
            c.save()
            ModernDialog(self, "نجاح", f"تم تصدير ملف {filename} بنجاح").exec()
        except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Tajawal", 10))
    window = AdminApp()
    window.show()
    sys.exit(app.exec())
