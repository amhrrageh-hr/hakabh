import security
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
from reportlab.lib import colors
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import database as db_mod
from gui.utils import reshape_text, ServerWorker
from gui.dialogs import *

class SubscribersMixin:
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

        btn_new_grp = QPushButton("➕ فتح مجموعة جديدة")
        btn_new_grp.setObjectName("PrimaryBtn")
        btn_new_grp.setStyleSheet("background-color: #059669; color: white; padding: 6px 14px; font-weight: bold;")
        btn_new_grp.setFixedHeight(35)
        btn_new_grp.clicked.connect(self.open_new_group_from_subscribers)
        header.addWidget(btn_new_grp)
        
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
        
        # Advanced Search Field
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("بحث متقدم:"))
        self.sub_search_input = QLineEdit()
        self.sub_search_input.setPlaceholderText("ابحث بالاسم، الهاتف، أو رقم الحساب...")
        self.sub_search_input.textChanged.connect(self.load_subscribers)
        search_layout.addWidget(self.sub_search_input)
        layout.addLayout(search_layout)
        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs)
        return page
    def load_subscribers(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all()
        
        self._current_search_text = self.sub_search_input.text().strip()
        
        # Disconnect signal if connected to prevent triggering while clearing
        try:
            self.sub_tabs.currentChanged.disconnect()
        except TypeError:
            pass
            
        current_idx = self.sub_tabs.currentIndex()
        if current_idx < 0:
            current_idx = 0
            
        self.sub_tabs.clear()
        
        pending_count = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "pending").count()
        pending_label = f"طلبات الانضمام ({pending_count})" if pending_count > 0 else "طلبات الانضمام"
        
        self._categories_cache = ["الكل", pending_label] + [c.name for c in self.db.query(db_mod.Category).all()] + ["قائمة المستبعدين"]
        
        for cat_name in self._categories_cache:
            # Placeholder widget for lazy loading
            dummy = QWidget()
            dummy.setObjectName("DummyTab")
            lay = QVBoxLayout(dummy)
            lbl = QLabel("جاري التحميل...")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl)
            self.sub_tabs.addTab(dummy, cat_name)
            
        self.sub_tabs.currentChanged.connect(self._on_sub_tab_changed)
        
        # Load the appropriate tab
        if current_idx < len(self._categories_cache):
            self.sub_tabs.setCurrentIndex(current_idx)
            self._on_sub_tab_changed(current_idx)
        else:
            self._on_sub_tab_changed(0)

    def _on_sub_tab_changed(self, index):
        if index < 0 or index >= len(self._categories_cache):
            return
            
        cat_name = self._categories_cache[index]
        widget = self.sub_tabs.widget(index)
        
        if widget.property("loaded"):
            return
            
        base_query = self.db.query(db_mod.Subscriber)
        if hasattr(self, '_current_search_text') and self._current_search_text:
            search_text = self._current_search_text
            base_query = base_query.filter(
                (db_mod.Subscriber.name.like(f"%{search_text}%")) |
                (db_mod.Subscriber.phone.like(f"%{search_text}%")) |
                (db_mod.Subscriber.subscriber_number.like(f"%{search_text}%"))
            )
            
        if cat_name.startswith("طلبات الانضمام"):
            base_query = base_query.filter(db_mod.Subscriber.status == "pending")
        elif cat_name == "قائمة المستبعدين":
            base_query = base_query.filter(db_mod.Subscriber.status == "excluded")
        elif cat_name != "الكل":
            base_query = base_query.filter(db_mod.Subscriber.category == cat_name, db_mod.Subscriber.status != "excluded")
            
        subs = base_query.all()
        
        # Only compute stats for displayed subscribers
        try:
            ids = [s.id for s in subs]
            if ids:
                stats = self.db.query(db_mod.Payment.subscriber_id,
                                      func.count(db_mod.Payment.id),
                                      func.sum(db_mod.Payment.amount))
                stats = stats.filter(db_mod.Payment.subscriber_id.in_(ids), db_mod.Payment.is_paid == True).group_by(db_mod.Payment.subscriber_id).all()
                self._payment_stats = {r[0]: (int(r[1]), float(r[2] or 0)) for r in stats}
            else:
                self._payment_stats = {}
        except Exception:
            self._payment_stats = {}
            
        # Create actual content and replace placeholder
        content = self.create_sub_cards_view(subs)
        
        old_lay = widget.layout()
        if old_lay:
            QWidget().setLayout(old_lay) # Delete old layout and contents
            
        new_lay = QVBoxLayout(widget)
        new_lay.setContentsMargins(0, 0, 0, 0)
        new_lay.addWidget(content)
        
        widget.setProperty("loaded", True)
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
        main_lay = QVBoxLayout(container)
        main_lay.setContentsMargins(0, 0, 0, 0)
        
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(15, 15, 15, 15)
        grid.setSpacing(25)
        main_lay.addWidget(grid_widget)
        
        btn_load = QPushButton()
        btn_load.setStyleSheet("""
            QPushButton {
                background-color: #e2e8f0; color: #334155; padding: 15px; 
                border-radius: 8px; font-weight: bold; margin: 15px;
            }
            QPushButton:hover { background-color: #cbd5e1; }
        """)
        btn_load.setCursor(Qt.CursorShape.PointingHandCursor)
        main_lay.addWidget(btn_load)
        main_lay.addStretch()
        
        columns = 2
        state = {'loaded': 0}
        
        def load_batch():
            start = state['loaded']
            end = min(start + 40, len(subs))
            for idx in range(start, end):
                s = subs[idx]
                row = idx // columns
                col = idx % columns
                card = self.create_subscriber_card(s)
                grid.addWidget(card, row, col)
            state['loaded'] = end
            if end >= len(subs):
                btn_load.hide()
            else:
                btn_load.show()
                btn_load.setText(f"عرض المزيد ({len(subs) - end} متبقي)")
                
        btn_load.clicked.connect(load_batch)
        load_batch()
        
        scroll.setWidget(container)
        return scroll
    def create_subscriber_card(self, s):
        card = QFrame()
        card.setObjectName("StatCard")
        card.setMinimumHeight(250)
        card.setMinimumWidth(400) # زيادة طفيفة في العرض

        # إضافة تأثير الظل
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 30)) # ظل أسود خفيف
        card.setGraphicsEffect(shadow)

        card.setStyleSheet("""
            QFrame#StatCard {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                border: 1px solid #e2e8f0;
                border-radius: 16px;
                padding: 1px; /* هام لتجنب قص الظل */
            }
            QFrame#StatCard:hover {
                border: 1px solid #2563eb;
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
        
        # Status Pill
        if s.status == "excluded":
            status_text = "مستبعد 🚫"
            status_bg = "#fee2e2"
            status_fg = "#991b1b"
        elif s.status == "accepted":
            status_text = "مقبول"
            status_bg = "#d1fae5"
            status_fg = "#065f46"
        else:
            status_text = "معلق"
            status_bg = "#fef3c7"
            status_fg = "#92400e"
        
        status_pill = QLabel(status_text)
        status_pill.setFont(QFont("Tajawal", 8, QFont.Weight.Bold))
        status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_pill.setStyleSheet(f"""
            background: {status_bg};
            color: {status_fg};
            padding: 4px 10px;
            border-radius: 10px;
        """)
        header_lay.addWidget(status_pill)

        # Financial Status Pill
        if s.status == "excluded":
            fin_text, fin_bg, fin_fg = "مستبعد 🚫", "#fee2e2", "#991b1b"
        else:
            fin_status = db_mod.calculate_financial_status(s, self.db)
            if fin_status == "committed":
                fin_text, fin_bg, fin_fg = "ملتزم 🟢", "#d1fae5", "#065f46"
            elif fin_status == "pending_payment":
                fin_text, fin_bg, fin_fg = "بانتظار الدفع 🟡", "#fef3c7", "#92400e"
            elif fin_status == "late":
                fin_text, fin_bg, fin_fg = "متأخر 🔴", "#fee2e2", "#991b1b"
            elif fin_status == "suspended":
                fin_text, fin_bg, fin_fg = "موقوف 🚫", "#f1f5f9", "#475569"
            else:
                fin_text, fin_bg, fin_fg = "معلق", "#fef3c7", "#92400e"

        fin_status_pill = QLabel(fin_text)
        fin_status_pill.setFont(QFont("Tajawal", 8, QFont.Weight.Bold))
        fin_status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fin_status_pill.setStyleSheet(f"""
            background: {fin_bg};
            color: {fin_fg};
            padding: 4px 10px;
            border-radius: 10px;
        """)
        header_lay.addWidget(fin_status_pill)
        
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
        
        paid_count, total_paid = self._payment_stats.get(s.id, (0, 0))
        lbl_paid_val = QLabel(f"{paid_count} أقساط")
        lbl_paid_val.setFont(QFont("Tajawal", 10, QFont.Weight.Bold))
        lbl_paid_val.setStyleSheet("color: #10b981;")
        stats_lay.addWidget(lbl_paid_val, 1, 1)
        
        lbl_total_title = QLabel("إجمالي المدفوع:")
        lbl_total_title.setFont(QFont("Tajawal", 9))
        lbl_total_title.setStyleSheet("color: #94a3b8;")
        stats_lay.addWidget(lbl_total_title, 2, 0)
        
        lbl_total_val = QLabel(f"{total_paid:,.2f} ر.ي")
        lbl_total_val.setFont(QFont("Tajawal", 10, QFont.Weight.Bold))
        lbl_total_val.setStyleSheet("color: #1e3a8a;")
        stats_lay.addWidget(lbl_total_val, 2, 1)
        
        if s.status == "excluded":
            lbl_ex_title = QLabel("سبب الاستبعاد:")
            lbl_ex_title.setFont(QFont("Tajawal", 9))
            lbl_ex_title.setStyleSheet("color: #b91c1c; font-weight: bold;")
            stats_lay.addWidget(lbl_ex_title, 3, 0)
            
            lbl_ex_val = QLabel(s.exclusion_reason or "قرار إداري")
            lbl_ex_val.setFont(QFont("Tajawal", 9))
            lbl_ex_val.setWordWrap(True)
            lbl_ex_val.setStyleSheet("color: #dc2626;")
            stats_lay.addWidget(lbl_ex_val, 3, 1)
        elif s.status == "pending":
            lbl_timer_title = QLabel("الوقت المتبقي:")
            lbl_timer_title.setFont(QFont("Tajawal", 9))
            lbl_timer_title.setStyleSheet("color: #ef4444;")
            stats_lay.addWidget(lbl_timer_title, 3, 0)
            
            created_time = s.created_at or datetime.datetime.now()
            time_diff = datetime.datetime.now() - created_time
            remaining_hours = 48 - (time_diff.total_seconds() / 3600)
            if remaining_hours > 0:
                h = int(remaining_hours)
                m = int((remaining_hours - h) * 60)
                timer_text = f"{h} ساعة و {m} دقيقة"
                timer_color = "#ef4444" # Red
            else:
                timer_text = "انتهت المهلة"
                timer_color = "#ef4444" # Red
                
            lbl_timer_val = QLabel(timer_text)
            lbl_timer_val.setFont(QFont("Tajawal", 10, QFont.Weight.Bold))
            lbl_timer_val.setStyleSheet(f"color: {timer_color};")
            stats_lay.addWidget(lbl_timer_val, 3, 1)
        
        layout.addLayout(stats_lay)
        
        # Action Buttons Row
        actions_lay = QHBoxLayout()
        actions_lay.setSpacing(6)
        
        if s.status == "pending":
            btn_approve = QPushButton("قبول")
            btn_approve.setObjectName("PrimaryBtn")
            btn_approve.setFixedHeight(28)
            btn_approve.setStyleSheet("font-size: 11px; background-color: #10b981; color: white;")
            btn_approve.clicked.connect(lambda checked, sid=s.id: self.approve_subscriber(sid))
            actions_lay.addWidget(btn_approve, 1)
        elif s.status == "excluded":
            btn_reactivate = QPushButton("إلغاء الاستبعاد")
            btn_reactivate.setObjectName("PrimaryBtn")
            btn_reactivate.setFixedHeight(28)
            btn_reactivate.setStyleSheet("font-size: 11px; background-color: #059669; color: white;")
            btn_reactivate.clicked.connect(lambda checked, sid=s.id: self.reactivate_subscriber(sid))
            actions_lay.addWidget(btn_reactivate, 2)
        else:
            btn_exclude = QPushButton("استبعاد")
            btn_exclude.setObjectName("DangerBtn")
            btn_exclude.setFixedHeight(28)
            btn_exclude.setStyleSheet("font-size: 11px; background-color: #fff1f2; color: #e11d48; border: 1px solid #fecdd3;")
            btn_exclude.clicked.connect(lambda checked, sid=s.id: self.exclude_subscriber(sid))
            actions_lay.addWidget(btn_exclude, 1)
        
        btn_details = QPushButton("كشف حساب")
        btn_details.setObjectName("PrimaryBtn")
        btn_details.setFixedHeight(28)
        btn_details.setStyleSheet("font-size: 11px; background-color: #2563eb; color: white;")
        btn_details.clicked.connect(lambda checked, sid=s.id: self.open_account_details(sid))
        actions_lay.addWidget(btn_details, 2)
        
        btn_edit = QPushButton("تعديل")
        btn_edit.setObjectName("PrimaryBtn")
        btn_edit.setFixedHeight(28)
        btn_edit.setStyleSheet("font-size: 11px; background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; font-weight: normal;")
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
        
        sub = self.db.get(db_mod.Subscriber, sid)
        if sub and sub.status == "excluded":
            act_reactivate = QAction("إلغاء الاستبعاد وإعادة التفعيل", self)
            act_reactivate.triggered.connect(lambda: self.reactivate_subscriber(sid))
            menu.addAction(act_reactivate)
        else:
            act_exclude = QAction("استبعاد المشترك", self)
            act_exclude.triggered.connect(lambda: self.exclude_subscriber(sid))
            menu.addAction(act_exclude)

        menu.addAction(act_edit)
        menu.addAction(act_details)
        menu.addSeparator()
        menu.addAction(act_del)
        menu.exec(QCursor.pos())

    def exclude_subscriber(self, sid):
        sub = self.db.get(db_mod.Subscriber, sid)
        if not sub: return
        dlg = ExcludeSubscriberDialog(self, sub)
        if dlg.exec():
            try:
                sub.status = "excluded"
                sub.exclusion_reason = dlg.get_reason()
                sub.excluded_at = datetime.datetime.now()
                self.db.commit()
                self.load_subscribers()
                ModernDialog(self, "تم الاستبعاد", f"تم استبعاد المشترك '{sub.name}' ونقله إلى قائمة المستبعدين.").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء الاستبعاد: {e}").exec()

    def reactivate_subscriber(self, sid):
        sub = self.db.get(db_mod.Subscriber, sid)
        if not sub: return
        if ModernDialog(self, "تأكيد إعادة التفعيل", f"هل تريد إلغاء استبعاد المشترك '{sub.name}' وإعادته للحالة النشطة؟", is_confirm=True).exec():
            try:
                sub.status = "accepted"
                sub.exclusion_reason = None
                sub.excluded_at = None
                self.db.commit()
                self.load_subscribers()
                ModernDialog(self, "نجاح", f"تمت إعادة تفعيل المشترك '{sub.name}' بنجاح.").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ: {e}").exec()

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
        if ModernDialog(self, "تأكيد", "حذف المشترك؟\nسيتم حذف جميع بياناته وأقساطه نهائياً.", is_confirm=True).exec():
            try:
                sub = self.db.get(db_mod.Subscriber, sid)
                if sub:
                    # 1. حذف جميع الأقساط المرتبطة بالمشترك أولاً
                    self.db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sid).delete(synchronize_session=False)
                    
                    # 2. تحرير الرقم المحجوز (إن وُجد)
                    self.db.query(db_mod.SubscriberNumber).filter(
                        db_mod.SubscriberNumber.subscriber_id == sid
                    ).update({"is_reserved": False, "subscriber_id": None}, synchronize_session=False)
                    
                    # 3. إزالة الربط في المشترك نفسه قبل حذفه
                    sub.selected_number_id = None
                    self.db.flush()
                    
                    # 4. الآن يمكن حذف المشترك بأمان
                    self.db.delete(sub)
                    self.db.commit()
                    self.load_subscribers()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"فشل الحذف: {e}").exec()
    def approve_subscriber(self, sid):
        sub = self.db.get(db_mod.Subscriber, sid)
        if sub:
            sub.status = "accepted"
            self.db.commit()
            self.load_subscribers()
            ModernDialog(self, "نجاح", f"تم قبول المشترك {sub.name} بنجاح").exec()
    def open_new_group_from_subscribers(self):
        curr_idx = self.sub_tabs.currentIndex()
        cat = None
        if hasattr(self, '_categories_cache') and 0 <= curr_idx < len(self._categories_cache):
            cat_name = self._categories_cache[curr_idx]
            if cat_name not in ["الكل", "قائمة المستبعدين"] and not cat_name.startswith("طلبات الانضمام"):
                cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == cat_name).first()
        if not cat:
            cat = self.db.query(db_mod.Category).first()
            
        dlg = CreateGroupBatchDialog(self, cat)
        if dlg.exec():
            try:
                name = dlg.ent_name.text().strip()
                amount = float(dlg.ent_amount.text().strip())
                prize = float(dlg.ent_prize.text().strip())
                cycles = int(dlg.ent_cycles.text().strip())
                inst = int(dlg.ent_inst.text().strip())
                start_date_q = dlg.dt_start.date()
                start_date = datetime.datetime(start_date_q.year(), start_date_q.month(), start_date_q.day())
                
                prefix = dlg.ent_prefix.text().strip()
                num_start = int(dlg.ent_num_start.text().strip())
                num_end = int(dlg.ent_num_end.text().strip())
                
                if num_start > num_end:
                    ModernDialog(self, "خطأ", "رقم البداية يجب أن يكون أصغر من رقم النهاية").exec()
                    return

                exists = self.db.query(db_mod.Category).filter(db_mod.Category.name == name).first()
                if exists:
                    ModernDialog(self, "خطأ", "هذا الاسم موجود بالفعل، يرجى اختيار اسم مختلف للمجموعة.").exec()
                    return
                
                new_cat = db_mod.Category(
                    name=name,
                    amount=amount,
                    prize_amount=prize,
                    max_cycles=cycles,
                    max_installments=inst,
                    start_date=start_date,
                    is_active=True
                )
                self.db.add(new_cat)
                self.db.flush()
                
                nums_to_add = []
                for i in range(num_start, num_end + 1):
                    formatted_num = f"{prefix}{i:02d}" if (num_end >= 10 and len(str(i)) < 2) else f"{prefix}{i}"
                    nums_to_add.append(db_mod.SubscriberNumber(
                        number=formatted_num,
                        category_id=new_cat.id,
                        is_reserved=False
                    ))
                self.db.bulk_save_objects(nums_to_add)
                self.db.commit()
                
                self.load_subscribers()
                ModernDialog(self, "نجاح", f"تم إنشاء المجموعة '{name}' بنجاح وتوليد {len(nums_to_add)} رقماً لها.").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء إنشاء المجموعة: {e}").exec()

    def add_new_subscriber(self):
        dlg = AddSubscriberDialog(self, self.db)
        if dlg.exec():
            try:
                name = dlg.ent_name.text()
                phone = dlg.ent_phone.text().strip()
                cat_name = dlg.cb_cat.currentText()
                sub_num_text = dlg.cb_num.currentText()
                sub_num_id = dlg.cb_num.currentData()

                pwd = dlg.ent_pwd.text()

                if not name or not phone or not pwd:
                    ModernDialog(self, "خطأ", "يرجى إدخال الاسم ورقم الهاتف وكلمة المرور.").exec()
                    return

                # التأكد من عدم تكرار رقم الهاتف
                existing_phone = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.phone == phone).first()
                if existing_phone:
                    ModernDialog(self, "خطأ", "رقم الهاتف مسجل مسبقاً لمشترك آخر.").exec()
                    return

                # التأكد من صحة رقم المشترك المختار
                if sub_num_id is None:
                    ModernDialog(self, "خطأ", "الرجاء اختيار رقم مشترك صالح.").exec()
                    return

                sub_num_obj = self.db.get(db_mod.SubscriberNumber, sub_num_id)
                if not sub_num_obj or sub_num_obj.is_reserved:
                    ModernDialog(self, "خطأ", "هذا الرقم تم حجزه مؤخراً، يرجى اختيار رقم آخر.").exec()
                    return

                # 1. Create Subscriber (don't set selected_number_id until validated)
                new_sub = db_mod.Subscriber(
                    name=name,
                    phone=phone,
                    password=security.hash_password(pwd),
                    category=cat_name,
                    subscriber_number=sub_num_text,
                    status="accepted"
                )
                self.db.add(new_sub)
                self.db.flush()  # للحصول على ID المشترك قبل الربط

                # 2. تحديث حالة الرقم وربطه بالمشترك
                sub_num_obj.is_reserved = True
                sub_num_obj.subscriber_id = new_sub.id
                new_sub.selected_number_id = sub_num_id

                try:
                    # 3. توليد الأقساط الفائتة والقسط الحالي فقط بناءً على تاريخ بداية الفئة
                    cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == cat_name).first()
                    if cat and cat.start_date:
                        start_date = cat.start_date.date()
                        today = datetime.date.today()
                        
                        # حساب عدد الأيام التي مضت منذ بداية الهكبة (بافتراض قسط واحد يومياً)
                        days_passed = (today - start_date).days
                        
                        if days_passed >= 0:
                            max_c = int(cat.max_cycles or 1)
                            max_i = int(cat.max_installments or 1)
                            total_possible = max_c * max_i
                            
                            # نولد فقط الأقساط التي حان موعدها أو فات موعدها (بحد أقصى إجمالي أقساط الهكبة)
                            count_to_gen = min(days_passed + 1, total_possible)
                            
                            for i in range(count_to_gen):
                                c_num = (i // max_i) + 1
                                i_num = (i % max_i) + 1
                                due_dt = datetime.datetime.combine(start_date + datetime.timedelta(days=i), datetime.time.min)
                                
                                # التأكد من عدم وجود القسط مسبقاً
                                self.db.add(db_mod.Payment(
                                    subscriber_id=new_sub.id,
                                    amount=cat.amount,
                                    due_date=due_dt,
                                    is_paid=False,
                                    cycle_number=c_num,
                                    installment_number=i_num,
                                    note=db_mod.build_installment_note(is_paid=False, due_date=due_dt)
                                ))
                    self.db.commit()
                except Exception as e:
                    self.db.rollback()
                    print(f"Error generating initial payments: {e}")
                
                self.load_subscribers()
                ModernDialog(self, "نجاح", f"تم إضافة المشترك {name} بنجاح").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"فشل الإضافة: {e}").exec()
    def open_account_details(self, sid):
        AccountDetailsDialog(self, sid, self.db).exec()
    def open_batch_payment(self):
        dialog = BatchPaymentDialog(self, self.db)
        dialog.exec()
        self.load_subscribers()
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
    def export_subscribers_excel(self):
        try:
            subs = self.db.query(db_mod.Subscriber).all()
            data = [{"الاسم": s.name, "الهاتف": s.phone, "رقم الحساب": s.subscriber_number, "الفئة": s.category} for s in subs]
            df = pd.DataFrame(data)
            
            filename, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير المشتركين (Excel)", "subscribers_report.xlsx", "Excel Files (*.xlsx)")
            if not filename: return
            
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Subscribers', index=False, startrow=3)
                workbook = writer.book
                worksheet = writer.sheets['Subscribers']
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#2e7d32', 'color': 'white', 'border': 1, 'align': 'center'})
                title_fmt = workbook.add_format({'bold': True, 'font_size': 16, 'color': '#2e7d32'})
                worksheet.write(0, 0, "تقرير عام لجميع المشتركين", title_fmt)
                worksheet.write(1, 0, f"تاريخ الاستخراج: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(3, col_num, value, header_fmt)
                    column_len = max(df[value].astype(str).str.len().max(), len(value) + 2)
                    worksheet.set_column(col_num, col_num, column_len)

            ModernDialog(self, "نجاح", f"تم تصدير ملف {filename} بنجاح").exec()
        except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()
    def export_subscribers_pdf(self):
        try:
            subs = self.db.query(db_mod.Subscriber).all()
            
            filename, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير المشتركين (PDF)", "subscribers_report.pdf", "PDF Files (*.pdf)")
            if not filename: return
            
            c = canvas.Canvas(filename, pagesize=A4)
            width, height = A4
            margin = 40
            GOLD        = colors.HexColor("#c9a84c")
            DARK_GREEN  = colors.HexColor("#052109")
            MID_GREEN   = colors.HexColor("#0a3d0e")
            ROW_ALT     = colors.HexColor("#f1f8f1")
            
            # Register Arabic Font (Try common Windows path)
            possible_fonts = [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/tahoma.ttf",
                "static/arial.ttf"
            ]
            font_path = next((p for p in possible_fonts if os.path.exists(p)), None)
            font_name = 'ArabicFont'
            try:
                if font_path: pdfmetrics.registerFont(TTFont('ArabicFont', font_path))
                else: font_name = 'Helvetica'
            except: font_name = 'Helvetica'

            # --- الترويسة الاحترافية ---
            c.setFillColor(DARK_GREEN)
            c.rect(0, height - 80, width, 80, fill=1, stroke=0)
            
            c.setFillColor(GOLD)
            c.setFont(font_name, 20)
            c.drawCentredString(width/2, height - 40, reshape_text("هكبة المليون - قائمة المشتركين"))
            
            c.setFillColor(colors.white)
            c.setFont(font_name, 10)
            c.drawCentredString(width/2, height - 60, reshape_text("تقرير إداري عام لجميع الفئات المسجلة"))

            # --- جدول البيانات ---
            c.setFillColor(colors.black)
            y = height - 120
            headers = ["الاسم", "الهاتف", "رقم الحساب", "الفئة"]
            col_x = [margin+10, margin+160, margin+280, margin+400]
            
            c.setFillColor(MID_GREEN)
            c.rect(margin, y - 5, width - 2*margin, 20, fill=1)
            c.setFillColor(GOLD)
            c.setFont(font_name, 11)
            for i, h in enumerate(headers): c.drawString(col_x[i], y, reshape_text(h))
            
            y -= 30
            c.setFont(font_name, 10)
            for idx, s in enumerate(subs):
                if y < 60:
                    c.showPage()
                    y = height - 50
                    c.setFont(font_name, 10)
                if idx % 2 == 1:
                    c.setFillColor(ROW_ALT)
                    c.rect(margin, y - 5, width - 2*margin, 18, fill=1)
                c.setFillColor(colors.black)
                c.drawString(col_x[0], y, reshape_text((s.name or "")[:35]))
                c.drawString(col_x[1], y, reshape_text(s.phone or ""))
                c.drawString(col_x[2], y, reshape_text(s.subscriber_number or ""))
                c.drawString(col_x[3], y, reshape_text(s.category or ""))
                y -= 20
                
            c.save()
            ModernDialog(self, "نجاح", f"تم تصدير ملف {filename} بنجاح").exec()
        except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()