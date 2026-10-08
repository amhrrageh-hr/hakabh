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

class CapitalMixin:
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
        t2_header.addWidget(QLabel("بحث:"))
        self.cap_search_def = QLineEdit()
        self.cap_search_def.setPlaceholderText("ابحث باسم المشترك أو الهاتف...")
        self.cap_search_def.textChanged.connect(self.refresh_capital_defaulters)
        t2_header.addWidget(self.cap_search_def, 1)
        
        btn_pay_all = QPushButton("سداد المتأخرات دفعة واحدة")
        btn_pay_all.setStyleSheet("background-color: #22c55e; color: white; border-radius: 4px; padding: 5px 15px; font-weight: bold;")
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
        self.exp_search_input.textChanged.connect(self.refresh_capital_expenses)
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
        self.table_cap_expenses.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_cap_expenses.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_cap_expenses.setMinimumHeight(250)
        t4_layout.addWidget(self.table_cap_expenses)
        
        self.capital_tabs.addTab(self.tab_cap_expenses, "النفقات التشغيلية")
        
        # Tab 5: Winner Payouts (مستحقات الفائزين بالقرعة)
        self.tab_cap_winners = QWidget()
        t5_layout = QVBoxLayout(self.tab_cap_winners)
        t5_layout.setContentsMargins(20, 20, 20, 20)
        t5_layout.setSpacing(20)
        
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
        self.cap_search_winners.textChanged.connect(self.refresh_capital_winners)
        t5_header.addWidget(self.cap_search_winners, 1)
        
        btn_win_excel = QPushButton("تصدير كشف مستحقات الفائزين")
        btn_win_excel.setObjectName("PrimaryBtn")
        btn_win_excel.clicked.connect(self.export_winners_excel)
        t5_header.addWidget(btn_win_excel)
        t5_layout.addLayout(t5_header)
        
        self.table_cap_winners = QTableWidget()
        self.table_cap_winners.setColumnCount(10)
        self.table_cap_winners.setHorizontalHeaderLabels([
            "اسم المشترك", "الهاتف", "الفئة", "نوع القرعة", "الدورة", 
            "تاريخ الفوز", "المبلغ المستحق (ر.ي)", "حالة الاستلام", "تاريخ الاستلام", "إجراء"
        ])
        self.table_cap_winners.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_cap_winners.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_cap_winners.setMinimumHeight(250)
        t5_layout.addWidget(self.table_cap_winners)
        
        self.capital_tabs.addTab(self.tab_cap_winners, "مستحقات الفائزين بالقرعة")
        
        page.setWidget(container)
        return page
    def show_capital_management(self):
        self.content_stack.setCurrentWidget(self.page_capital)
        self._update_nav_style("إدارة رأس المال")
        
        self.load_capital_category_filter()
        
        self.refresh_capital_stats()
        self.refresh_capital_categories()
        self.refresh_capital_defaulters()
        self.refresh_capital_standing()
        self.refresh_capital_expenses()
        self.refresh_capital_winners()

    def load_capital_category_filter(self):
        self.cap_filter_cat.blockSignals(True)
        self.cap_filter_cat.clear()
        self.cap_filter_cat.addItem("كل الفئات", None)
        self.exp_sub_cat_combo.clear()
        self.exp_sub_cat_combo.addItem("مصاريف عامة (الكل)", None)
        for cat in self.db.query(db_mod.Category).all():
            self.cap_filter_cat.addItem(cat.name, cat.name)
            self.exp_sub_cat_combo.addItem(cat.name, cat.name)
        self.cap_filter_cat.blockSignals(False)

    def refresh_capital_on_category_change(self):
        self.refresh_capital_stats()
        self.refresh_capital_categories()
        self.refresh_capital_defaulters()
        self.refresh_capital_standing()
        self.refresh_capital_winners()
    def sync_unpaid_installments(self):
        """تقوم هذه الدالة بإضافة أقساط غير مسددة تلقائياً للأيام التي مضت ولم يسدد فيها المشترك"""
        try:
            now_date = datetime.datetime.now().date()
            subscribers = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted").all()
            
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
                    # نبدأ دائماً من تاريخ بدء الفئة لضمان توليد ما فات المشترك من أقساط الهكبة
                    current_check = cat.start_date.date() if cat.start_date else now_date
                
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
        self.db.expire_all() # ضمان جلب أحدث مبالغ السداد من الموقع
        # Clear stats
        for i in reversed(range(self.capital_stats_layout.count())):
            widget = self.capital_stats_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
            
        # Queries
        # حساب رأس المال المتوقع بناءً على جميع السجلات المولدة للمشتركين المقبولين
        sel_cat = self.cap_filter_cat.currentData()

        expected_query = self.db.query(func.sum(db_mod.Payment.amount)).join(db_mod.Subscriber).filter(
            db_mod.Subscriber.status == "accepted"
        )
        collected_query = self.db.query(func.sum(db_mod.Payment.amount)).join(db_mod.Subscriber).filter(
            db_mod.Subscriber.status == "accepted",
            db_mod.Payment.is_paid == True
        )
        arrears_query = self.db.query(func.sum(db_mod.Payment.amount)).join(db_mod.Subscriber).filter(
            db_mod.Subscriber.status == "accepted",
            db_mod.Payment.is_paid == False, 
            db_mod.Payment.due_date < datetime.datetime.now()
        )

        if sel_cat:
            expected_query = expected_query.filter(db_mod.Subscriber.category == sel_cat)
            collected_query = collected_query.filter(db_mod.Subscriber.category == sel_cat)
            arrears_query = arrears_query.filter(db_mod.Subscriber.category == sel_cat)

        total_expected = expected_query.scalar() or 0
        total_collected = collected_query.scalar() or 0
        
        total_remaining = total_expected - total_collected
        total_arrears = arrears_query.scalar() or 0
        
        # تعديل حساب المصاريف ليعتمد على الفئة المختارة
        exp_query = self.db.query(func.sum(db_mod.Expense.amount))
        if sel_cat:
            exp_query = exp_query.filter(db_mod.Expense.subscriber_category == sel_cat)
        total_expenses = exp_query.scalar() or 0
        
        # حساب مستحقات الفائزين بالقرعة المسددة (الذين استلموا مبالغهم)
        winner_payouts_query = self.db.query(func.sum(db_mod.Winner.payout_amount)).filter(
            db_mod.Winner.is_received == True
        )
        if sel_cat:
            winner_payouts_query = winner_payouts_query.filter(
                db_mod.Winner.subscriber_number.in_(
                    self.db.query(db_mod.Subscriber.subscriber_number).filter(db_mod.Subscriber.category == sel_cat)
                )
            )
        total_winner_payouts = winner_payouts_query.scalar() or 0.0

        net_cash = total_collected - total_expenses - total_winner_payouts
        
        stats = [
            ("رأس المال المستهدف (الإجمالي)", f"{total_expected:,.2f} ر.ي", "#3b82f6"),
            ("المبالغ المحصلة (الإيرادات)", f"{total_collected:,.2f} ر.ي", "#2e7d32"),
            ("مستحقات الفائزين (المسددة)", f"{total_winner_payouts:,.2f} ر.ي", "#8b5cf6"),
            ("النفقات التشغيلية", f"{total_expenses:,.2f} ر.ي", "#ec4899"),
            ("الأقساط المتأخرة (المستحقة)", f"{total_arrears:,.2f} ر.ي", "#ef4444"),
            ("صافي السيولة النقدية المتبقية", f"{net_cash:,.2f} ر.ي", "#06b6d4" if net_cash >= 0 else "#ef4444")
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
        sel_cat = self.cap_filter_cat.currentData()
        query = self.db.query(db_mod.Category)
        if sel_cat:
            query = query.filter(db_mod.Category.name == sel_cat)
        categories = query.all()
        self.table_cap_categories.setRowCount(len(categories))
        
        for i, cat in enumerate(categories):
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
            
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(int(ratio))
            pbar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pbar.setFormat(f"{ratio:.1f}%")
            
            if ratio >= 80:
                pbar.setStyleSheet("QProgressBar { border-radius: 5px; text-align: center; color: white; background-color: #e2e8f0; } QProgressBar::chunk { background-color: #22c55e; border-radius: 5px; }")
            elif ratio >= 50:
                pbar.setStyleSheet("QProgressBar { border-radius: 5px; text-align: center; color: white; background-color: #e2e8f0; } QProgressBar::chunk { background-color: #f59e0b; border-radius: 5px; }")
            else:
                pbar.setStyleSheet("QProgressBar { border-radius: 5px; text-align: center; color: white; background-color: #e2e8f0; } QProgressBar::chunk { background-color: #ef4444; border-radius: 5px; }")
                
            self.table_cap_categories.setCellWidget(i, 6, pbar)

    def refresh_capital_defaulters(self):
        # Query unpaid payments
        query = self.db.query(db_mod.Payment, db_mod.Subscriber).join(db_mod.Subscriber).filter(
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
            
        unpaid_data = query.order_by(db_mod.Payment.due_date.asc()).all()
        self.table_cap_defaulters.setRowCount(len(unpaid_data))
        
        for i, (p, sub) in enumerate(unpaid_data):
            # تخزين معرف المشترك لتمكين النقر المزدوج
            name_item = QTableWidgetItem(sub.name)
            name_item.setData(Qt.ItemDataRole.UserRole, sub.id)
            
            date_cell = p.due_date.strftime("%Y-%m-%d") if p.due_date else "-"
            items = [
                name_item,
                QTableWidgetItem(sub.phone),
                QTableWidgetItem(sub.category or "-"),
                QTableWidgetItem(f"دورة {p.cycle_number} - قسط {p.installment_number}"),
                QTableWidgetItem(date_cell),
                QTableWidgetItem(f"{p.amount:,.2f}")
            ]
            
            # تلوين جميع صفوف جدول المتأخرات لتمييزها
            bg_color = QColor("#fff1f2")
            for col, item in enumerate(items):
                item.setBackground(bg_color)
                self.table_cap_defaulters.setItem(i, col, item)
            
            # Action Button
            btn_pay = QPushButton("سداد سريع")
            btn_pay.setStyleSheet("QPushButton { background-color: #ef4444; color: white; border-radius: 4px; padding: 5px; font-weight: bold; } QPushButton:hover { background-color: #dc2626; }")
            btn_pay.setCursor(Qt.CursorShape.PointingHandCursor)
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
                p.staff_id = self.logged_in_staff.id if self.logged_in_staff else None
                p.is_staff_settled = False
                
                # إضافة الملاحظة (استبدال الملاحظة التلقائية بالملاحظة الوصفية)
                staff_name = self.logged_in_staff.name if (self.logged_in_staff and self.logged_in_staff.name) else ""
                note_msg = "سداد سريع عبر لوحة التحكم"
                if staff_name:
                    note_msg += f" من موظف {staff_name}"
                # الاحتفاظ بأي ملاحظة مخصصة من المشرف وتجاهل الملاحظة التلقائية فقط
                default_notes = {"قسط يومي غير مسدد", "قسط مستحق عند التسجيل"}
                existing_custom = (p.note or "").strip()
                if existing_custom and not any(existing_custom.startswith(d) for d in default_notes):
                    p.note = f"{existing_custom} | {note_msg}"
                else:
                    p.note = note_msg
                
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

    def quick_pay_all_defaulters(self):
        # Query unpaid payments matching current filters
        query = self.db.query(db_mod.Payment, db_mod.Subscriber).join(db_mod.Subscriber).filter(
            db_mod.Payment.is_paid == False,
            db_mod.Payment.due_date < datetime.datetime.now())
        
        sel_cat = self.cap_filter_cat.currentData()
        if sel_cat:
            query = query.filter(db_mod.Subscriber.category == sel_cat)
            
        search_txt = self.cap_search_def.text().strip()
        if search_txt:
            query = query.filter((db_mod.Subscriber.name.like(f"%{search_txt}%")) | (db_mod.Subscriber.phone.like(f"%{search_txt}%")))
            
        unpaid_data = query.all()
        
        if not unpaid_data:
            ModernDialog(self, "معلومات", "لا توجد أقساط متأخرة مطابقة للبحث الحالي لسدادها.").exec()
            return
            
        total_amount = sum(p.amount for p, sub in unpaid_data)
        count = len(unpaid_data)
        
        msg = f"هل أنت متأكد من سداد جميع الأقساط المتأخرة المعروضة؟\nالعدد: {count} قسط\nالإجمالي: {total_amount:,.2f} ر.ي"
        if ModernDialog(self, "تأكيد السداد الجماعي", msg, is_confirm=True).exec():
            try:
                now = datetime.datetime.now()
                staff_id = self.logged_in_staff.id if self.logged_in_staff else None
                staff_name = self.logged_in_staff.name if (self.logged_in_staff and self.logged_in_staff.name) else ""
                
                for p, sub in unpaid_data:
                    p.is_paid = True
                    p.paid_date = now
                    p.staff_id = staff_id
                    p.is_staff_settled = False
                    
                    # إضافة الملاحظة (استبدال الملاحظة التلقائية بالملاحظة الوصفية)
                    note_msg = "سداد جماعي للأقساط المتأخرة عبر لوحة التحكم"
                    if staff_name:
                        note_msg += f" من موظف {staff_name}"
                    # الاحتفاظ بأي ملاحظة مخصصة من المشرف وتجاهل الملاحظة التلقائية فقط
                    default_notes = {"قسط يومي غير مسدد", "قسط مستحق عند التسجيل"}
                    existing_custom = (p.note or "").strip()
                    if existing_custom and not any(existing_custom.startswith(d) for d in default_notes):
                        p.note = f"{existing_custom} | {note_msg}"
                    else:
                        p.note = note_msg
                    
                self.db.commit()
                ModernDialog(self, "نجاح", "تم تسجيل سداد جميع الأقساط المتأخرة بنجاح").exec()
                
                # Refresh tables
                self.refresh_capital_stats()
                self.refresh_capital_categories()
                self.refresh_capital_defaulters()
                self.refresh_capital_standing()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء السداد الجماعي: {e}").exec()

    def refresh_capital_standing(self):
        # تحسين: استعلام واحد يجلب المشتركين مع مجاميعهم المالية دفعة واحدة
        sel_cat = self.cap_filter_cat.currentData()
        query = self.db.query(
            db_mod.Subscriber,
            func.sum(db_mod.Payment.amount).label('expected'),
            func.sum(case((db_mod.Payment.is_paid == True, db_mod.Payment.amount), else_=0)).label('collected'),
            func.sum(case((db_mod.Payment.is_paid == False, db_mod.Payment.amount), else_=0)).label('remaining')
        ).outerjoin(db_mod.Payment).group_by(db_mod.Subscriber.id)
        if sel_cat:
            query = query.filter(db_mod.Subscriber.category == sel_cat)
        
        search_txt = self.cap_search_standing.text().strip()
        if search_txt:
            query = query.filter((db_mod.Subscriber.name.like(f"%{search_txt}%")) | (db_mod.Subscriber.phone.like(f"%{search_txt}%")))
            
        subs_data = query.all()
        self.table_cap_standing.setRowCount(len(subs_data))
        
        for i, (s, expected, collected, remaining) in enumerate(subs_data):
            expected = expected or 0
            collected = collected or 0
            remaining = remaining or 0

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
            sel_cat = self.cap_filter_cat.currentData()
            query = self.db.query(db_mod.Category)
            if sel_cat:
                query = query.filter(db_mod.Category.name == sel_cat)
            categories = query.all()
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
            # توحيد المنطق مع الجدول المرئي (فقط المتأخرات الفائتة)
            query = self.db.query(db_mod.Payment).join(db_mod.Subscriber).filter(
                db_mod.Payment.is_paid == False,
                db_mod.Payment.due_date < datetime.datetime.now()
            )
            
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
                    "تاريخ الاستحقاق": (p.due_date.strftime("%Y-%m-%d") if p.due_date else "-"),
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
        # Refresh summary
        for i in reversed(range(self.exp_summary_layout.count())):
            widget = self.exp_summary_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        
        categories = ["سيرفرات وتقنية", "رسائل SMS", "رواتب وأجور", "تسويق وإعلانات", "أخرى"]
        row, col = 0, 0
        for cat in categories:
            total = self.db.query(func.sum(db_mod.Expense.amount)).filter(db_mod.Expense.category == cat).scalar() or 0
            
            card = QFrame()
            card.setObjectName("StatCard")
            card.setStyleSheet("background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; padding: 5px;")
            vbox = QVBoxLayout(card)
            vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.setContentsMargins(5, 5, 5, 5)
            
            t_lbl = QLabel(cat)
            t_lbl.setStyleSheet("color: #475569; font-weight: bold; font-size: 12px;")
            t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(t_lbl)
            
            v_lbl = QLabel(f"{total:,.2f} ر.ي")
            v_lbl.setStyleSheet("color: #0f172a; font-weight: bold; font-size: 13px;")
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(v_lbl)
            
            self.exp_summary_layout.addWidget(card, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

        query = self.db.query(db_mod.Expense)
        
        search_txt = self.exp_search_input.text().strip()
        if search_txt:
            query = query.filter((db_mod.Expense.title.like(f"%{search_txt}%")) | (db_mod.Expense.note.like(f"%{search_txt}%")))
            
        sel_cat = self.exp_filter_cat.currentData()
        if sel_cat:
            query = query.filter(db_mod.Expense.category == sel_cat)
            
        expenses = query.order_by(db_mod.Expense.date.desc()).all()
        self.table_cap_expenses.setRowCount(len(expenses))
        
        for i, e in enumerate(expenses):
            self.table_cap_expenses.setItem(i, 0, QTableWidgetItem(e.title))
            self.table_cap_expenses.setItem(i, 1, QTableWidgetItem(f"{e.amount:,.2f}"))
            self.table_cap_expenses.setItem(i, 2, QTableWidgetItem(e.category or "-"))
            self.table_cap_expenses.setItem(i, 3, QTableWidgetItem(e.subscriber_category or "عامة"))
            self.table_cap_expenses.setItem(i, 4, QTableWidgetItem(e.date.strftime("%Y-%m-%d %H:%M")))
            self.table_cap_expenses.setItem(i, 5, QTableWidgetItem(e.note or "-"))
            
            # Delete Button
            btn_del = QPushButton("حذف")
            btn_del.setObjectName("DangerBtn")
            btn_del.setStyleSheet("padding: 3px 8px; font-size: 11px;")
            btn_del.clicked.connect(lambda checked, eid=e.id: self.delete_expense(eid))
            self.table_cap_expenses.setCellWidget(i, 6, btn_del)
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
                    "المبلغ (ر.ي)": e.amount,
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
        
        display_list = []
        for w in winners:
            sub = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.subscriber_number == w.subscriber_number).first()
            if not sub:
                s_num = self.db.query(db_mod.SubscriberNumber).filter(db_mod.SubscriberNumber.number == w.subscriber_number).first()
                if s_num and s_num.subscriber:
                    sub = s_num.subscriber
            
            sub_name = sub.name if sub else "مشترك غير معروف"
            sub_phone = sub.phone if sub else "-"
            sub_cat = sub.category if sub else "-"
            
            if sel_cat and sub_cat != sel_cat:
                continue
                
            if search_txt:
                match = (search_txt in sub_name.lower()) or (search_txt in sub_phone.lower()) or (search_txt in (w.subscriber_number or "").lower())
                if not match:
                    continue
                    
            payout_amt = w.payout_amount or 0.0
            if payout_amt == 0.0 and sub:
                cat_obj = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
                if cat_obj:
                    payout_amt = cat_obj.prize_amount if (cat_obj.prize_amount and cat_obj.prize_amount > 0) else (cat_obj.amount * cat_obj.max_installments)
            
            display_list.append((w, sub, sub_name, sub_phone, sub_cat, payout_amt))
            
        self.table_cap_winners.setRowCount(len(display_list))
        
        for i, (w, sub, sub_name, sub_phone, sub_cat, payout_amt) in enumerate(display_list):
            name_item = QTableWidgetItem(sub_name)
            if sub:
                name_item.setData(Qt.ItemDataRole.UserRole, sub.id)
                
            self.table_cap_winners.setItem(i, 0, name_item)
            self.table_cap_winners.setItem(i, 1, QTableWidgetItem(sub_phone))
            self.table_cap_winners.setItem(i, 2, QTableWidgetItem(sub_cat))
            self.table_cap_winners.setItem(i, 3, QTableWidgetItem(w.draw_type or "سحب عام"))
            self.table_cap_winners.setItem(i, 4, QTableWidgetItem(str(w.cycle_number) if w.cycle_number else "1"))
            
            draw_date_str = w.draw_date.strftime("%Y-%m-%d %H:%M") if w.draw_date else "-"
            self.table_cap_winners.setItem(i, 5, QTableWidgetItem(draw_date_str))
            
            self.table_cap_winners.setItem(i, 6, QTableWidgetItem(f"{payout_amt:,.2f}"))
            
            # Status Widget
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
            
            # Action Button
            btn_act = QPushButton()
            btn_act.setCursor(Qt.CursorShape.PointingHandCursor)
            if w.is_received:
                btn_act.setText("إلغاء التسليم")
                btn_act.setStyleSheet("QPushButton { background-color: #64748b; color: white; border-radius: 4px; padding: 4px 10px; font-weight: bold; } QPushButton:hover { background-color: #475569; }")
            else:
                btn_act.setText("تأكيد التسليم (استلم)")
                btn_act.setStyleSheet("QPushButton { background-color: #16a34a; color: white; border-radius: 4px; padding: 4px 10px; font-weight: bold; } QPushButton:hover { background-color: #15803d; }")
            
            btn_act.clicked.connect(lambda checked, wid=w.id, cur_status=w.is_received, cur_amt=payout_amt: self.toggle_winner_payout_status(wid, cur_status, cur_amt))
            self.table_cap_winners.setCellWidget(i, 9, btn_act)

    def toggle_winner_payout_status(self, wid, current_status, default_amount):
        w = self.db.get(db_mod.Winner, wid)
        if not w: return
        
        sub = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.subscriber_number == w.subscriber_number).first()
        sub_name = sub.name if sub else w.subscriber_number
        
        if not current_status:
            amt_dialog = QInputDialog(self)
            amt_dialog.setWindowTitle("تأكيد تسليم المبلغ للمشترك الفائز")
            amt_dialog.setLabelText(f"يرجى تأكيد المبلغ المستحق للمشترك ({sub_name}):\n(سيتم خصم هذا المبلغ من رأس المال والسيولة النقدية)")
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

    def export_winners_excel(self):
        try:
            query = self.db.query(db_mod.Winner)
            status_filter = self.cap_filter_winner_status.currentData() if hasattr(self, 'cap_filter_winner_status') else None
            if status_filter is not None:
                query = query.filter(db_mod.Winner.is_received == status_filter)
                
            winners = query.order_by(db_mod.Winner.draw_date.desc()).all()
            sel_cat = self.cap_filter_cat.currentData() if hasattr(self, 'cap_filter_cat') else None
            search_txt = self.cap_search_winners.text().strip().lower() if hasattr(self, 'cap_search_winners') else ""
            
            data = []
            for w in winners:
                sub = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.subscriber_number == w.subscriber_number).first()
                if not sub:
                    s_num = self.db.query(db_mod.SubscriberNumber).filter(db_mod.SubscriberNumber.number == w.subscriber_number).first()
                    if s_num and s_num.subscriber:
                        sub = s_num.subscriber
                
                sub_name = sub.name if sub else "مشترك غير معروف"
                sub_phone = sub.phone if sub else "-"
                sub_cat = sub.category if sub else "-"
                
                if sel_cat and sub_cat != sel_cat:
                    continue
                    
                if search_txt:
                    match = (search_txt in sub_name.lower()) or (search_txt in sub_phone.lower()) or (search_txt in (w.subscriber_number or "").lower())
                    if not match:
                        continue
                        
                payout_amt = w.payout_amount or 0.0
                if payout_amt == 0.0 and sub:
                    cat_obj = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
                    if cat_obj:
                        payout_amt = cat_obj.prize_amount if (cat_obj.prize_amount and cat_obj.prize_amount > 0) else (cat_obj.amount * cat_obj.max_installments)
                        
                data.append({
                    "اسم المشترك": sub_name,
                    "رقم الهاتف": sub_phone,
                    "الفئة": sub_cat,
                    "نوع القرعة": w.draw_type or "سحب عام",
                    "رقم الدورة": w.cycle_number or 1,
                    "تاريخ الفوز": (w.draw_date.strftime("%Y-%m-%d %H:%M") if w.draw_date else "-"),
                    "المبلغ المستحق (ر.ي)": payout_amt,
                    "حالة الاستلام": "استلم (تم التسليم)" if w.is_received else "لم يستلم بعد",
                    "تاريخ الاستلام": (w.received_date.strftime("%Y-%m-%d %H:%M") if (w.is_received and w.received_date) else "-")
                })
                
            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير مستحقات الفائزين", "winners_payouts_report.xlsx", "Excel Files (*.xlsx)")
            if file_path:
                df.to_excel(file_path, index=False)
                ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as err:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {err}").exec()
