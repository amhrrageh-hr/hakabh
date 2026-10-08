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

class DrawMixin:
    def show_draw_management(self): 
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all() # ضمان مزامنة البيانات قبل عرض حالة السحب
        self.content_stack.setCurrentWidget(self.page_draw)
        self._update_nav_style("إدارة القرعة")
        self.refresh_draw_categories_filter()
        self.load_recent_winners()
        self.load_draw_excluded()
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
        
        # Get theme configuration
        try:
            theme_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "admin_theme").first()
            theme = theme_setting.value if theme_setting else "dark"
        except Exception:
            theme = "dark"
        is_dark = (theme == "dark")
        title_green = "color: #4ade80;" if is_dark else "color: #1b5e20;"
        lbl_muted = "color: #94a3b8;" if is_dark else "color: #64748b;"
        
        # Statistics Section
        stats_frame = QFrame(); stats_frame.setObjectName("StatCard")
        self.draw_stats_layout = QVBoxLayout(stats_frame); self.draw_stats_layout.setSpacing(10)
        stats_title = QLabel("إحصائيات التأهل للسحب")
        stats_title.setObjectName("SectionTitle")
        stats_title.setStyleSheet(f"font-size: 16px; {title_green}")
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
            d_lbl = QLabel(desc); d_lbl.setWordWrap(True); d_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); d_lbl.setStyleSheet(f"{lbl_muted} font-size: 13px;")
            
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
        
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)
        filter_layout.addWidget(QLabel("تصفية حسب الجائزة:"))
        self.combo_draw_filter = QComboBox()
        self.combo_draw_filter.addItems(["الكل", "القرعة الاسبوعية", "الجائزة التحفيزية", "الجائزة الكبرى"])
        self.combo_draw_filter.currentTextChanged.connect(self.load_recent_winners)
        filter_layout.addWidget(self.combo_draw_filter)
        
        filter_layout.addWidget(QLabel("الفئة المالية:"))
        self.combo_draw_cat_filter = QComboBox()
        self.combo_draw_cat_filter.addItem("كل الفئات", None)
        self.combo_draw_cat_filter.currentIndexChanged.connect(self.load_recent_winners)
        filter_layout.addWidget(self.combo_draw_cat_filter)

        filter_layout.addWidget(QLabel("بحث سريع:"))
        self.draw_winners_search = QLineEdit()
        self.draw_winners_search.setPlaceholderText("ابحث باسم المشترك، رقم الحساب، أو الهاتف...")
        self.draw_winners_search.textChanged.connect(self.load_recent_winners)
        filter_layout.addWidget(self.draw_winners_search)
        
        filter_layout.addStretch()
        
        btn_win_excel = QPushButton("تصدير Excel رسمياً")
        btn_win_excel.setObjectName("PrimaryBtn")
        btn_win_excel.clicked.connect(self.export_winners_excel)
        filter_layout.addWidget(btn_win_excel)
        
        lay2.addLayout(filter_layout)
        
        winners_card = QFrame(); winners_card.setObjectName("StatCard"); win_layout = QVBoxLayout(winners_card); win_layout.setContentsMargins(10, 10, 10, 10)
        
        self.table_recent_winners = QTableWidget()
        self.table_recent_winners.setColumnCount(8)
        self.table_recent_winners.setHorizontalHeaderLabels([
            "اسم المشترك", "رقم الحساب / المشترك", "الفئة المالية", "رقم الهاتف", "رقم الدورة", "نوع الجائزة", "تاريخ السحب", "حالة الاستلام"
        ])
        self.table_recent_winners.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_recent_winners.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_recent_winners.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_recent_winners.customContextMenuRequested.connect(self.show_winner_context_menu)
        win_layout.addWidget(self.table_recent_winners)
        
        lay2.addWidget(winners_card)
        self.draw_tabs.addTab(tab2, "سجل الفائزين")

        # --- TAB 3: Excluded from Draw ---
        tab_ex = QWidget(); lay_ex = QVBoxLayout(tab_ex); lay_ex.setContentsMargins(20, 20, 20, 20)
        
        ex_filter_layout = QHBoxLayout()
        ex_filter_layout.setSpacing(12)
        
        ex_filter_layout.addWidget(QLabel("الفئة المالية:"))
        self.combo_draw_ex_cat_filter = QComboBox()
        self.combo_draw_ex_cat_filter.addItem("كل الفئات", None)
        self.combo_draw_ex_cat_filter.currentIndexChanged.connect(self.load_draw_excluded)
        ex_filter_layout.addWidget(self.combo_draw_ex_cat_filter)

        ex_filter_layout.addWidget(QLabel("بحث سريع:"))
        self.draw_ex_search = QLineEdit()
        self.draw_ex_search.setPlaceholderText("ابحث باسم المشترك، رقم الحساب، أو الهاتف...")
        self.draw_ex_search.textChanged.connect(self.load_draw_excluded)
        ex_filter_layout.addWidget(self.draw_ex_search)
        
        ex_filter_layout.addStretch()
        
        btn_ex_excel = QPushButton("تصدير المستبعدين Excel")
        btn_ex_excel.setObjectName("PrimaryBtn")
        btn_ex_excel.clicked.connect(self.export_draw_excluded_excel)
        ex_filter_layout.addWidget(btn_ex_excel)
        
        lay_ex.addLayout(ex_filter_layout)
        
        ex_card = QFrame(); ex_card.setObjectName("StatCard"); ex_card_lay = QVBoxLayout(ex_card); ex_card_lay.setContentsMargins(10, 10, 10, 10)
        
        self.table_draw_excluded = QTableWidget()
        self.table_draw_excluded.setColumnCount(7)
        self.table_draw_excluded.setHorizontalHeaderLabels([
            "اسم المشترك", "رقم الحساب", "الفئة المالية", "رقم الهاتف", "سبب الاستبعاد / عدم التأهل", "حالة الانضباط", "إجراء"
        ])
        self.table_draw_excluded.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_draw_excluded.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        ex_card_lay.addWidget(self.table_draw_excluded)
        
        lay_ex.addWidget(ex_card)
        self.draw_tabs.addTab(tab_ex, "🚫 المستبعدين من السحب")
        
        # --- TAB 4: Draw Settings ---
        tab3 = QScrollArea(); tab3.setWidgetResizable(True)
        con3 = QWidget(); lay3 = QVBoxLayout(con3); lay3.setContentsMargins(20, 20, 20, 20); lay3.setSpacing(25)
        
        # --- Grand Prize Settings ---
        settings_frame = QFrame(); settings_frame.setObjectName("StatCard")
        set_lay = QVBoxLayout(settings_frame); set_lay.setSpacing(15)
        
        set_title_color = "color: #f59e0b;" if is_dark else "color: #b45309;"
        set_title = QLabel("إعدادات الجائزة الكبرى")
        set_title.setObjectName("SectionTitle")
        set_title.setStyleSheet(f"font-size: 16px; {set_title_color}")
        set_lay.addWidget(set_title)
        
        form_layout = QFormLayout()
        
        self.dt_start = QDateEdit()
        self.dt_start.setCalendarPopup(True)
        self.dt_start.setDisplayFormat("yyyy-MM-dd")
        
        self.dt_end = QDateEdit()
        self.dt_end.setCalendarPopup(True)
        self.dt_end.setDisplayFormat("yyyy-MM-dd")
        
        self.spin_winners = QSpinBox()
        self.spin_winners.setMinimum(1)
        self.spin_winners.setMaximum(1000)
        
        form_layout.addRow("من تاريخ:", self.dt_start)
        form_layout.addRow("إلى تاريخ:", self.dt_end)
        form_layout.addRow("عدد الفائزين:", self.spin_winners)
        
        set_lay.addLayout(form_layout)
        
        btn_save = QPushButton("حفظ الإعدادات")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.clicked.connect(self.save_draw_settings)
        set_lay.addWidget(btn_save)
        
        lay3.addWidget(settings_frame)

        # --- Incentive Prize Eligibility Settings ---
        incentive_frame = QFrame(); incentive_frame.setObjectName("StatCard")
        inc_lay = QVBoxLayout(incentive_frame); inc_lay.setSpacing(15)

        inc_title_color = "color: #3b82f6;" if is_dark else "color: #1d4ed8;"
        inc_title = QLabel("⚙️  إعدادات المؤهلين في الجائزة التحفيزية")
        inc_title.setObjectName("SectionTitle")
        inc_title.setStyleSheet(f"font-size: 16px; {inc_title_color}")
        inc_lay.addWidget(inc_title)

        inc_desc = QLabel(
            "حدد عدد الأقساط المتأخرة المسموح بها للمشترك كي يبقى مؤهلاً للجائزة التحفيزية."
            "\n(اختر خياراً واحداً أو أكثر — سيكون المشترك مؤهلاً إذا انطبق عليه أيٌّ من الخيارات المحددة)"
        )
        inc_desc.setWordWrap(True)
        inc_desc.setStyleSheet(f"font-size: 12px; {lbl_muted}")
        inc_lay.addWidget(inc_desc)

        self.chk_late_1 = QCheckBox("إذا تأخر المشترك عن سداد  1  قسط")
        self.chk_late_2 = QCheckBox("إذا تأخر المشترك عن سداد  2  قسط")
        self.chk_late_3 = QCheckBox("إذا تأخر المشترك عن سداد  3  أقساط")

        chk_style = "font-size: 14px; padding: 6px 0px;"
        self.chk_late_1.setStyleSheet(chk_style)
        self.chk_late_2.setStyleSheet(chk_style)
        self.chk_late_3.setStyleSheet(chk_style)

        inc_lay.addWidget(self.chk_late_1)
        inc_lay.addWidget(self.chk_late_2)
        inc_lay.addWidget(self.chk_late_3)

        btn_save_inc = QPushButton("حفظ إعدادات التحفيزية")
        btn_save_inc.setObjectName("PrimaryBtn")
        btn_save_inc.clicked.connect(self.save_incentive_settings)
        inc_lay.addWidget(btn_save_inc)

        lay3.addWidget(incentive_frame)
        lay3.addStretch()
        self.draw_tabs.addTab(tab3, "إعداد القرعات")
        
        self.load_draw_settings()
        
        layout.addWidget(self.draw_tabs)
        return page

    def load_draw_settings(self):
        try:
            start_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_start_date").first()
            end_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_end_date").first()
            count_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_winners_count").first()
            
            if start_setting:
                dt = QDate.fromString(start_setting.value, "yyyy-MM-dd")
                if dt.isValid(): self.dt_start.setDate(dt)
            else:
                self.dt_start.setDate(QDate.currentDate())
                
            if end_setting:
                dt = QDate.fromString(end_setting.value, "yyyy-MM-dd")
                if dt.isValid(): self.dt_end.setDate(dt)
            else:
                self.dt_end.setDate(QDate.currentDate().addDays(30))
                
            if count_setting and count_setting.value.isdigit():
                self.spin_winners.setValue(int(count_setting.value))
            else:
                self.spin_winners.setValue(1)

            # Load incentive late-payment settings
            late1 = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "incentive_allow_late_1").first()
            late2 = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "incentive_allow_late_2").first()
            late3 = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "incentive_allow_late_3").first()
            self.chk_late_1.setChecked(late1.value == "1" if late1 else False)
            self.chk_late_2.setChecked(late2.value == "1" if late2 else False)
            self.chk_late_3.setChecked(late3.value == "1" if late3 else False)
        except Exception as e:
            print(f"Error loading draw settings: {e}")

    def save_draw_settings(self):
        try:
            start_val = self.dt_start.date().toString("yyyy-MM-dd")
            end_val = self.dt_end.date().toString("yyyy-MM-dd")
            count_val = str(self.spin_winners.value())
            
            settings = {
                "grand_prize_start_date": start_val,
                "grand_prize_end_date": end_val,
                "grand_prize_winners_count": count_val
            }
            
            for key, val in settings.items():
                setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
                if setting:
                    setting.value = val
                else:
                    self.db.add(db_mod.Setting(key=key, value=val))
            
            self.db.commit()
            ModernDialog(self, "نجاح", "تم حفظ إعدادات القرعة بنجاح.").exec()
        except Exception as e:
            self.db.rollback()
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء الحفظ: {e}").exec()

    def save_incentive_settings(self):
        """حفظ إعدادات التأخر المسموح به في الجائزة التحفيزية."""
        try:
            incentive_settings = {
                "incentive_allow_late_1": "1" if self.chk_late_1.isChecked() else "0",
                "incentive_allow_late_2": "1" if self.chk_late_2.isChecked() else "0",
                "incentive_allow_late_3": "1" if self.chk_late_3.isChecked() else "0",
            }
            for key, val in incentive_settings.items():
                setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
                if setting:
                    setting.value = val
                else:
                    self.db.add(db_mod.Setting(key=key, value=val))
            self.db.commit()
            ModernDialog(self, "نجاح", "تم حفظ إعدادات الجائزة التحفيزية بنجاح.").exec()
        except Exception as e:
            self.db.rollback()
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء الحفظ: {e}").exec()

    def _get_incentive_max_late(self):
        """إرجاع الحد الأقصى للأقساط المتأخرة المسموح بها للجائزة التحفيزية حسب الإعدادات."""
        try:
            late3 = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "incentive_allow_late_3").first()
            late2 = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "incentive_allow_late_2").first()
            late1 = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "incentive_allow_late_1").first()
            if late3 and late3.value == "1":
                return 3
            if late2 and late2.value == "1":
                return 2
            if late1 and late1.value == "1":
                return 1
        except Exception:
            pass
        return 0  # لا يُسمح بأي تأخر (الإعداد الافتراضي)

    def _get_category_stats(self, cat, target_cycle=None):
        today = datetime.datetime.now()
        subs_in_cat = self.db.query(db_mod.Subscriber).filter(
            db_mod.Subscriber.category == cat.name,
            db_mod.Subscriber.status == "accepted"
        ).all()
        
        completed_cycle_count = 0
        incentive_count = 0
        
        for sub in subs_in_cat:
            # التحقق من الانضباط المالي للمشترك
            fin_status = db_mod.calculate_financial_status(sub, self.db)
            if fin_status in ["late", "suspended"]:
                continue

            if target_cycle and target_cycle != "auto" and isinstance(target_cycle, int):
                sub_current_cycle = target_cycle
            else:
                active_sub_p = self.db.query(db_mod.Payment).filter(
                    db_mod.Payment.subscriber_id == sub.id,
                    db_mod.Payment.due_date <= today
                ).order_by(db_mod.Payment.due_date.desc()).first()
                sub_current_cycle = active_sub_p.cycle_number if active_sub_p else 1

            payments = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == sub.id, 
                db_mod.Payment.cycle_number == sub_current_cycle
            ).all()
            if not payments: continue
            
            # Check if all installments in the cycle are paid and the count matches the category requirement
            max_inst = cat.max_installments if cat else 0
            total_expected_for_cycle = (cat.amount * max_inst) if cat else 0
            total_paid_in_cycle = sum(p.amount for p in payments if p.is_paid)
            
            is_cycle_finished = (total_paid_in_cycle >= total_expected_for_cycle - 0.01) and all(p.is_paid for p in payments)
            
            is_incentive = True
            has_paid_something = False
            max_late_allowed = self._get_incentive_max_late()
            late_count = 0
            
            for p in payments:
                if p.due_date.date() <= today.date():
                    if not p.is_paid:
                        late_count += 1
                    else:
                        has_paid_something = True
                        if p.paid_date and p.paid_date.date() > p.due_date.date():
                            late_count += 1
                else:
                    # Future installments
                    if p.is_paid:
                        has_paid_something = True
                        if p.paid_date and p.paid_date.date() > p.due_date.date():
                            late_count += 1
            
            if late_count > max_late_allowed:
                is_incentive = False
            
            if is_cycle_finished:
                completed_cycle_count += 1
            if is_incentive and has_paid_something:
                incentive_count += 1

        return completed_cycle_count, incentive_count

    def refresh_draw_stats(self):
        if not hasattr(self, "category_selected_cycles"):
            self.category_selected_cycles = {}

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
            # Find the active cycle based on today's date for display label
            active_p = self.db.query(db_mod.Payment).join(db_mod.Subscriber).filter(
                db_mod.Subscriber.category == cat.name,
                db_mod.Payment.due_date <= today
            ).order_by(db_mod.Payment.due_date.desc()).first()
            active_cycle = active_p.cycle_number if active_p else 1
            
            cat_max = cat.max_cycles or 1
            max_p_cycle = self.db.query(func.max(db_mod.Payment.cycle_number)).join(db_mod.Subscriber).filter(
                db_mod.Subscriber.category == cat.name
            ).scalar() or 1
            total_cycles = max(cat_max, max_p_cycle)

            selected_cycle = self.category_selected_cycles.get(cat.name, "auto")
            completed_cycle_count, incentive_count = self._get_category_stats(cat, selected_cycle)
            
            # Create a Premium Category Card
            cat_card = QFrame(); cat_card.setObjectName("StatCard")
            v_lay = QVBoxLayout(cat_card); v_lay.setSpacing(12)
            
            header_row = QHBoxLayout()
            header = QLabel(f"📊 {cat.name}"); header.setObjectName("SectionTitle"); header.setStyleSheet("font-size: 16px;")
            
            combo_cycle = QComboBox()
            combo_cycle.setMinimumWidth(170)
            combo_cycle.addItem(f"الدورة الحالية تلقائياً (دورة {active_cycle})", "auto")
            for c_i in range(1, total_cycles + 1):
                combo_cycle.addItem(f"الدورة {c_i}", c_i)

            if selected_cycle == "auto" or selected_cycle is None:
                combo_cycle.setCurrentIndex(0)
            else:
                found_idx = combo_cycle.findData(selected_cycle)
                if found_idx >= 0:
                    combo_cycle.setCurrentIndex(found_idx)
                else:
                    combo_cycle.setCurrentIndex(0)

            header_row.addWidget(header)
            header_row.addStretch()
            header_row.addWidget(QLabel("تصفية الدورة:"))
            header_row.addWidget(combo_cycle)
            
            v_lay.addLayout(header_row)
            
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
            
            def make_on_change(c_box, cat_obj, w_l, i_l):
                def on_change():
                    val = c_box.currentData()
                    self.category_selected_cycles[cat_obj.name] = val
                    w_cnt, i_cnt = self._get_category_stats(cat_obj, val)
                    w_l.setText(str(w_cnt))
                    i_l.setText(str(i_cnt))
                return on_change
                
            combo_cycle.currentIndexChanged.connect(make_on_change(combo_cycle, cat, w_val, i_val))
            
            cat_card.setMinimumWidth(300)
            grid.addWidget(cat_card, idx // cols, idx % cols)
        
        if not categories:
            self.draw_stats_layout.addWidget(QLabel("لا توجد فئات مسجلة حالياً."))

    def refresh_draw_categories_filter(self):
        cats = self.db.query(db_mod.Category).all()
        for combo_attr in ['combo_draw_cat_filter', 'combo_draw_ex_cat_filter']:
            if not hasattr(self, combo_attr):
                continue
            combo = getattr(self, combo_attr)
            curr = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("كل الفئات", None)
            for cat in cats:
                combo.addItem(cat.name, cat.name)
            if curr:
                idx = combo.findData(curr)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def load_recent_winners(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all()
        
        query = self.db.query(db_mod.Winner)
        if hasattr(self, 'combo_draw_filter'):
            filter_val = self.combo_draw_filter.currentText()
            if filter_val != "الكل":
                query = query.filter(db_mod.Winner.draw_type.contains(filter_val))
                
        winners = query.order_by(db_mod.Winner.draw_date.desc()).all()
        
        # Prefetch subscribers for quick lookup
        subs = self.db.query(db_mod.Subscriber).all()
        sub_map = {s.subscriber_number: s for s in subs}
        
        cat_filter = self.combo_draw_cat_filter.currentData() if hasattr(self, 'combo_draw_cat_filter') else None
        search_txt = self.draw_winners_search.text().strip().lower() if hasattr(self, 'draw_winners_search') else ""
        
        filtered_winners = []
        for w in winners:
            sub = sub_map.get(w.subscriber_number)
            sub_name = sub.name if sub else "غير مسجل"
            sub_cat = sub.category if sub else "-"
            sub_phone = sub.phone if sub else "-"
            
            if cat_filter and sub_cat != cat_filter:
                continue
                
            if search_txt:
                match = (search_txt in sub_name.lower()) or (search_txt in (w.subscriber_number or "").lower()) or (search_txt in sub_phone.lower())
                if not match:
                    continue
                    
            filtered_winners.append((w, sub, sub_name, sub_cat, sub_phone))
            
        self.table_recent_winners.setRowCount(len(filtered_winners))
        for i, (w, sub, sub_name, sub_cat, sub_phone) in enumerate(filtered_winners):
            # 0: Subscriber Name
            item_name = QTableWidgetItem(sub_name)
            item_name.setData(Qt.ItemDataRole.UserRole, w.id)
            self.table_recent_winners.setItem(i, 0, item_name)
            
            # 1: Subscriber number / Account
            self.table_recent_winners.setItem(i, 1, QTableWidgetItem(w.subscriber_number or "-"))
            
            # 2: Category
            self.table_recent_winners.setItem(i, 2, QTableWidgetItem(sub_cat))
            
            # 3: Phone
            self.table_recent_winners.setItem(i, 3, QTableWidgetItem(sub_phone))
            
            # 4: Cycle number
            cycle_str = str(w.cycle_number) if w.cycle_number is not None else "-"
            self.table_recent_winners.setItem(i, 4, QTableWidgetItem(cycle_str))
            
            # 5: Draw type
            self.table_recent_winners.setItem(i, 5, QTableWidgetItem(w.draw_type or "سحب عام"))
            
            # 6: Draw date
            draw_date = w.draw_date.strftime("%Y-%m-%d %H:%M") if w.draw_date else "-"
            self.table_recent_winners.setItem(i, 6, QTableWidgetItem(draw_date))
            
            # 7: Payout Status
            is_rec = getattr(w, 'is_received', False)
            payout_item = QTableWidgetItem("🟢 تم الاستلام" if is_rec else "🔴 لم يستلم")
            if is_rec:
                payout_item.setForeground(QColor("#16a34a"))
            else:
                payout_item.setForeground(QColor("#dc2626"))
            self.table_recent_winners.setItem(i, 7, payout_item)

    def export_winners_excel(self):
        try:
            items = []
            subs = self.db.query(db_mod.Subscriber).all()
            sub_map = {s.subscriber_number: s for s in subs}
            winners = self.db.query(db_mod.Winner).order_by(db_mod.Winner.draw_date.desc()).all()
            cat_filter = self.combo_draw_cat_filter.currentData() if hasattr(self, 'combo_draw_cat_filter') else None
            filter_val = self.combo_draw_filter.currentText() if hasattr(self, 'combo_draw_filter') else "الكل"
            search_txt = self.draw_winners_search.text().strip().lower() if hasattr(self, 'draw_winners_search') else ""

            for w in winners:
                if filter_val != "الكل" and filter_val not in (w.draw_type or ""):
                    continue
                sub = sub_map.get(w.subscriber_number)
                sub_name = sub.name if sub else "غير مسجل"
                sub_cat = sub.category if sub else "-"
                sub_phone = sub.phone if sub else "-"
                
                if cat_filter and sub_cat != cat_filter:
                    continue
                if search_txt:
                    match = (search_txt in sub_name.lower()) or (search_txt in (w.subscriber_number or "").lower()) or (search_txt in sub_phone.lower())
                    if not match:
                        continue
                
                items.append({
                    "اسم المشترك": sub_name,
                    "رقم الحساب": w.subscriber_number,
                    "الفئة المالية": sub_cat,
                    "رقم الهاتف": sub_phone,
                    "رقم الدورة": w.cycle_number if w.cycle_number is not None else "-",
                    "نوع الجائزة": w.draw_type or "-",
                    "تاريخ السحب": w.draw_date.strftime("%Y-%m-%d %H:%M") if w.draw_date else "-",
                    "حالة الاستلام": "تم الاستلام" if getattr(w, 'is_received', False) else "لم يستلم",
                    "المبلغ المستلم (ر.ي)": getattr(w, 'payout_amount', 0.0)
                })

            if not items:
                ModernDialog(self, "تنبيه", "لا توجد بيانات فائزين مطابقة للشروط لتصديرها.").exec()
                return

            df = pd.DataFrame(items)
            default_name = f"winners_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ سجل الفائزين", default_name, "Excel Files (*.xlsx)")
            if not file_path:
                return

            with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="سجل الفائزين")
                workbook = writer.book
                worksheet = writer.sheets["سجل الفائزين"]
                worksheet.right_to_left()

            ModernDialog(self, "نجاح", f"تم تصدير سجل الفائزين بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {e}").exec()

    def load_draw_excluded(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all()

        if not hasattr(self, 'table_draw_excluded'):
            return

        cat_filter = self.combo_draw_ex_cat_filter.currentData() if hasattr(self, 'combo_draw_ex_cat_filter') else None
        search_txt = self.draw_ex_search.text().strip().lower() if hasattr(self, 'draw_ex_search') else ""

        all_subs = self.db.query(db_mod.Subscriber).all()
        excluded_list = []

        for sub in all_subs:
            sub_cat = sub.category or "-"
            if cat_filter and sub_cat != cat_filter:
                continue

            sub_name = sub.name or ""
            sub_acc = sub.subscriber_number or ""
            sub_phone = sub.phone or ""

            if search_txt:
                match = (search_txt in sub_name.lower()) or (search_txt in sub_acc.lower()) or (search_txt in sub_phone.lower())
                if not match:
                    continue

            fin_status = db_mod.calculate_financial_status(sub, self.db)
            is_excluded = False
            reason = ""
            status_badge = ""

            if sub.status == "excluded":
                is_excluded = True
                reason = sub.exclusion_reason or "استبعاد إداري مباشر"
                status_badge = "مستبعد 🚫"
            elif fin_status == "suspended":
                is_excluded = True
                reason = "إيقاف آلي بسبب تراكم الأقساط المتأخرة"
                status_badge = "موقوف ⚫"
            elif fin_status == "late":
                is_excluded = True
                reason = "تأخر وتعثر عن سداد الأقساط المستحقة"
                status_badge = "متأخر 🔴"
            elif sub.status == "pending":
                is_excluded = True
                reason = "طلب اشتراك معلق لم يتم اعتماده بعد"
                status_badge = "معلق 🟡"

            if is_excluded:
                excluded_list.append({
                    "id": sub.id,
                    "name": sub_name,
                    "acc": sub_acc,
                    "cat": sub_cat,
                    "phone": sub_phone,
                    "reason": reason,
                    "status_badge": status_badge,
                    "status": sub.status
                })

        self.table_draw_excluded.setRowCount(len(excluded_list))
        for i, item in enumerate(excluded_list):
            self.table_draw_excluded.setItem(i, 0, QTableWidgetItem(item["name"]))
            self.table_draw_excluded.setItem(i, 1, QTableWidgetItem(item["acc"]))
            self.table_draw_excluded.setItem(i, 2, QTableWidgetItem(item["cat"]))
            self.table_draw_excluded.setItem(i, 3, QTableWidgetItem(item["phone"]))
            
            reason_item = QTableWidgetItem(item["reason"])
            reason_item.setForeground(QColor("#b91c1c"))
            self.table_draw_excluded.setItem(i, 4, reason_item)
            
            st_item = QTableWidgetItem(item["status_badge"])
            self.table_draw_excluded.setItem(i, 5, st_item)

            btn_details = QPushButton("كشف حساب")
            btn_details.setObjectName("PrimaryBtn")
            btn_details.setStyleSheet("font-size: 11px; background-color: #2563eb; color: white; padding: 4px;")
            btn_details.clicked.connect(lambda checked, sid=item["id"]: self.open_account_details(sid))
            self.table_draw_excluded.setCellWidget(i, 6, btn_details)

    def export_draw_excluded_excel(self):
        try:
            cat_filter = self.combo_draw_ex_cat_filter.currentData() if hasattr(self, 'combo_draw_ex_cat_filter') else None
            search_txt = self.draw_ex_search.text().strip().lower() if hasattr(self, 'draw_ex_search') else ""

            all_subs = self.db.query(db_mod.Subscriber).all()
            items = []

            for sub in all_subs:
                sub_cat = sub.category or "-"
                if cat_filter and sub_cat != cat_filter:
                    continue

                sub_name = sub.name or ""
                sub_acc = sub.subscriber_number or ""
                sub_phone = sub.phone or ""

                if search_txt:
                    match = (search_txt in sub_name.lower()) or (search_txt in sub_acc.lower()) or (search_txt in sub_phone.lower())
                    if not match:
                        continue

                fin_status = db_mod.calculate_financial_status(sub, self.db)
                is_excluded = False
                reason = ""
                status_badge = ""

                if sub.status == "excluded":
                    is_excluded = True
                    reason = sub.exclusion_reason or "استبعاد إداري مباشر"
                    status_badge = "مستبعد"
                elif fin_status == "suspended":
                    is_excluded = True
                    reason = "إيقاف آلي بسبب تراكم الأقساط المتأخرة"
                    status_badge = "موقوف"
                elif fin_status == "late":
                    is_excluded = True
                    reason = "تأخر وتعثر عن سداد الأقساط المستحقة"
                    status_badge = "متأخر"
                elif sub.status == "pending":
                    is_excluded = True
                    reason = "طلب اشتراك معلق لم يتم اعتماده بعد"
                    status_badge = "معلق"

                if is_excluded:
                    items.append({
                        "اسم المشترك": sub_name,
                        "رقم الحساب": sub_acc,
                        "الفئة المالية": sub_cat,
                        "رقم الهاتف": sub_phone,
                        "سبب الاستبعاد": reason,
                        "حالة الانضباط": status_badge
                    })

            if not items:
                ModernDialog(self, "تنبيه", "لا توجد بيانات مستبعدين لتصديرها.").exec()
                return

            df = pd.DataFrame(items)
            default_name = f"draw_excluded_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ قائمة المستبعدين من السحب", default_name, "Excel Files (*.xlsx)")
            if not file_path:
                return

            with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="المستبعدين من السحب")
                workbook = writer.book
                worksheet = writer.sheets["المستبعدين من السحب"]
                worksheet.right_to_left()

            ModernDialog(self, "نجاح", f"تم تصدير قائمة المستبعدين من السحب بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء التصدير: {e}").exec()

    def show_winner_context_menu(self, pos):
        row = self.table_recent_winners.rowAt(pos.y())
        if row < 0: return
        
        wid = self.table_recent_winners.item(row, 0).data(Qt.ItemDataRole.UserRole)
        name_txt = self.table_recent_winners.item(row, 0).text()
        num_txt = self.table_recent_winners.item(row, 1).text()
        
        menu = QMenu(self)
        act_del = QAction(f"حذف الفائز ({name_txt} - {num_txt})", self)
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

    def perform_draw(self, draw_name):
        if not hasattr(self, "category_selected_cycles"):
            self.category_selected_cycles = {}
        # 1. Get accepted subscribers
        all_subs = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted").all()
        qualified_subs = []
        qualified_by_category = {}
        disqualified_count = 0
        
        today = datetime.datetime.now()
        for sub in all_subs:
            # التحقق من الانضباط المالي للمشترك
            fin_status = db_mod.calculate_financial_status(sub, self.db)
            if fin_status in ["late", "suspended"]:
                disqualified_count += 1
                continue

            # Determine the cycle for this subscriber (selected vs auto)
            cat_selected = self.category_selected_cycles.get(sub.category, "auto")
            if cat_selected != "auto" and isinstance(cat_selected, int):
                sub_current_cycle = cat_selected
            else:
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
            
            # Find category for max_installments
            cat = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
            max_inst = cat.max_installments if cat else 0

            # الأهلية: سداد كامل المبلغ المطلوب للدورة (مثلاً: 12 قسط × 1000 ريال)
            total_expected_for_cycle = (cat.amount * max_inst) if cat else 0
            total_paid_in_cycle = sum(p.amount for p in payments if p.is_paid)
            
            # المشترك مؤهل إذا سدد كامل المبلغ ولم يتبقَ عليه أي سجل غير مدفوع في الدورة
            is_cycle_finished = (total_paid_in_cycle >= total_expected_for_cycle - 0.01) and all(p.is_paid for p in payments)
            
            # التحقق مما إذا كان اليوم الأخير قد وصل
            last_payment_date = payments[-1].due_date if payments else today
            is_date_reached = today >= last_payment_date

            is_incentive = True
            has_paid_something = False
            max_late_allowed = self._get_incentive_max_late()
            late_count = 0

            for p in payments:
                if p.due_date.date() <= today.date():
                    if not p.is_paid:
                        late_count += 1
                    else:
                        has_paid_something = True
                        if p.paid_date and p.paid_date.date() > p.due_date.date():
                            late_count += 1
                else:
                    if p.is_paid:
                        has_paid_something = True
                        if p.paid_date and p.paid_date.date() > p.due_date.date():
                            late_count += 1

            if late_count > max_late_allowed:
                is_incentive = False
            
            if draw_name == "القرعة الاسبوعية":
                # استبعاد المشتركين الذين فازوا سابقاً في القرعة الاسبوعية في نفس الدورة
                already_won = self.db.query(db_mod.Winner).filter(
                    db_mod.Winner.subscriber_number == sub.subscriber_number,
                    db_mod.Winner.draw_type.contains(draw_name),
                    (db_mod.Winner.cycle_number == sub_current_cycle) | (db_mod.Winner.cycle_number == None)
                ).first()
                if already_won:
                    continue

                if is_cycle_finished and is_date_reached:
                    qualified_subs.append(sub)
                    if sub.category not in qualified_by_category: qualified_by_category[sub.category] = []
                    qualified_by_category[sub.category].append(sub)
            elif draw_name == "الجائزة التحفيزية":
                if is_incentive and has_paid_something:
                    qualified_subs.append(sub)
                    if sub.category not in qualified_by_category: qualified_by_category[sub.category] = []
                    qualified_by_category[sub.category].append(sub)
            else:
                # Grand Prize: Must have finished the cycle
                if is_cycle_finished and is_date_reached:
                    qualified_subs.append(sub)
        
        if not qualified_subs:
            msg_alert = f"لا يوجد مشتركون مستوفون لشروط {draw_name} حالياً."
            if disqualified_count > 0:
                msg_alert += f"\n\n(تنبيه: تم استبعاد {disqualified_count} مشتركين بسبب عدم الانضباط المالي: متأخر/موقوف)."
            ModernDialog(self, "تنبيه", msg_alert).exec()
            return
            
        if draw_name in ["القرعة الاسبوعية", "الجائزة التحفيزية"]:
            msg = f"هل أنت متأكد من بدء {draw_name}؟ (عدد الفئات المؤهلة: {len(qualified_by_category)})"
            if disqualified_count > 0:
                msg += f"\n\n⚠️ تم استبعاد {disqualified_count} مشتركين بسبب عدم الانضباط المالي (متأخر/موقوف)."
            if not ModernDialog(self, "تأكيد", msg, is_confirm=True).exec():
                return
            
            # Use the animated multi-category draw
            anim_dlg = DrawAnimationDialog(self, qualified_by_category, draw_name, self.db)
            anim_dlg.exec()
            self.load_recent_winners(); self.refresh_draw_stats()
            return

        msg = f"هل أنت متأكد من بدء {draw_name}؟ (عدد المؤهلين: {len(qualified_subs)})"
        if disqualified_count > 0:
            msg += f"\n\n⚠️ تم استبعاد {disqualified_count} مشتركين بسبب عدم الانضباط المالي (متأخر/موقوف)."
        if not ModernDialog(self, "تأكيد", msg, is_confirm=True).exec():
            return

        if draw_name == "الجائزة الكبرى":
            count_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_winners_count").first()
            num_winners = int(count_setting.value) if count_setting and count_setting.value.isdigit() else 1
            num_winners = min(num_winners, len(qualified_subs))
            
            winners = random.sample(qualified_subs, num_winners)
            
            res_msg = f"مبروك للفائزين في {draw_name}!\n\n"
            for w in winners:
                cat_selected = self.category_selected_cycles.get(w.category, "auto")
                if cat_selected != "auto" and isinstance(cat_selected, int):
                    cycle_num = cat_selected
                else:
                    active_p = self.db.query(db_mod.Payment).filter(
                        db_mod.Payment.subscriber_id == w.id,
                        db_mod.Payment.due_date <= datetime.datetime.now()
                    ).order_by(db_mod.Payment.due_date.desc()).first()
                    cycle_num = active_p.cycle_number if active_p else 1

                new_w = db_mod.Winner(
                    subscriber_number=w.subscriber_number, 
                    draw_type=draw_name,
                    draw_date=datetime.datetime.now(),
                    cycle_number=cycle_num
                )
                self.db.add(new_w)
                res_msg += f"الاسم: {w.name} - الفئة: {w.category} - رقم الحساب: {w.subscriber_number}\n"
            
            self.db.commit()
            ModernDialog(self, "تم السحب بنجاح", res_msg).exec()
            self.load_recent_winners()
            self.refresh_draw_stats()
            return

        # Simple Shuffling Effect Dialog
        winner = random.choice(qualified_subs)
        
        # Save Winner
        cat_selected = self.category_selected_cycles.get(winner.category, "auto")
        if cat_selected != "auto" and isinstance(cat_selected, int):
            cycle_num = cat_selected
        else:
            active_p = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == winner.id,
                db_mod.Payment.due_date <= datetime.datetime.now()
            ).order_by(db_mod.Payment.due_date.desc()).first()
            cycle_num = active_p.cycle_number if active_p else 1

        new_w = db_mod.Winner(
            subscriber_number=winner.subscriber_number, 
            draw_type=draw_name,
            draw_date=datetime.datetime.now(),
            cycle_number=cycle_num
        )
        self.db.add(new_w)
        self.db.commit()
        
        # Show Result
        res_msg = f"مبروك للفائز في {draw_name}!\n\nالاسم: {winner.name}\nالفئة: {winner.category}\nرقم الحساب: {winner.subscriber_number}\nرقم الهاتف: {winner.phone}"
        ModernDialog(self, "تم السحب بنجاح", res_msg).exec()
        
        self.load_recent_winners()
        self.refresh_draw_stats()

