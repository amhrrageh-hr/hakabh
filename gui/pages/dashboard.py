from sqlalchemy import func
from sqlalchemy.orm import Session
import os
import shutil
import datetime
import random
import time
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import database as db_mod
from gui.utils import reshape_text, ServerWorker
from gui.dialogs import *

class DashboardMixin:
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

        # إضافة حاوية للأزرار لتكون جنباً إلى جنب
        server_btns_layout = QHBoxLayout()
        
        self.btn_start_server = QPushButton("تشغيل الموقع")
        self.btn_start_server.setObjectName("PrimaryBtn")
        self.btn_start_server.setFixedHeight(55)
        self.btn_start_server.clicked.connect(self.start_web_server)
        server_btns_layout.addWidget(self.btn_start_server)

        self.btn_stop_server = QPushButton("إيقاف الموقع")
        self.btn_stop_server.setObjectName("DangerBtn")
        self.btn_stop_server.setFixedHeight(55)
        self.btn_stop_server.setEnabled(False) # معطل حتى يتم التشغيل
        self.btn_stop_server.clicked.connect(self.stop_web_server)
        server_btns_layout.addWidget(self.btn_stop_server)

        server_layout.addLayout(server_btns_layout)

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
        self.btn_stop_server.setEnabled(True)
        self.thread = QThread()
        self.worker = ServerWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.link_found.connect(self._on_server_link_found)
        self.worker.error_occurred.connect(self._on_server_error)
        self.thread.start()

    def stop_web_server(self):
        if hasattr(self, 'worker'):
            self.worker.stop()
        if hasattr(self, 'thread'):
            self.thread.quit()
            self.thread.wait()
        
        self.btn_start_server.setEnabled(True)
        self.btn_stop_server.setEnabled(False)
        self.lbl_public_link.setText("تم إيقاف الموقع وفصل الرابط العام")
        self.btn_copy_link.hide()
        ModernDialog(self, "تنبيه", "تم إيقاف الموقع بنجاح ولن يتمكن المشتركون من الدخول إليه حالياً").exec()

    def _on_server_link_found(self, url):
        self.public_url = url
        self.lbl_public_link.setText(f"الرابط العام: {url}")
        self.btn_copy_link.show()
        ModernDialog(self, "نجاح", "الموقع متاح الآن للمشتركين").exec()

    def _on_server_error(self, err):
        self.btn_start_server.setEnabled(True)
        self.btn_stop_server.setEnabled(False)
        ModernDialog(self, "خطأ", f"حدث خطأ: {err}").exec()

    def copy_link(self):
        QApplication.clipboard().setText(self.public_url)
        ModernDialog(self, "نجاح", "تم نسخ الرابط").exec()
    def toggle_reg(self):
        val = "true" if self.reg_switch.isChecked() else "false"
        self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "registration_open").update({"value": val})
        self.db.commit()
    def refresh_stats(self):
        self.db.expire_all() # تحديث الجلسة لقراءة البيانات الجديدة من الموقع
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
