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
from gui.utils import reshape_text, ServerWorker, fit_dialog_to_screen
from gui.dialogs import *

class DashboardMixin:
    def init_dashboard_page(self):
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        title = QLabel("إحصائيات النظام")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Server Control
        server_card = QFrame(); server_card.setObjectName("StatCard")
        server_layout = QVBoxLayout(server_card); server_layout.setContentsMargins(18, 16, 18, 16); server_layout.setSpacing(10)

        # إضافة حاوية للأزرار لتكون جنباً إلى جنب
        server_btns_layout = QHBoxLayout()
        server_btns_layout.setSpacing(12)
        
        self.btn_start_server = QPushButton("تشغيل الموقع")
        self.btn_start_server.setObjectName("PrimaryBtn")
        self.btn_start_server.setFixedHeight(44)
        self.btn_start_server.clicked.connect(self.start_web_server)
        server_btns_layout.addWidget(self.btn_start_server)

        self.btn_stop_server = QPushButton("إيقاف الموقع")
        self.btn_stop_server.setObjectName("DangerBtn")
        self.btn_stop_server.setFixedHeight(44)
        self.btn_stop_server.setEnabled(False) # معطل حتى يتم التشغيل
        self.btn_stop_server.clicked.connect(self.stop_web_server)
        server_btns_layout.addWidget(self.btn_stop_server)

        server_layout.addLayout(server_btns_layout)

        self.lbl_public_link = QLabel("رابط الموقع: سيظهر هنا بعد التشغيل")
        self.lbl_public_link.setWordWrap(True)
        self.lbl_public_link.setStyleSheet("color: #94a3b8; font-size: 13px; margin-top: 4px;")
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
        reg_layout = QHBoxLayout(reg_card); reg_layout.setContentsMargins(18, 14, 18, 14)
        reg_layout.addWidget(QLabel("حالة التسجيل في الموقع"))
        self.reg_switch = QCheckBox()
        reg_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "registration_open").first()
        self.reg_switch.setChecked(True if reg_setting and reg_setting.value == "true" else False)
        self.reg_switch.stateChanged.connect(self.toggle_reg)
        reg_layout.addStretch(); reg_layout.addWidget(self.reg_switch)
        layout.addWidget(reg_card)

        # Stats (شبكة متجاوبة من 3 أعمدة تتكيف مع الشاشات الصغيرة والكبيرة دون تمرير أفقي)
        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(12)
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

        cols = 3
        for idx_card, (title, value, color, click_callback) in enumerate(items):
            card = QFrame(); card.setObjectName("StatCard"); card.setMinimumHeight(96)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            vbox = QVBoxLayout(card); vbox.setContentsMargins(10, 8, 10, 8); vbox.setSpacing(4); vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t_lbl = QLabel(title); t_lbl.setObjectName("StatTitle"); t_lbl.setWordWrap(True); t_lbl.setStyleSheet("font-size: 13px; font-weight: bold;"); t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(t_lbl)
            v_lbl = QLabel(str(value)); v_lbl.setObjectName("StatValue"); v_lbl.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 800;"); v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(v_lbl)
            if click_callback:
                card.setCursor(Qt.CursorShape.PointingHandCursor)
                card.mousePressEvent = lambda e, cb=click_callback: cb()
                card.setToolTip("انقر هنا لعرض قائمة المتصلين حالياً")
            self.stats_grid.addWidget(card, idx_card // cols, idx_card % cols)
        for c_i in range(cols):
            self.stats_grid.setColumnStretch(c_i, 1)

    def _render_dashboard_stats_db(self):
        try:
            self.db.expire_all()
        except Exception:
            pass
        for i in reversed(range(self.stats_grid.count())):
            w = self.stats_grid.itemAt(i).widget()
            if w:
                w.setParent(None)

        season_id = self.get_active_season_id() if hasattr(self, 'get_active_season_id') else None

        ten_min_ago = db_mod.get_utc_now() - datetime.timedelta(minutes=10)
        q_online = self.db.query(func.count(db_mod.Subscriber.id)).filter(
            db_mod.Subscriber.last_seen >= ten_min_ago
        )
        q_sub_visits = self.db.query(func.sum(db_mod.Subscriber.visit_count))
        q_visiting_subs = self.db.query(func.count(db_mod.Subscriber.id)).filter(
            func.coalesce(db_mod.Subscriber.visit_count, 0) > 0
        )
        q_cat_counts = self.db.query(db_mod.Subscriber.category, func.count(db_mod.Subscriber.id))
        q_total_subs = self.db.query(db_mod.Subscriber)
        q_cats = self.db.query(db_mod.Category)

        if season_id and season_id != -1:
            q_online = q_online.filter(db_mod.Subscriber.season_id == season_id)
            q_sub_visits = q_sub_visits.filter(db_mod.Subscriber.season_id == season_id)
            q_visiting_subs = q_visiting_subs.filter(db_mod.Subscriber.season_id == season_id)
            q_cat_counts = q_cat_counts.filter(db_mod.Subscriber.season_id == season_id)
            q_total_subs = q_total_subs.filter(db_mod.Subscriber.season_id == season_id)
            q_cats = q_cats.filter(db_mod.Category.season_id == season_id)

        online_count = q_online.scalar() or 0
        sub_visits = q_sub_visits.scalar() or 0
        site_visits = self.db.query(func.count(db_mod.VisitLog.id)).scalar() or 0
        total_visits = int(sub_visits) + (int(site_visits) if not season_id else 0)
        visiting_subs = q_visiting_subs.scalar() or 0

        cat_counts = dict(q_cat_counts.group_by(db_mod.Subscriber.category).all())
        total_subscribers = q_total_subs.count()
        items = [
            ("إجمالي المشتركين", total_subscribers, "#2e7d32", None),
            ("المتصلون الآن 🟢", online_count, "#10b981", self.show_online_subscribers_dialog),
            ("إجمالي الزيارات 👁️", total_visits, "#0284c7", None),
            ("مشتركون زاروا الموقع 👥", visiting_subs, "#8b5cf6", None)
        ]
        colors = ["#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444"]
        for i, cat in enumerate(q_cats.all()):
            count = cat_counts.get(cat.name, 0)
            items.append((cat.name, count, colors[i % len(colors)], None))

        cols = 3
        for idx_card, (title, value, color, click_callback) in enumerate(items):
            card = QFrame(); card.setObjectName("StatCard"); card.setMinimumHeight(96)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            vbox = QVBoxLayout(card); vbox.setContentsMargins(10, 8, 10, 8); vbox.setSpacing(4); vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t_lbl = QLabel(title); t_lbl.setObjectName("StatTitle"); t_lbl.setWordWrap(True); t_lbl.setStyleSheet("font-size: 13px; font-weight: bold;"); t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(t_lbl)
            v_lbl = QLabel(str(value)); v_lbl.setObjectName("StatValue"); v_lbl.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 800;"); v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(v_lbl)
            if click_callback:
                card.setCursor(Qt.CursorShape.PointingHandCursor)
                card.mousePressEvent = lambda e, cb=click_callback: cb()
                card.setToolTip("انقر هنا لعرض قائمة المتصلين حالياً")
            self.stats_grid.addWidget(card, idx_card // cols, idx_card % cols)
        for c_i in range(cols):
            self.stats_grid.setColumnStretch(c_i, 1)

    def show_online_subscribers_dialog(self):
        """نافذة منبثقة تفاعلية لعرض المشتركين المتصلين بالموقع في هذه اللحظة"""
        try:
            self.db.expire_all()
        except Exception:
            pass

        season_id = self.get_active_season_id() if hasattr(self, 'get_active_season_id') else None
        ten_min_ago = db_mod.get_utc_now() - datetime.timedelta(minutes=10)
        q_online_subs = self.db.query(db_mod.Subscriber).filter(
            db_mod.Subscriber.last_seen >= ten_min_ago
        )
        if season_id and season_id != -1:
            q_online_subs = q_online_subs.filter(db_mod.Subscriber.season_id == season_id)
        online_subs = q_online_subs.order_by(db_mod.Subscriber.last_seen.desc()).all()

        dlg = QDialog(self)
        dlg.setWindowTitle("المشتركون المتصلون بالموقع حالياً 🟢")
        fit_dialog_to_screen(dlg, 720, 480)
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
