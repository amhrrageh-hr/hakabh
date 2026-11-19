from sqlalchemy import func, case
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
from gui.dialogs import BatchProgressDialog, ModernDialog

class CapitalMixin:
    def init_capital_page(self):
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        
        title = QLabel("إدارة رأس المال والتدفق المالي")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        header_layout.addWidget(QLabel("اختر الفئة:"))
        self.cap_filter_cat = QComboBox()
        self.cap_filter_cat.addItem("كل الفئات", None)
        self.cap_filter_cat.currentIndexChanged.connect(self.refresh_capital_on_category_change)
        header_layout.addWidget(self.cap_filter_cat)
        btn_reset_cat = QPushButton("عرض كل الفئات")
        btn_reset_cat.setObjectName("SecondaryBtn")
        btn_reset_cat.clicked.connect(lambda: self.cap_filter_cat.setCurrentIndex(0))
        header_layout.addWidget(btn_reset_cat)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Stats Grid (شبكة متجاوبة 3 أعمدة × صفين لتتكيف مع الشاشات الصغيرة والكبيرة دون تمرير أفقي)
        self.capital_stats_layout = QGridLayout()
        self.capital_stats_layout.setSpacing(10)
        layout.addLayout(self.capital_stats_layout)
        
        # Tabs
        self.capital_tabs = QTabWidget()
        self.capital_tabs.tabBar().setUsesScrollButtons(True)
        self.capital_tabs.tabBar().setExpanding(False)
        layout.addWidget(self.capital_tabs)

        def _make_responsive_table(tbl):
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            tbl.horizontalHeader().setMinimumSectionSize(42)
            tbl.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
            tbl.setWordWrap(True)
            tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            tbl.setStyleSheet(
                "QTableWidget { font-size: 11px; } "
                "QHeaderView::section { font-size: 11px; padding: 4px 3px; }"
            )
            tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Tab 1: Categories summary
        self.tab_cap_categories = QWidget()
        t1_layout = QVBoxLayout(self.tab_cap_categories)
        t1_layout.setContentsMargins(10, 10, 10, 10)
        t1_layout.setSpacing(10)
        
        t1_header = QHBoxLayout()
        t1_header.addWidget(QLabel("تحليل السيولة ورأس المال حسب الفئات"))
        t1_header.addStretch()
        btn_cat_cap_excel = QPushButton("تصدير Excel للفئات")
        btn_cat_cap_excel.setObjectName("PrimaryBtn")
        btn_cat_cap_excel.clicked.connect(self.export_categories_financial_excel)
        t1_header.addWidget(btn_cat_cap_excel)
        t1_layout.addLayout(t1_header)
        
        self.table_cap_categories = QTableWidget()
        self.table_cap_categories.setColumnCount(9)
        self.table_cap_categories.setHorizontalHeaderLabels([
            "الفئة",
            "القسط / الدورة",
            "المشتركين",
            "المستهدف للموسم",
            "المستحق لليوم",
            "المحصل",
            "المتأخرات",
            "المتبقي للموسم",
            "نسبة التحصيل",
        ])
        _make_responsive_table(self.table_cap_categories)
        self.table_cap_categories.setMinimumHeight(240)
        t1_layout.addWidget(self.table_cap_categories)
        
        self.capital_tabs.addTab(self.tab_cap_categories, "تحليل الفئات والسيولة")
        
        # Tab 2: Defaulters / Unpaid
        self.tab_cap_defaulters = QWidget()
        t2_layout = QVBoxLayout(self.tab_cap_defaulters)
        t2_layout.setContentsMargins(10, 10, 10, 10)
        t2_layout.setSpacing(10)
        
        t2_header = QHBoxLayout()
        t2_header.addWidget(QLabel("بحث:"))
        self.cap_search_def = QLineEdit()
        self.cap_search_def.setPlaceholderText("ابحث باسم المشترك أو الهاتف أو رقم الحساب...")
        self._cap_search_def_timer = QTimer(page)
        self._cap_search_def_timer.setSingleShot(True)
        self._cap_search_def_timer.setInterval(300)
        self._cap_search_def_timer.timeout.connect(self.refresh_capital_defaulters)
        self.cap_search_def.textChanged.connect(lambda: self._cap_search_def_timer.start())
        self.cap_search_def.returnPressed.connect(lambda: (self._cap_search_def_timer.stop(), self.refresh_capital_defaulters()))
        t2_header.addWidget(self.cap_search_def, 1)
        
        btn_pay_all = QPushButton("⚡ سداد المتأخرات دفعة واحدة")
        btn_pay_all.setStyleSheet("background-color: #22c55e; color: white; border-radius: 4px; padding: 5px 12px; font-weight: bold;")
        btn_pay_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pay_all.clicked.connect(self.quick_pay_all_defaulters)
        t2_header.addWidget(btn_pay_all)
        
        btn_def_excel = QPushButton("تصدير كشف المتأخرات")
        btn_def_excel.setObjectName("PrimaryBtn")
        btn_def_excel.clicked.connect(self.export_defaulters_excel)
        t2_header.addWidget(btn_def_excel)
        t2_layout.addLayout(t2_header)
        
        self.table_cap_defaulters = QTableWidget()
        self.table_cap_defaulters.setColumnCount(7)
        self.table_cap_defaulters.setHorizontalHeaderLabels([
            "المشترك", "الهاتف", "الفئة", "الدورة/القسط", "الاستحقاق", "المبلغ المستحق", "إجراء سريع"
        ])
        _make_responsive_table(self.table_cap_defaulters)
        self.table_cap_defaulters.setMinimumHeight(240)
        # تفعيل النقر المزدوج لفتح كشف الحساب من جدول المتأخرات
        self.table_cap_defaulters.cellDoubleClicked.connect(lambda r, c: self.open_account_details(self.table_cap_defaulters.item(r, 0).data(Qt.ItemDataRole.UserRole)))
        t2_layout.addWidget(self.table_cap_defaulters)
        
        self.capital_tabs.addTab(self.tab_cap_defaulters, "الأقساط غير المسددة (المتأخرات)")
        
        # Tab 3: General financial standing
        self.tab_cap_standing = QWidget()
        t3_layout = QVBoxLayout(self.tab_cap_standing)
        t3_layout.setContentsMargins(10, 10, 10, 10)
        t3_layout.setSpacing(10)
        
        t3_header = QHBoxLayout()
        t3_header.addWidget(QLabel("الموقف المالي:"))
        self.cap_search_standing = QLineEdit()
        self.cap_search_standing.setPlaceholderText("ابحث باسم المشترك أو الهاتف أو رقم الحساب...")
        self._cap_search_standing_timer = QTimer(page)
        self._cap_search_standing_timer.setSingleShot(True)
        self._cap_search_standing_timer.setInterval(300)
        self._cap_search_standing_timer.timeout.connect(self.refresh_capital_standing)
        self.cap_search_standing.textChanged.connect(lambda: self._cap_search_standing_timer.start())
        self.cap_search_standing.returnPressed.connect(lambda: (self._cap_search_standing_timer.stop(), self.refresh_capital_standing()))
        t3_header.addWidget(self.cap_search_standing, 1)

        btn_standing_excel = QPushButton("تصدير Excel")
        btn_standing_excel.setObjectName("PrimaryBtn")
        btn_standing_excel.clicked.connect(self.export_standing_excel)
        t3_header.addWidget(btn_standing_excel)

        t3_layout.addLayout(t3_header)
        
        self.table_cap_standing = QTableWidget()
        self.table_cap_standing.setColumnCount(7)
        self.table_cap_standing.setHorizontalHeaderLabels([
            "اسم المشترك", "الفئة", "رقم الحساب", "المستحق لليوم", "إجمالي المسدد", "المتأخرات", "الحالة المالية"
        ])
        _make_responsive_table(self.table_cap_standing)
        self.table_cap_standing.setMinimumHeight(240)
        self.table_cap_standing.cellDoubleClicked.connect(lambda r, c: self.open_account_details(self.table_cap_standing.item(r, 0).data(Qt.ItemDataRole.UserRole)))
        t3_layout.addWidget(self.table_cap_standing)
        
        self.capital_tabs.addTab(self.tab_cap_standing, "المواقف المالية للمشتركين")

        # Tab 4: Operational Expenses
        self.tab_cap_expenses = QWidget()
        t4_layout = QVBoxLayout(self.tab_cap_expenses)
        t4_layout.setContentsMargins(10, 10, 10, 10)
        t4_layout.setSpacing(10)
        
        t4_upper = QHBoxLayout()
        t4_upper.setSpacing(15)
        
        form_card = QFrame()
        form_card.setObjectName("StatCard")
        form_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        form_vbox = QVBoxLayout(form_card)
        form_vbox.setContentsMargins(20, 20, 20, 20)
        form_vbox.setSpacing(15)
        
        lbl_title = QLabel("إضافة نفقة تشغيلية جديدة")
        lbl_title.setObjectName("SectionTitle")
        form_vbox.addWidget(lbl_title)
        
        form_lay = QGridLayout()
        form_lay.setSpacing(15)
        
        form_lay.addWidget(QLabel("البيان / الوصف:"), 0, 0)
        self.exp_title_input = QLineEdit()
        self.exp_title_input.setPlaceholderText("مثال: تكلفة رسائل SMS...")
        form_lay.addWidget(self.exp_title_input, 0, 1)
        
        form_lay.addWidget(QLabel("المبلغ (ر.ي):"), 0, 2)
        self.exp_amount_input = QLineEdit()
        self.exp_amount_input.setPlaceholderText("0.00")
        form_lay.addWidget(self.exp_amount_input, 0, 3)
        
        form_lay.addWidget(QLabel("التصنيف:"), 1, 0)
        self.exp_cat_combo = QComboBox()
        self.exp_cat_combo.addItems(["سيرفرات وتقنية", "رسائل SMS", "رواتب وأجور", "تسويق وإعلانات", "أخرى"])
        form_lay.addWidget(self.exp_cat_combo, 1, 1)
        
        form_lay.addWidget(QLabel("ملاحظات:"), 1, 2)
        self.exp_note_input = QLineEdit()
        self.exp_note_input.setPlaceholderText("اختياري...")
        form_lay.addWidget(self.exp_note_input, 1, 3)

        form_lay.addWidget(QLabel("الفئة المالية:"), 2, 0)
        self.exp_sub_cat_combo = QComboBox()
        self.exp_sub_cat_combo.addItem("مصاريف عامة (الكل)", None)
        form_lay.addWidget(self.exp_sub_cat_combo, 2, 1)
        
        form_vbox.addLayout(form_lay)
        
        btn_add_exp = QPushButton("إضافة النفقة")
        btn_add_exp.setObjectName("PrimaryBtn")
        btn_add_exp.setFixedHeight(40)
        btn_add_exp.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_exp.clicked.connect(self.add_new_expense)
        
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        btn_lay.addWidget(btn_add_exp)
        form_vbox.addLayout(btn_lay)
        
        t4_upper.addWidget(form_card)
        t4_layout.addLayout(t4_upper)
        
        # Expenses Summary
        self.exp_summary_layout = QGridLayout()
        self.exp_summary_layout.setSpacing(15)
        t4_layout.addLayout(self.exp_summary_layout)
        
        t4_header = QHBoxLayout()
        t4_header.addWidget(QLabel("جدول النفقات التشغيلية:"))
        
        self.exp_filter_cat = QComboBox()
        self.exp_filter_cat.addItem("كل التصنيفات", None)
        self.exp_filter_cat.addItems(["سيرفرات وتقنية", "رسائل SMS", "رواتب وأجور", "تسويق وإعلانات", "أخرى"])
        for i in range(1, self.exp_filter_cat.count()):
            self.exp_filter_cat.setItemData(i, self.exp_filter_cat.itemText(i))
        self.exp_filter_cat.currentIndexChanged.connect(self.refresh_capital_expenses)
        t4_header.addWidget(self.exp_filter_cat)
        
        self.exp_search_input = QLineEdit()
        self.exp_search_input.setPlaceholderText("ابحث باسم النفقة أو الملاحظات...")
        self._exp_search_timer = QTimer(page)
        self._exp_search_timer.setSingleShot(True)
        self._exp_search_timer.setInterval(350)
        self._exp_search_timer.timeout.connect(self.refresh_capital_expenses)
        self.exp_search_input.textChanged.connect(lambda: self._exp_search_timer.start())
        self.exp_search_input.returnPressed.connect(lambda: (self._exp_search_timer.stop(), self.refresh_capital_expenses()))
        t4_header.addWidget(self.exp_search_input, 1)
        
        btn_exp_excel = QPushButton("تصدير كشف المصاريف")
        btn_exp_excel.setObjectName("PrimaryBtn")
        btn_exp_excel.clicked.connect(self.export_expenses_excel)
        t4_header.addWidget(btn_exp_excel)
        t4_layout.addLayout(t4_header)
        
        self.table_cap_expenses = QTableWidget()
        self.table_cap_expenses.setColumnCount(7)
        self.table_cap_expenses.setHorizontalHeaderLabels([
            "البيان / الوصف", "المبلغ (ر.ي)", "التصنيف", "الفئة المالية", "التاريخ والوقت", "الملاحظات", "إجراء"
        ])
        _make_responsive_table(self.table_cap_expenses)
        self.table_cap_expenses.setMinimumHeight(230)
        t4_layout.addWidget(self.table_cap_expenses)
        
        self.capital_tabs.addTab(self.tab_cap_expenses, "النفقات التشغيلية")
        
        # Tab 5: Winner Payouts (مستحقات الفائزين بالقرعة)
        self.tab_cap_winners = QWidget()
        t5_layout = QVBoxLayout(self.tab_cap_winners)
        t5_layout.setContentsMargins(10, 10, 10, 10)
        t5_layout.setSpacing(10)
        
        t5_header = QHBoxLayout()
        t5_header.addWidget(QLabel("تصفية بالحالة:"))
        self.cap_filter_winner_status = QComboBox()
        self.cap_filter_winner_status.addItem("الكل", None)
        self.cap_filter_winner_status.addItem("استلم (تم التسليم)", True)
        self.cap_filter_winner_status.addItem("لم يستلم بعد", False)
        self.cap_filter_winner_status.currentIndexChanged.connect(self.refresh_capital_winners)
        t5_header.addWidget(self.cap_filter_winner_status)
        
        t5_header.addWidget(QLabel("بحث:"))
        self.cap_search_winners = QLineEdit()
        self.cap_search_winners.setPlaceholderText("ابحث باسم المشترك، رقم الحساب، أو الهاتف...")
        self._cap_search_win_timer = QTimer(page)
        self._cap_search_win_timer.setSingleShot(True)
        self._cap_search_win_timer.setInterval(350)
        self._cap_search_win_timer.timeout.connect(self.refresh_capital_winners)
        self.cap_search_winners.textChanged.connect(lambda: self._cap_search_win_timer.start())
        self.cap_search_winners.returnPressed.connect(lambda: (self._cap_search_win_timer.stop(), self.refresh_capital_winners()))
        t5_header.addWidget(self.cap_search_winners, 1)
        
        btn_win_excel = QPushButton("تصدير Excel")
        btn_win_excel.setObjectName("PrimaryBtn")
        btn_win_excel.clicked.connect(self.export_capital_winners_excel)
        t5_header.addWidget(btn_win_excel)
        t5_layout.addLayout(t5_header)
        
        self.table_cap_winners = QTableWidget()
        self.table_cap_winners.setColumnCount(10)
        self.table_cap_winners.setHorizontalHeaderLabels([
            "المشترك", "الهاتف", "الفئة", "نوع القرعة", "الدورة", 
            "تاريخ الفوز", "المستحق", "الحالة", "تاريخ الاستلام", "إجراء"
        ])
        _make_responsive_table(self.table_cap_winners)
        self.table_cap_winners.setMinimumHeight(230)
        t5_layout.addWidget(self.table_cap_winners)
        
        self.capital_tabs.addTab(self.tab_cap_winners, "مستحقات الفائزين بالقرعة")
        self.capital_tabs.currentChanged.connect(self.refresh_current_capital_tab)

        try:
            self.load_capital_category_filter()
        except Exception:
            pass

        page.setWidget(container)
        return page

    def refresh_current_capital_tab(self):
        idx = self.capital_tabs.currentIndex()
        if idx == 0:
            self.refresh_capital_categories()
        elif idx == 1:
            self.refresh_capital_defaulters()
        elif idx == 2:
            self.refresh_capital_standing()
        elif idx == 3:
            self.refresh_capital_expenses()
        elif idx == 4:
            self.refresh_capital_winners()

    def show_capital_management(self):
        page = self._ensure_page('page_capital', self.init_capital_page)
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all()
        self.content_stack.setCurrentWidget(page)
        self._update_nav_style("إدارة رأس المال")
        self.load_capital_category_filter()
        self.refresh_capital_stats()
        self.refresh_current_capital_tab()

    def load_capital_category_filter(self):
        curr_filter = self.cap_filter_cat.currentData() if hasattr(self, 'cap_filter_cat') else None
        curr_exp_cat = self.exp_sub_cat_combo.currentData() if hasattr(self, 'exp_sub_cat_combo') else None

        self.cap_filter_cat.blockSignals(True)
        self.cap_filter_cat.clear()
        self.cap_filter_cat.addItem("كل الفئات", None)

        self.exp_sub_cat_combo.blockSignals(True)
        self.exp_sub_cat_combo.clear()
        self.exp_sub_cat_combo.addItem("مصاريف عامة (الكل)", None)

        seen_names = set()
        for cat in self.db.query(db_mod.Category).order_by(db_mod.Category.id.asc()).all():
            if cat.name and cat.name not in seen_names:
                seen_names.add(cat.name)
                self.cap_filter_cat.addItem(cat.name, cat.name)
                self.exp_sub_cat_combo.addItem(cat.name, cat.name)

        for (sub_cat,) in self.db.query(db_mod.Subscriber.category).distinct().all():
            if sub_cat and sub_cat not in seen_names:
                seen_names.add(sub_cat)
                self.cap_filter_cat.addItem(sub_cat, sub_cat)
                self.exp_sub_cat_combo.addItem(sub_cat, sub_cat)

        if curr_filter:
            idx = self.cap_filter_cat.findData(curr_filter)
            if idx >= 0:
                self.cap_filter_cat.setCurrentIndex(idx)
        if curr_exp_cat:
            idx_e = self.exp_sub_cat_combo.findData(curr_exp_cat)
            if idx_e >= 0:
                self.exp_sub_cat_combo.setCurrentIndex(idx_e)

        self.exp_sub_cat_combo.blockSignals(False)
        self.cap_filter_cat.blockSignals(False)

    def refresh_capital_on_category_change(self):
        self.refresh_capital_stats()
        self.refresh_current_capital_tab()

    def sync_unpaid_installments(self):
        """توليد الأقساط اليومية المفقودة للمشتركين بشكل موحد وآمن دون أي تكرار عبر الدالة المركزية"""
        def _background_worker():
            bg_db = db_mod.SessionLocal()
            try:
                subscribers = bg_db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted").all()
                for sub in subscribers:
                    try:
                        db_mod.ensure_daily_payments(bg_db, sub)
                    except Exception as sub_err:
                        print(f"Error syncing installments for sub {sub.id}: {sub_err}")
            except Exception as e:
                print(f"Error during auto-sync: {e}")
                bg_db.rollback()
            finally:
                bg_db.close()

        import threading
        threading.Thread(target=_background_worker, daemon=True).start()

    def refresh_capital_stats(self):
        """قراءة الإحصائيات المالية مباشرة من قاعدة البيانات المحلية بسرعة فورية (بدون انتظار اتصال شبكي ميت)."""
        self._render_capital_stats_db()

    def _compute_default_winner_payout(self, w, sub, cat_obj):
        """حساب المبلغ المستحق الافتراضي للفائز حسب نوع القرعة والفئة بدقة."""
        saved_amt = float(w.payout_amount or 0.0)
        if saved_amt > 0:
            return saved_amt
        if not cat_obj:
            return 0.0
        draw_t = (w.draw_type or "").strip()
        if "تحفيزية" in draw_t:
            # الجائزة التحفيزية يحدد المشرف قيمتها عند التسليم (أو قيمة قسط واحد افتراضياً)
            return float(cat_obj.amount or 0.0)
        # القرعة الأسبوعية أو الكبرى: جائزة الفئة المحددة أو إجمالي دورة الفئة
        if cat_obj.prize_amount and float(cat_obj.prize_amount) > 0:
            return float(cat_obj.prize_amount)
        return float((cat_obj.amount or 0.0) * (cat_obj.max_installments or 1))

    def _render_capital_stats_db(self):
        try:
            self.db.expire_all()
        except Exception:
            pass
        for i in reversed(range(self.capital_stats_layout.count())):
            widget = self.capital_stats_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        sel_cat = self.cap_filter_cat.currentData() if hasattr(self, 'cap_filter_cat') else None
        now_val = datetime.datetime.now()

        # 1. حساب رأس المال المستهدف للموسم الكامل حسب الفئات والمشتركين المقبولين
        cat_q = self.db.query(db_mod.Category)
        if sel_cat:
            cat_q = cat_q.filter(db_mod.Category.name == sel_cat)
        cats_list = cat_q.all()
        cats_map = {c.name: c for c in cats_list}

        sub_counts_by_cat = dict(
            self.db.query(db_mod.Subscriber.category, func.count(db_mod.Subscriber.id))
            .filter(db_mod.Subscriber.status == "accepted")
            .group_by(db_mod.Subscriber.category)
            .all()
        )

        season_target_capital = 0.0
        for c_obj in cats_list:
            s_cnt = sub_counts_by_cat.get(c_obj.name, 0)
            c_inst = max(1, int(c_obj.max_installments or 1))
            c_cycles = max(1, int(c_obj.max_cycles or 1))
            season_target_capital += s_cnt * float(c_obj.amount or 0.0) * c_inst * c_cycles

        base_filter = [db_mod.Subscriber.status == "accepted"]
        if sel_cat:
            base_filter.append(db_mod.Subscriber.category == sel_cat)

        stats_row = self.db.query(
            func.coalesce(func.sum(db_mod.Payment.amount), 0).label("generated_expected"),
            func.coalesce(func.sum(case((db_mod.Payment.due_date <= now_val, db_mod.Payment.amount), else_=0)), 0).label("due_so_far"),
            func.coalesce(func.sum(case((db_mod.Payment.is_paid == True, db_mod.Payment.amount), else_=0)), 0).label("collected"),
            func.coalesce(func.sum(case(((db_mod.Payment.is_paid == False) & (db_mod.Payment.due_date <= now_val), db_mod.Payment.amount), else_=0)), 0).label("arrears"),
            func.coalesce(func.count(case(((db_mod.Payment.is_paid == False) & (db_mod.Payment.due_date <= now_val), 1), else_=None)), 0).label("arrears_count"),
        ).join(db_mod.Subscriber, db_mod.Subscriber.id == db_mod.Payment.subscriber_id).filter(*base_filter).first()

        due_so_far = float(stats_row.due_so_far) if stats_row else 0.0
        generated_expected = float(stats_row.generated_expected) if stats_row else 0.0
        total_collected = float(stats_row.collected) if stats_row else 0.0
        total_arrears = float(stats_row.arrears) if stats_row else 0.0
        arrears_count = int(stats_row.arrears_count) if stats_row else 0

        if season_target_capital <= 0:
            season_target_capital = generated_expected

        exp_query = self.db.query(func.coalesce(func.sum(db_mod.Expense.amount), 0))
        if sel_cat:
            exp_query = exp_query.filter(db_mod.Expense.subscriber_category == sel_cat)
        total_expenses = float(exp_query.scalar() or 0.0)

        # حساب مستحقات الفائزين المسلمة وغير المسلمة
        all_winners = self.db.query(db_mod.Winner).all()
        all_subs = self.db.query(db_mod.Subscriber).all()
        sub_by_num = {s.subscriber_number: s for s in all_subs if s.subscriber_number}

        total_winner_payouts = 0.0
        pending_winners_count = 0
        for w in all_winners:
            sub = sub_by_num.get(w.subscriber_number)
            sub_cat = sub.category if sub else None
            if sel_cat and sub_cat != sel_cat:
                continue
            if w.is_received:
                total_winner_payouts += float(w.payout_amount or 0.0)
            else:
                pending_winners_count += 1

        net_cash = total_collected - total_expenses - total_winner_payouts
        collection_pct = (total_collected / due_so_far * 100.0) if due_so_far > 0 else 100.0

        stats = [
            (
                "رأس المال المستهدف للموسم",
                f"{season_target_capital:,.2f} ر.ي",
                f"المستحق حتى اليوم: {due_so_far:,.0f} ر.ي",
                "#3b82f6",
            ),
            (
                "المبالغ المحصلة (الإيرادات)",
                f"{total_collected:,.2f} ر.ي",
                f"نسبة تحصيل المستحق: {collection_pct:.1f}%",
                "#2e7d32",
            ),
            (
                "الأقساط المتأخرة (المستحقة)",
                f"{total_arrears:,.2f} ر.ي",
                f"عدد الأقساط المتأخرة: {arrears_count} قسط",
                "#ef4444",
            ),
            (
                "مستحقات الفائزين (المسلّمة)",
                f"{total_winner_payouts:,.2f} ر.ي",
                f"فائزون بانتظار التسليم: {pending_winners_count}",
                "#8b5cf6",
            ),
            (
                "النفقات التشغيلية",
                f"{total_expenses:,.2f} ر.ي",
                "مخصومة من السيولة",
                "#ec4899",
            ),
            (
                "صافي السيولة النقدية المتوفرة",
                f"{net_cash:,.2f} ر.ي",
                "المحصل - (المصاريف + جوائز مسلّمة)",
                "#06b6d4" if net_cash >= 0 else "#ef4444",
            ),
        ]

        for idx_card, (title, value, sub_txt, color) in enumerate(stats):
            card = QFrame()
            card.setObjectName("StatCard")
            card.setMinimumHeight(92)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            vbox = QVBoxLayout(card)
            vbox.setContentsMargins(10, 8, 10, 8)
            vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.setSpacing(3)

            t_lbl = QLabel(title)
            t_lbl.setObjectName("StatTitle")
            t_lbl.setWordWrap(True)
            t_lbl.setStyleSheet("font-size: 12px; font-weight: bold;")
            t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(t_lbl)

            v_lbl = QLabel(value)
            v_lbl.setObjectName("StatValue")
            v_lbl.setWordWrap(True)
            v_lbl.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(v_lbl)

            s_lbl = QLabel(sub_txt)
            s_lbl.setWordWrap(True)
            s_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
            s_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(s_lbl)

            row_i = idx_card // 3
            col_i = idx_card % 3
            self.capital_stats_layout.addWidget(card, row_i, col_i)
        for c_i in range(3):
            self.capital_stats_layout.setColumnStretch(c_i, 1)

    def _get_categories_financial_summary_rows(self):
        """حساب ملخص السيولة ورأس المال لكل فئة بدقة عالية واستعلام تجميعي واحد."""
        sel_cat = self.cap_filter_cat.currentData() if hasattr(self, 'cap_filter_cat') else None
        now_val = datetime.datetime.now()

        query = self.db.query(db_mod.Category)
        if sel_cat:
            query = query.filter(db_mod.Category.name == sel_cat)
        categories = query.all()

        sub_counts_by_cat = dict(
            self.db.query(db_mod.Subscriber.category, func.count(db_mod.Subscriber.id))
            .filter(db_mod.Subscriber.status == "accepted")
            .group_by(db_mod.Subscriber.category)
            .all()
        )

        cat_stats_query = self.db.query(
            db_mod.Subscriber.category,
            func.coalesce(func.sum(db_mod.Payment.amount), 0).label("generated_expected"),
            func.coalesce(func.sum(case((db_mod.Payment.due_date <= now_val, db_mod.Payment.amount), else_=0)), 0).label("due_so_far"),
            func.coalesce(func.sum(case((db_mod.Payment.is_paid == True, db_mod.Payment.amount), else_=0)), 0).label("collected"),
            func.coalesce(func.sum(case(((db_mod.Payment.is_paid == False) & (db_mod.Payment.due_date <= now_val), db_mod.Payment.amount), else_=0)), 0).label("arrears"),
        ).join(
            db_mod.Payment, db_mod.Subscriber.id == db_mod.Payment.subscriber_id, isouter=True
        ).filter(
            db_mod.Subscriber.status == "accepted"
        ).group_by(db_mod.Subscriber.category)

        if sel_cat:
            cat_stats_query = cat_stats_query.filter(db_mod.Subscriber.category == sel_cat)

        cat_stats_map = {row[0]: row for row in cat_stats_query.all()}

        rows = []
        for cat in categories:
            sub_count = int(sub_counts_by_cat.get(cat.name, 0))
            stats = cat_stats_map.get(cat.name)

            inst_amt = float(cat.amount or 0.0)
            max_inst = max(1, int(cat.max_installments or 1))
            max_cycles = max(1, int(cat.max_cycles or 1))
            cycle_amt = inst_amt * max_inst
            season_target = sub_count * cycle_amt * max_cycles

            generated_expected = float(stats.generated_expected) if stats else 0.0
            due_so_far = float(stats.due_so_far) if stats else 0.0
            collected = float(stats.collected) if stats else 0.0
            arrears = float(stats.arrears) if stats else 0.0

            if season_target < generated_expected:
                season_target = generated_expected

            season_remaining = max(0.0, season_target - collected)
            # نسبة التحصيل بالنسبة للمبالغ المستحقة حتى اليوم (لا تزيد عن 100%)
            ratio_due = min(100.0, (collected / due_so_far * 100.0)) if due_so_far > 0 else 0.0

            rows.append({
                "cat": cat,
                "name": cat.name,
                "inst_amt": inst_amt,
                "cycle_amt": cycle_amt,
                "max_inst": max_inst,
                "sub_count": sub_count,
                "season_target": season_target,
                "due_so_far": due_so_far,
                "collected": collected,
                "arrears": arrears,
                "season_remaining": season_remaining,
                "ratio_due": ratio_due,
            })
        return rows

    def refresh_capital_categories(self):
        rows = self._get_categories_financial_summary_rows()
        self.table_cap_categories.setUpdatesEnabled(False)
        try:
            self.table_cap_categories.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.table_cap_categories.setItem(i, 0, QTableWidgetItem(r["name"]))
                self.table_cap_categories.setItem(
                    i, 1, QTableWidgetItem(f"{r['inst_amt']:,.0f} (الدورة: {r['cycle_amt']:,.0f})")
                )
                self.table_cap_categories.setItem(i, 2, QTableWidgetItem(str(r["sub_count"])))
                self.table_cap_categories.setItem(i, 3, QTableWidgetItem(f"{r['season_target']:,.2f}"))
                self.table_cap_categories.setItem(i, 4, QTableWidgetItem(f"{r['due_so_far']:,.2f}"))

                col_item = QTableWidgetItem(f"{r['collected']:,.2f}")
                col_item.setForeground(QColor("#16a34a"))
                col_item.setFont(QFont("Tajawal", 9, QFont.Weight.Bold))
                self.table_cap_categories.setItem(i, 5, col_item)

                arr_item = QTableWidgetItem(f"{r['arrears']:,.2f}")
                if r["arrears"] > 0:
                    arr_item.setForeground(QColor("#ef4444"))
                    arr_item.setFont(QFont("Tajawal", 9, QFont.Weight.Bold))
                self.table_cap_categories.setItem(i, 6, arr_item)

                self.table_cap_categories.setItem(i, 7, QTableWidgetItem(f"{r['season_remaining']:,.2f}"))

                ratio = r["ratio_due"]
                pbar = QProgressBar()
                pbar.setRange(0, 100)
                pbar.setValue(int(round(ratio)))
                pbar.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pbar.setFormat(f"{ratio:.1f}%")

                if ratio >= 85:
                    pbar.setStyleSheet("QProgressBar { border-radius: 5px; text-align: center; color: white; background-color: #334155; } QProgressBar::chunk { background-color: #22c55e; border-radius: 5px; }")
                elif ratio >= 50:
                    pbar.setStyleSheet("QProgressBar { border-radius: 5px; text-align: center; color: white; background-color: #334155; } QProgressBar::chunk { background-color: #f59e0b; border-radius: 5px; }")
                else:
                    pbar.setStyleSheet("QProgressBar { border-radius: 5px; text-align: center; color: white; background-color: #334155; } QProgressBar::chunk { background-color: #ef4444; border-radius: 5px; }")

                self.table_cap_categories.setCellWidget(i, 8, pbar)
        finally:
            self.table_cap_categories.setUpdatesEnabled(True)

    def _build_defaulters_query(self):
        now_val = datetime.datetime.now()
        query = self.db.query(db_mod.Payment, db_mod.Subscriber).join(
            db_mod.Subscriber, db_mod.Subscriber.id == db_mod.Payment.subscriber_id
        ).filter(
            db_mod.Subscriber.status == "accepted",
            db_mod.Payment.is_paid == False,
            db_mod.Payment.due_date <= now_val,
        )
        sel_cat = self.cap_filter_cat.currentData() if hasattr(self, 'cap_filter_cat') else None
        if sel_cat:
            query = query.filter(db_mod.Subscriber.category == sel_cat)

        search_txt = self.cap_search_def.text().strip() if hasattr(self, 'cap_search_def') else ""
        if search_txt:
            query = query.filter(
                (db_mod.Subscriber.name.like(f"%{search_txt}%"))
                | (db_mod.Subscriber.phone.like(f"%{search_txt}%"))
                | (db_mod.Subscriber.subscriber_number.like(f"%{search_txt}%"))
            )
        return query

    def refresh_capital_defaulters(self):
        unpaid_data = self._build_defaulters_query().order_by(db_mod.Payment.due_date.asc()).all()
        self.table_cap_defaulters.setUpdatesEnabled(False)
        try:
            self.table_cap_defaulters.setRowCount(len(unpaid_data))
            for i, (p, sub) in enumerate(unpaid_data):
                name_item = QTableWidgetItem(f"{sub.name} ({sub.subscriber_number or '-'})")
                name_item.setData(Qt.ItemDataRole.UserRole, sub.id)

                date_cell = p.due_date.strftime("%Y-%m-%d") if p.due_date else "-"
                amt_item = QTableWidgetItem(f"{p.amount:,.2f}")
                amt_item.setForeground(QColor("#ef4444"))
                amt_item.setFont(QFont("Tajawal", 9, QFont.Weight.Bold))

                items = [
                    name_item,
                    QTableWidgetItem(sub.phone or "-"),
                    QTableWidgetItem(sub.category or "-"),
                    QTableWidgetItem(f"دورة {p.cycle_number} - قسط {p.installment_number}"),
                    QTableWidgetItem(date_cell),
                    amt_item,
                ]

                for col, item in enumerate(items):
                    self.table_cap_defaulters.setItem(i, col, item)

                btn_pay = QPushButton("سداد سريع")
                btn_pay.setStyleSheet(
                    "QPushButton { background-color: #ef4444; color: white; border-radius: 4px; padding: 4px 8px; font-weight: bold; } "
                    "QPushButton:hover { background-color: #dc2626; }"
                )
                btn_pay.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_pay.clicked.connect(lambda checked, pid=p.id: self.quick_pay_payment(pid))
                self.table_cap_defaulters.setCellWidget(i, 6, btn_pay)
        finally:
            self.table_cap_defaulters.setUpdatesEnabled(True)

    def quick_pay_payment(self, pid):
        p = self.db.get(db_mod.Payment, pid)
        if not p:
            return
        sub = self.db.get(db_mod.Subscriber, p.subscriber_id)
        sub_name = sub.name if sub else "-"
        msg = f"هل تريد تأكيد سداد الدورة {p.cycle_number} - القسط {p.installment_number} للمشترك {sub_name} بمبلغ {p.amount:,.2f} ر.ي؟"
        if ModernDialog(self, "تأكيد السداد السريع", msg, is_confirm=True).exec():
            try:
                p.is_paid = True
                p.paid_date = datetime.datetime.now()
                p.staff_id = self.logged_in_staff.id if self.logged_in_staff else None
                p.is_staff_settled = False

                staff_name = self.logged_in_staff.name if (self.logged_in_staff and self.logged_in_staff.name) else ""
                note_msg = "سداد سريع عبر لوحة التحكم"
                if staff_name:
                    note_msg += f" من موظف {staff_name}"
                default_notes = {"قسط يومي غير مسدد", "قسط مستحق عند التسجيل"}
                existing_custom = (p.note or "").strip()
                if existing_custom and not any(existing_custom.startswith(d) for d in default_notes):
                    p.note = f"{existing_custom} | {note_msg}"
                else:
                    p.note = note_msg

                self.db.commit()
                ModernDialog(self, "نجاح", "تم تسجيل السداد بنجاح").exec()

                self.refresh_capital_stats()
                self.refresh_current_capital_tab()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء السداد: {e}").exec()

    def quick_pay_all_defaulters(self):
        unpaid_data = self._build_defaulters_query().all()
        if not unpaid_data:
            ModernDialog(self, "معلومات", "لا توجد أقساط متأخرة مطابقة للبحث الحالي لسدادها.").exec()
            return

        total_amount = sum(float(p.amount or 0.0) for p, sub in unpaid_data)
        count = len(unpaid_data)

        msg = f"هل أنت متأكد من سداد جميع الأقساط المتأخرة المعروضة؟\nالعدد: {count} قسط\nالإجمالي: {total_amount:,.2f} ر.ي"
        if not ModernDialog(self, "تأكيد السداد الجماعي", msg, is_confirm=True).exec():
            return

        prog = BatchProgressDialog(
            self,
            "جاري سداد المتأخرات الجماعي",
            f"يتم الآن سداد {count} قسط متأخر...",
            count,
        )
        prog.show()
        QApplication.processEvents()

        try:
            now = datetime.datetime.now()
            staff_id = self.logged_in_staff.id if self.logged_in_staff else None
            staff_name = self.logged_in_staff.name if (self.logged_in_staff and self.logged_in_staff.name) else ""
            note_msg = "سداد جماعي للأقساط المتأخرة عبر لوحة التحكم"
            if staff_name:
                note_msg += f" من موظف {staff_name}"
            default_notes = {"قسط يومي غير مسدد", "قسط مستحق عند التسجيل"}

            step = max(1, count // 25)
            for idx, (p, sub) in enumerate(unpaid_data, start=1):
                p.is_paid = True
                p.paid_date = now
                p.staff_id = staff_id
                p.is_staff_settled = False

                existing_custom = (p.note or "").strip()
                if existing_custom and not any(existing_custom.startswith(d) for d in default_notes):
                    p.note = f"{existing_custom} | {note_msg}"
                else:
                    p.note = note_msg

                if idx % step == 0 or idx == count:
                    prog.update_progress(idx, f"تم معالجة {idx} من {count} قسط...")

            self.db.commit()
            prog.close()
            ModernDialog(self, "نجاح", f"تم تسجيل سداد جميع الأقساط المتأخرة ({count} قسط) بنجاح ✅").exec()

            self.refresh_capital_stats()
            self.refresh_current_capital_tab()
        except Exception as e:
            prog.close()
            self.db.rollback()
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء السداد الجماعي: {e}").exec()

    def _get_standing_rows(self):
        now_val = datetime.datetime.now()
        sel_cat = self.cap_filter_cat.currentData() if hasattr(self, 'cap_filter_cat') else None
        query = self.db.query(
            db_mod.Subscriber,
            func.coalesce(func.sum(case((db_mod.Payment.due_date <= now_val, db_mod.Payment.amount), else_=0)), 0).label('due_so_far'),
            func.coalesce(func.sum(case((db_mod.Payment.is_paid == True, db_mod.Payment.amount), else_=0)), 0).label('collected'),
            func.coalesce(func.sum(case(((db_mod.Payment.is_paid == False) & (db_mod.Payment.due_date <= now_val), db_mod.Payment.amount), else_=0)), 0).label('arrears'),
        ).outerjoin(
            db_mod.Payment, db_mod.Subscriber.id == db_mod.Payment.subscriber_id
        ).filter(
            db_mod.Subscriber.status == "accepted"
        ).group_by(db_mod.Subscriber.id)

        if sel_cat:
            query = query.filter(db_mod.Subscriber.category == sel_cat)

        search_txt = self.cap_search_standing.text().strip() if hasattr(self, 'cap_search_standing') else ""
        if search_txt:
            query = query.filter(
                (db_mod.Subscriber.name.like(f"%{search_txt}%"))
                | (db_mod.Subscriber.phone.like(f"%{search_txt}%"))
                | (db_mod.Subscriber.subscriber_number.like(f"%{search_txt}%"))
            )

        subs_data = query.all()
        all_subs_objs = [r[0] for r in subs_data]
        fin_map = db_mod.calculate_financial_status_batch(all_subs_objs, self.db) if all_subs_objs else {}
        return subs_data, fin_map

    def refresh_capital_standing(self):
        subs_data, fin_map = self._get_standing_rows()
        self.table_cap_standing.setUpdatesEnabled(False)
        try:
            self.table_cap_standing.setRowCount(len(subs_data))
            for i, (s, due_so_far, collected, arrears) in enumerate(subs_data):
                due_so_far = float(due_so_far or 0.0)
                collected = float(collected or 0.0)
                arrears = float(arrears or 0.0)

                name_item = QTableWidgetItem(s.name or "-")
                name_item.setData(Qt.ItemDataRole.UserRole, s.id)

                self.table_cap_standing.setItem(i, 0, name_item)
                self.table_cap_standing.setItem(i, 1, QTableWidgetItem(s.category or "-"))
                self.table_cap_standing.setItem(i, 2, QTableWidgetItem(s.subscriber_number or "-"))
                self.table_cap_standing.setItem(i, 3, QTableWidgetItem(f"{due_so_far:,.2f}"))

                col_item = QTableWidgetItem(f"{collected:,.2f}")
                col_item.setForeground(QColor("#16a34a"))
                self.table_cap_standing.setItem(i, 4, col_item)

                arr_item = QTableWidgetItem(f"{arrears:,.2f}")
                if arrears > 0:
                    arr_item.setForeground(QColor("#ef4444"))
                    arr_item.setFont(QFont("Tajawal", 9, QFont.Weight.Bold))
                self.table_cap_standing.setItem(i, 5, arr_item)

                fin_st = fin_map.get(s.id, "committed")
                if fin_st == "suspended":
                    st_txt, st_col = "موقوف ⚫", "#dc2626"
                elif fin_st == "late" or arrears > 0:
                    st_txt, st_col = "متأخر 🔴", "#ef4444"
                else:
                    st_txt, st_col = "ملتزم 🟢", "#16a34a"

                st_item = QTableWidgetItem(st_txt)
                st_item.setForeground(QColor(st_col))
                st_item.setFont(QFont("Tajawal", 9, QFont.Weight.Bold))
                self.table_cap_standing.setItem(i, 6, st_item)
        finally:
            self.table_cap_standing.setUpdatesEnabled(True)

    def export_standing_excel(self):
        try:
            subs_data, fin_map = self._get_standing_rows()
            if not subs_data:
                ModernDialog(self, "تنبيه", "لا توجد بيانات لتصديرها.").exec()
                return
            data = []
            for s, due_so_far, collected, arrears in subs_data:
                fin_st = fin_map.get(s.id, "committed")
                st_txt = "موقوف" if fin_st == "suspended" else ("متأخر" if (fin_st == "late" or (arrears or 0) > 0) else "ملتزم")
                data.append({
                    "اسم المشترك": s.name or "-",
                    "الفئة": s.category or "-",
                    "رقم الحساب": s.subscriber_number or "-",
                    "الهاتف": s.phone or "-",
                    "المستحق حتى اليوم (ر.ي)": float(due_so_far or 0.0),
                    "إجمالي المسدد (ر.ي)": float(collected or 0.0),
                    "المتأخرات المستحقة (ر.ي)": float(arrears or 0.0),
                    "الحالة المالية": st_txt,
                })
            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ المواقف المالية للمشتركين", "subscribers_financial_standing.xlsx", "Excel Files (*.xlsx)")
            if file_path:
                with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="المواقف المالية")
                    writer.sheets["المواقف المالية"].right_to_left()
                ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {e}").exec()

    def export_categories_financial_excel(self):
        try:
            rows = self._get_categories_financial_summary_rows()
            if not rows:
                ModernDialog(self, "تنبيه", "لا توجد بيانات فئات لتصديرها.").exec()
                return
            data = []
            for r in rows:
                data.append({
                    "اسم الفئة": r["name"],
                    "قيمة القسط (ر.ي)": r["inst_amt"],
                    "قيمة الدورة (ر.ي)": r["cycle_amt"],
                    "عدد المشتركين": r["sub_count"],
                    "رأس المال المستهدف للموسم": r["season_target"],
                    "المستحق حتى اليوم": r["due_so_far"],
                    "رأس المال المحصل": r["collected"],
                    "المتأخرات المستحقة": r["arrears"],
                    "المتبقي لنهاية الموسم": r["season_remaining"],
                    "نسبة تحصيل المستحق": f"{r['ratio_due']:.1f}%",
                })

            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير سيولة الفئات", "categories_financial_report.xlsx", "Excel Files (*.xlsx)")
            if file_path:
                with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="سيولة الفئات")
                    writer.sheets["سيولة الفئات"].right_to_left()
                ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {e}").exec()

    def export_defaulters_excel(self):
        try:
            unpaid_data = self._build_defaulters_query().order_by(db_mod.Payment.due_date.asc()).all()
            if not unpaid_data:
                ModernDialog(self, "تنبيه", "لا توجد أقساط متأخرة لتصديرها.").exec()
                return

            data = []
            for p, sub in unpaid_data:
                data.append({
                    "المشترك": sub.name if sub else "غير محدد",
                    "رقم الحساب": sub.subscriber_number if sub else "-",
                    "الهاتف": sub.phone if sub else "-",
                    "الفئة": sub.category if sub else "-",
                    "الدورة والقسط": f"دورة {p.cycle_number} - قسط {p.installment_number}",
                    "تاريخ الاستحقاق": (p.due_date.strftime("%Y-%m-%d") if p.due_date else "-"),
                    "المبلغ المستحق (ر.ي)": float(p.amount or 0.0),
                })

            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير المتأخرات", "unpaid_installments_report.xlsx", "Excel Files (*.xlsx)")
            if file_path:
                with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="المتأخرات")
                    writer.sheets["المتأخرات"].right_to_left()
                ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {e}").exec()

    def refresh_capital_expenses(self):
        for i in reversed(range(self.exp_summary_layout.count())):
            widget = self.exp_summary_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        sel_sub_cat = self.cap_filter_cat.currentData() if hasattr(self, 'cap_filter_cat') else None

        exp_sum_q = self.db.query(db_mod.Expense.category, func.coalesce(func.sum(db_mod.Expense.amount), 0))
        if sel_sub_cat:
            exp_sum_q = exp_sum_q.filter(db_mod.Expense.subscriber_category == sel_sub_cat)
        totals_by_cat = dict(exp_sum_q.group_by(db_mod.Expense.category).all())

        categories = ["سيرفرات وتقنية", "رسائل SMS", "رواتب وأجور", "تسويق وإعلانات", "أخرى"]
        row, col = 0, 0
        for cat in categories:
            total = float(totals_by_cat.get(cat, 0.0))

            card = QFrame()
            card.setObjectName("StatCard")
            vbox = QVBoxLayout(card)
            vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.setContentsMargins(10, 8, 10, 8)

            t_lbl = QLabel(cat)
            t_lbl.setObjectName("StatTitle")
            t_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
            t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(t_lbl)

            v_lbl = QLabel(f"{total:,.2f} ر.ي")
            v_lbl.setStyleSheet("color: #ec4899; font-weight: bold; font-size: 14px;")
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(v_lbl)

            self.exp_summary_layout.addWidget(card, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

        query = self.db.query(db_mod.Expense)
        if sel_sub_cat:
            query = query.filter(db_mod.Expense.subscriber_category == sel_sub_cat)

        search_txt = self.exp_search_input.text().strip()
        if search_txt:
            query = query.filter((db_mod.Expense.title.like(f"%{search_txt}%")) | (db_mod.Expense.note.like(f"%{search_txt}%")))

        sel_cat = self.exp_filter_cat.currentData()
        if sel_cat:
            query = query.filter(db_mod.Expense.category == sel_cat)

        expenses = query.order_by(db_mod.Expense.date.desc()).all()
        self.table_cap_expenses.setUpdatesEnabled(False)
        try:
            self.table_cap_expenses.setRowCount(len(expenses))
            for i, e in enumerate(expenses):
                self.table_cap_expenses.setItem(i, 0, QTableWidgetItem(e.title))
                self.table_cap_expenses.setItem(i, 1, QTableWidgetItem(f"{e.amount:,.2f}"))
                self.table_cap_expenses.setItem(i, 2, QTableWidgetItem(e.category or "-"))
                self.table_cap_expenses.setItem(i, 3, QTableWidgetItem(e.subscriber_category or "عامة"))
                self.table_cap_expenses.setItem(i, 4, QTableWidgetItem(e.date.strftime("%Y-%m-%d %H:%M") if e.date else "-"))
                self.table_cap_expenses.setItem(i, 5, QTableWidgetItem(e.note or "-"))

                btn_del = QPushButton("حذف")
                btn_del.setObjectName("DangerBtn")
                btn_del.setStyleSheet("padding: 3px 8px; font-size: 11px;")
                btn_del.clicked.connect(lambda checked, eid=e.id: self.delete_expense(eid))
                self.table_cap_expenses.setCellWidget(i, 6, btn_del)
        finally:
            self.table_cap_expenses.setUpdatesEnabled(True)

    def add_new_expense(self):
        title = self.exp_title_input.text().strip()
        amount_str = self.exp_amount_input.text().strip()
        category = self.exp_cat_combo.currentText()
        sub_category = self.exp_sub_cat_combo.currentData()
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
                subscriber_category=sub_category,
                note=note if note else None,
                date=datetime.datetime.now()
            )
            self.db.add(new_exp)
            self.db.commit()

            self.exp_title_input.clear()
            self.exp_amount_input.clear()
            self.exp_note_input.clear()

            ModernDialog(self, "نجاح", "تمت إضافة النفقة التشغيلية بنجاح").exec()

            self.refresh_capital_stats()
            self.refresh_capital_expenses()
        except Exception as err:
            self.db.rollback()
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء الإضافة: {err}").exec()

    def delete_expense(self, eid):
        exp = self.db.get(db_mod.Expense, eid)
        if not exp:
            return

        msg = f"هل تريد تأكيد حذف النفقة التشغيلية: {exp.title} بمبلغ {exp.amount:,.2f} ر.ي؟"
        if ModernDialog(self, "تأكيد الحذف", msg, is_confirm=True).exec():
            try:
                self.db.delete(exp)
                self.db.commit()
                ModernDialog(self, "نجاح", "تم حذف سجل النفقة بنجاح").exec()

                self.refresh_capital_stats()
                self.refresh_capital_expenses()
            except Exception as err:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء الحذف: {err}").exec()

    def export_expenses_excel(self):
        try:
            query = self.db.query(db_mod.Expense)
            sel_sub_cat = self.cap_filter_cat.currentData() if hasattr(self, 'cap_filter_cat') else None
            if sel_sub_cat:
                query = query.filter(db_mod.Expense.subscriber_category == sel_sub_cat)

            sel_cat = self.exp_filter_cat.currentData() if hasattr(self, 'exp_filter_cat') else None
            if sel_cat:
                query = query.filter(db_mod.Expense.category == sel_cat)

            search_txt = self.exp_search_input.text().strip()
            if search_txt:
                query = query.filter((db_mod.Expense.title.like(f"%{search_txt}%")) | (db_mod.Expense.note.like(f"%{search_txt}%")))

            expenses = query.order_by(db_mod.Expense.date.desc()).all()
            if not expenses:
                ModernDialog(self, "تنبيه", "لا توجد نفقات مطابقة لتصديرها.").exec()
                return

            data = []
            for e in expenses:
                data.append({
                    "البيان / الوصف": e.title,
                    "المبلغ (ر.ي)": e.amount,
                    "التصنيف": e.category or "-",
                    "الفئة المالية": e.subscriber_category or "عامة",
                    "التاريخ والوقت": (e.date.strftime("%Y-%m-%d %H:%M") if e.date else "-"),
                    "الملاحظات": e.note or "-"
                })

            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ كشف النفقات التشغيلية", "operational_expenses_report.xlsx", "Excel Files (*.xlsx)")
            if file_path:
                with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="النفقات التشغيلية")
                    writer.sheets["النفقات التشغيلية"].right_to_left()
                ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as err:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {err}").exec()

    def refresh_capital_winners(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all()

        query = self.db.query(db_mod.Winner)

        sel_cat = self.cap_filter_cat.currentData() if hasattr(self, 'cap_filter_cat') else None
        status_filter = self.cap_filter_winner_status.currentData() if hasattr(self, 'cap_filter_winner_status') else None

        if status_filter is not None:
            query = query.filter(db_mod.Winner.is_received == status_filter)

        winners = query.order_by(db_mod.Winner.draw_date.desc()).all()
        search_txt = self.cap_search_winners.text().strip().lower() if hasattr(self, 'cap_search_winners') else ""

        # جلب المشتركين والفئات دفعة واحدة لتجنب استعلامات N+1 البطيئة
        all_subs = self.db.query(db_mod.Subscriber).all()
        sub_by_num = {s.subscriber_number: s for s in all_subs if s.subscriber_number}
        s_nums = self.db.query(db_mod.SubscriberNumber).all()
        snum_map = {sn.number: sn.subscriber for sn in s_nums if sn.subscriber}
        cats_map = {c.name: c for c in self.db.query(db_mod.Category).all()}

        display_list = []
        for w in winners:
            sub = sub_by_num.get(w.subscriber_number) or snum_map.get(w.subscriber_number)
            sub_name = sub.name if sub else "مشترك غير معروف"
            sub_phone = sub.phone if sub else "-"
            sub_cat = sub.category if sub else "-"

            if sel_cat and sub_cat != sel_cat:
                continue

            if search_txt:
                match = (
                    (search_txt in sub_name.lower())
                    or (search_txt in sub_phone.lower())
                    or (search_txt in (w.subscriber_number or "").lower())
                )
                if not match:
                    continue

            cat_obj = cats_map.get(sub_cat)
            payout_amt = self._compute_default_winner_payout(w, sub, cat_obj)
            display_list.append((w, sub, sub_name, sub_phone, sub_cat, payout_amt))

        self.table_cap_winners.setUpdatesEnabled(False)
        try:
            self.table_cap_winners.setRowCount(len(display_list))
            for i, (w, sub, sub_name, sub_phone, sub_cat, payout_amt) in enumerate(display_list):
                name_item = QTableWidgetItem(f"{sub_name} ({w.subscriber_number or '-'})")
                if sub:
                    name_item.setData(Qt.ItemDataRole.UserRole, sub.id)

                self.table_cap_winners.setItem(i, 0, name_item)
                self.table_cap_winners.setItem(i, 1, QTableWidgetItem(sub_phone))
                self.table_cap_winners.setItem(i, 2, QTableWidgetItem(sub_cat))
                self.table_cap_winners.setItem(i, 3, QTableWidgetItem(w.draw_type or "سحب عام"))
                self.table_cap_winners.setItem(i, 4, QTableWidgetItem(str(w.cycle_number) if w.cycle_number else "-"))

                draw_date_str = w.draw_date.strftime("%Y-%m-%d %H:%M") if w.draw_date else "-"
                self.table_cap_winners.setItem(i, 5, QTableWidgetItem(draw_date_str))

                amt_txt = f"{payout_amt:,.2f}" if (w.is_received or payout_amt > 0) else "يحدد عند التسليم"
                self.table_cap_winners.setItem(i, 6, QTableWidgetItem(amt_txt))

                status_widget = QWidget()
                s_lay = QHBoxLayout(status_widget)
                s_lay.setContentsMargins(4, 2, 4, 2)
                s_lbl = QLabel()
                s_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if w.is_received:
                    s_lbl.setText("استلم (تم التسليم)")
                    s_lbl.setStyleSheet("background-color: #dcfce7; color: #15803d; font-weight: bold; border-radius: 4px; padding: 4px 8px;")
                else:
                    s_lbl.setText("لم يستلم بعد")
                    s_lbl.setStyleSheet("background-color: #fee2e2; color: #b91c1c; font-weight: bold; border-radius: 4px; padding: 4px 8px;")
                s_lay.addWidget(s_lbl)
                self.table_cap_winners.setCellWidget(i, 7, status_widget)

                recv_date_str = w.received_date.strftime("%Y-%m-%d %H:%M") if (w.is_received and w.received_date) else "-"
                self.table_cap_winners.setItem(i, 8, QTableWidgetItem(recv_date_str))

                btn_act = QPushButton()
                btn_act.setCursor(Qt.CursorShape.PointingHandCursor)
                if w.is_received:
                    btn_act.setText("إلغاء التسليم")
                    btn_act.setStyleSheet("QPushButton { background-color: #64748b; color: white; border-radius: 4px; padding: 4px 10px; font-weight: bold; } QPushButton:hover { background-color: #475569; }")
                else:
                    btn_act.setText("تأكيد التسليم (استلم)")
                    btn_act.setStyleSheet("QPushButton { background-color: #16a34a; color: white; border-radius: 4px; padding: 4px 10px; font-weight: bold; } QPushButton:hover { background-color: #15803d; }")

                btn_act.clicked.connect(
                    lambda checked, wid=w.id, cur_status=w.is_received, cur_amt=payout_amt: self.toggle_winner_payout_status(wid, cur_status, cur_amt)
                )
                self.table_cap_winners.setCellWidget(i, 9, btn_act)
        finally:
            self.table_cap_winners.setUpdatesEnabled(True)

    def toggle_winner_payout_status(self, wid, current_status, default_amount):
        w = self.db.get(db_mod.Winner, wid)
        if not w:
            return

        sub = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.subscriber_number == w.subscriber_number).first()
        sub_name = sub.name if sub else w.subscriber_number

        if not current_status:
            amt_dialog = QInputDialog(self)
            amt_dialog.setWindowTitle("تأكيد تسليم المبلغ للمشترك الفائز")
            amt_dialog.setLabelText(
                f"يرجى تأكيد المبلغ المستحق للمشترك ({sub_name}) - ({w.draw_type or ''}):\n"
                f"(سيتم خصم هذا المبلغ من رأس المال والسيولة النقدية)"
            )
            amt_dialog.setDoubleValue(default_amount if default_amount > 0 else 0.0)
            amt_dialog.setDoubleRange(0.0, 100000000.0)
            amt_dialog.setDoubleDecimals(2)

            if amt_dialog.exec():
                confirmed_amt = amt_dialog.doubleValue()
                try:
                    w.is_received = True
                    w.payout_amount = confirmed_amt
                    w.received_date = datetime.datetime.now()
                    self.db.commit()

                    ModernDialog(self, "نجاح", f"تم تسليم المبلغ ({confirmed_amt:,.2f} ر.ي) للمشترك {sub_name} بنجاح وخصمه من رأس المال.").exec()
                    self.refresh_capital_stats()
                    self.refresh_capital_winners()
                except Exception as e:
                    self.db.rollback()
                    ModernDialog(self, "خطأ", f"حدث خطأ أثناء تحديث حالة التسليم: {e}").exec()
        else:
            msg = f"هل تريد تأكيد إلغاء تسليم المبلغ للمشترك الفائز ({sub_name})؟\n(سيتم إعادة المبلغ إلى رأس المال)"
            if ModernDialog(self, "إلغاء التسليم", msg, is_confirm=True).exec():
                try:
                    w.is_received = False
                    w.received_date = None
                    self.db.commit()

                    ModernDialog(self, "نجاح", f"تم إلغاء حالة التسليم للمشترك {sub_name} وتعديل رأس المال.").exec()
                    self.refresh_capital_stats()
                    self.refresh_capital_winners()
                except Exception as e:
                    self.db.rollback()
                    ModernDialog(self, "خطأ", f"حدث خطأ أثناء إرجاع الحالة: {e}").exec()

    def export_capital_winners_excel(self):
        try:
            query = self.db.query(db_mod.Winner)
            status_filter = self.cap_filter_winner_status.currentData() if hasattr(self, 'cap_filter_winner_status') else None
            if status_filter is not None:
                query = query.filter(db_mod.Winner.is_received == status_filter)

            winners = query.order_by(db_mod.Winner.draw_date.desc()).all()
            sel_cat = self.cap_filter_cat.currentData() if hasattr(self, 'cap_filter_cat') else None
            search_txt = self.cap_search_winners.text().strip().lower() if hasattr(self, 'cap_search_winners') else ""

            all_subs = self.db.query(db_mod.Subscriber).all()
            sub_by_num = {s.subscriber_number: s for s in all_subs if s.subscriber_number}
            s_nums = self.db.query(db_mod.SubscriberNumber).all()
            snum_map = {sn.number: sn.subscriber for sn in s_nums if sn.subscriber}
            cats_map = {c.name: c for c in self.db.query(db_mod.Category).all()}

            data = []
            for w in winners:
                sub = sub_by_num.get(w.subscriber_number) or snum_map.get(w.subscriber_number)
                sub_name = sub.name if sub else "مشترك غير معروف"
                sub_phone = sub.phone if sub else "-"
                sub_cat = sub.category if sub else "-"

                if sel_cat and sub_cat != sel_cat:
                    continue

                if search_txt:
                    match = (
                        (search_txt in sub_name.lower())
                        or (search_txt in sub_phone.lower())
                        or (search_txt in (w.subscriber_number or "").lower())
                    )
                    if not match:
                        continue

                cat_obj = cats_map.get(sub_cat)
                payout_amt = self._compute_default_winner_payout(w, sub, cat_obj)

                data.append({
                    "اسم المشترك": sub_name,
                    "رقم الحساب": w.subscriber_number or "-",
                    "رقم الهاتف": sub_phone,
                    "الفئة": sub_cat,
                    "نوع القرعة": w.draw_type or "سحب عام",
                    "رقم الدورة": w.cycle_number or "-",
                    "تاريخ الفوز": (w.draw_date.strftime("%Y-%m-%d %H:%M") if w.draw_date else "-"),
                    "المبلغ المستحق (ر.ي)": payout_amt,
                    "حالة الاستلام": "استلم (تم التسليم)" if w.is_received else "لم يستلم بعد",
                    "تاريخ الاستلام": (w.received_date.strftime("%Y-%m-%d %H:%M") if (w.is_received and w.received_date) else "-"),
                })

            if not data:
                ModernDialog(self, "تنبيه", "لا توجد بيانات مستحقات فائزين مطابقة لتصديرها.").exec()
                return

            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير مستحقات الفائزين", "winners_payouts_report.xlsx", "Excel Files (*.xlsx)")
            if file_path:
                with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="مستحقات الفائزين")
                    writer.sheets["مستحقات الفائزين"].right_to_left()
                ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as err:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {err}").exec()
