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
        if hasattr(self, 'api_client') and self.api_client:
            if hasattr(self, '_dash_stats_worker') and self._dash_stats_worker.isRunning():
                self._dash_stats_worker.quit()
            from api_client import APIWorker
            self._dash_stats_worker = APIWorker(self.api_client.get_dashboard_stats)
            self._dash_stats_worker.finished.connect(self._render_dashboard_stats_api)
            self._dash_stats_worker.error.connect(lambda err: self._render_dashboard_stats_db())
            self._dash_stats_worker.start()
        else:
            self._render_dashboard_stats_db()

    def _render_dashboard_stats_api(self, data):
        for i in reversed(range(self.stats_grid.count())):
            w = self.stats_grid.itemAt(i).widget()
            if w:
                w.setParent(None)

        total_subscribers = data.get("total_subscribers", 0)
        online_count = data.get("online_count", 0)
        total_visits = data.get("total_visits", 0)
        visiting_subs = data.get("visiting_subscribers_count", 0)
        cat_counts = data.get("category_counts", {})
        
        items = [
            ("إجمالي المشتركين", total_subscribers, "#2e7d32", None),
            ("المتصلون الآن 🟢", online_count, "#10b981", self.show_online_subscribers_dialog),
            ("إجمالي الزيارات 👁️", total_visits, "#0284c7", None),
            ("مشتركون زاروا الموقع 👥", visiting_subs, "#8b5cf6", None)
        ]
        colors = ["#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444"]
        
        cats = [c for c in cat_counts.keys() if c != "غير محدد"]
        if not cats and hasattr(self, 'db'):
            try:
                cats = [c.name for c in self.db.query(db_mod.Category).all()]
            except Exception:
                cats = []

        for i, cat_name in enumerate(cats):
            count = cat_counts.get(cat_name, 0)
            items.append((cat_name, count, colors[i % len(colors)], None))

        for title, value, color, click_callback in items:
            card = QFrame(); card.setObjectName("StatCard"); card.setMinimumHeight(120)
            vbox = QVBoxLayout(card); vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t_lbl = QLabel(title); t_lbl.setObjectName("StatTitle"); t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(t_lbl)
            v_lbl = QLabel(str(value)); v_lbl.setObjectName("StatValue"); v_lbl.setStyleSheet(f"color: {color};"); v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(v_lbl)
            if click_callback:
                card.setCursor(Qt.CursorShape.PointingHandCursor)
                card.mousePressEvent = lambda e, cb=click_callback: cb()
                card.setToolTip("انقر هنا لعرض قائمة المتصلين حالياً")
            self.stats_grid.addWidget(card)

    def _render_dashboard_stats_db(self):
        try:
            self.db.expire_all()
        except Exception:
            pass
        for i in reversed(range(self.stats_grid.count())):
            w = self.stats_grid.itemAt(i).widget()
            if w:
                w.setParent(None)
        
        ten_min_ago = db_mod.get_utc_now() - datetime.timedelta(minutes=10)
        online_count = self.db.query(func.count(db_mod.Subscriber.id)).filter(
            db_mod.Subscriber.last_seen >= ten_min_ago
        ).scalar() or 0

        sub_visits = self.db.query(func.sum(db_mod.Subscriber.visit_count)).scalar() or 0
        site_visits = self.db.query(func.count(db_mod.VisitLog.id)).scalar() or 0
        total_visits = int(sub_visits) + int(site_visits)

        visiting_subs = self.db.query(func.count(db_mod.Subscriber.id)).filter(
            func.coalesce(db_mod.Subscriber.visit_count, 0) > 0
        ).scalar() or 0

        cat_counts = dict(
            self.db.query(db_mod.Subscriber.category, func.count(db_mod.Subscriber.id))
            .group_by(db_mod.Subscriber.category)
            .all()
        )
        total_subscribers = self.db.query(db_mod.Subscriber).count()
        items = [
            ("إجمالي المشتركين", total_subscribers, "#2e7d32", None),
            ("المتصلون الآن 🟢", online_count, "#10b981", self.show_online_subscribers_dialog),
            ("إجمالي الزيارات 👁️", total_visits, "#0284c7", None),
            ("مشتركون زاروا الموقع 👥", visiting_subs, "#8b5cf6", None)
        ]
        colors = ["#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444"]
        for i, cat in enumerate(self.db.query(db_mod.Category).all()):
            count = cat_counts.get(cat.name, 0)
            items.append((cat.name, count, colors[i % len(colors)], None))

        for title, value, color, click_callback in items:
            card = QFrame(); card.setObjectName("StatCard"); card.setMinimumHeight(120)
            vbox = QVBoxLayout(card); vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t_lbl = QLabel(title); t_lbl.setObjectName("StatTitle"); t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(t_lbl)
            v_lbl = QLabel(str(value)); v_lbl.setObjectName("StatValue"); v_lbl.setStyleSheet(f"color: {color};"); v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(v_lbl)
            if click_callback:
                card.setCursor(Qt.CursorShape.PointingHandCursor)
                card.mousePressEvent = lambda e, cb=click_callback: cb()
                card.setToolTip("انقر هنا لعرض قائمة المتصلين حالياً")
            self.stats_grid.addWidget(card)

    def show_online_subscribers_dialog(self):
        """نافذة منبثقة تفاعلية لعرض المشتركين المتصلين بالموقع في هذه اللحظة"""
        try:
            self.db.expire_all()
        except Exception:
            pass

        ten_min_ago = db_mod.get_utc_now() - datetime.timedelta(minutes=10)
        online_subs = self.db.query(db_mod.Subscriber).filter(
            db_mod.Subscriber.last_seen >= ten_min_ago
        ).order_by(db_mod.Subscriber.last_seen.desc()).all()

        dlg = QDialog(self)
        dlg.setWindowTitle("المشتركون المتصلون بالموقع حالياً 🟢")
        dlg.resize(720, 480)
        dlg.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(18)

        title = QLabel(f"المشتركون المتصلون الآن ({len(online_subs)})")
        title.setFont(QFont("Tajawal", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #059669;")
        layout.addWidget(title)

        if not online_subs:
            empty_lbl = QLabel("لا يوجد مشتركون متصلون بالموقع في هذه اللحظة.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #64748b; font-size: 15px; padding: 40px;")
            layout.addWidget(empty_lbl)
        else:
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["الاسم", "رقم الحساب", "رقم الهاتف", "الفئة", "آخر نشاط"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setRowCount(len(online_subs))
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

            now = db_mod.get_utc_now()
            for row, s in enumerate(online_subs):
                diff_sec = max(0, (now - s.last_seen).total_seconds()) if s.last_seen else 0
                mins = int(diff_sec // 60)
                time_str = f"منذ {mins} دقيقة" if mins > 0 else "الآن 🟢"

                name_item = QTableWidgetItem(f"🟢 {s.name}")
                name_item.setFont(QFont("Tajawal", 10, QFont.Weight.Bold))
                num_item = QTableWidgetItem(str(s.subscriber_number or "-"))
                phone_item = QTableWidgetItem(str(s.phone or "-"))
                cat_item = QTableWidgetItem(str(s.category or "-"))
                time_item = QTableWidgetItem(time_str)

                for item in [name_item, num_item, phone_item, cat_item, time_item]:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                table.setItem(row, 0, name_item)
                table.setItem(row, 1, num_item)
                table.setItem(row, 2, phone_item)
                table.setItem(row, 3, cat_item)
                table.setItem(row, 4, time_item)

            layout.addWidget(table)

        btn_close = QPushButton("إغلاق")
        btn_close.setObjectName("PrimaryBtn")
        btn_close.setFixedHeight(40)
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        dlg.exec()
