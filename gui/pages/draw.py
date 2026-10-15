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

class GrandPrizePeriodDialog(QDialog):
    def __init__(self, parent, periods_count, weeks_per_period):
        super().__init__(parent)
        self.setWindowTitle("تحديد فترة الجائزة الكبرى")
        self.setFixedWidth(440)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(18)
        
        title_lbl = QLabel("👑 سحب الجائزة الكبرى بحسب الفترات")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #f59e0b;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel(f"تم إعداد الجائزة الكبرى على {periods_count} فترات ({weeks_per_period} أسابيع لكل فترة).\nيرجى تحديد الفترة المراد إجراء السحب لها:")
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setStyleSheet("font-size: 13px; color: #64748b;")
        layout.addWidget(desc_lbl)
        
        self.combo_period = QComboBox()
        self.combo_period.setFixedHeight(42)
        for i in range(1, periods_count + 1):
            w_start = (i - 1) * weeks_per_period + 1
            w_end = i * weeks_per_period
            self.combo_period.addItem(f"الفترة {i} (الأسابيع {w_start} إلى {w_end})", i)
        layout.addWidget(self.combo_period)
        
        btn_lay = QHBoxLayout()
        btn_ok = QPushButton("متابعة السحب")
        btn_ok.setObjectName("PrimaryBtn")
        btn_ok.setFixedHeight(40)
        btn_ok.clicked.connect(self.accept)
        
        btn_cancel = QPushButton("إلغاء")
        btn_cancel.setObjectName("DangerBtn")
        btn_cancel.setFixedHeight(40)
        btn_cancel.clicked.connect(self.reject)
        
        btn_lay.addWidget(btn_ok)
        btn_lay.addWidget(btn_cancel)
        layout.addLayout(btn_lay)
        
    def get_selected_period(self):
        return self.combo_period.currentData()

class DrawStatsLoader(QThread):
    stats_loaded = pyqtSignal(dict)

    def __init__(self, selected_cycles):
        super().__init__()
        self.selected_cycles = dict(selected_cycles or {})

    def run(self):
        try:
            from api_client import get_api_client
            client = get_api_client()
            res = client.get_draw_stats()
            stats = {c["category_name"]: (c["completed_cycle_count"], c["incentive_count"]) for c in res.get("categories", [])}
            if stats:
                self.stats_loaded.emit(stats)
                return
        except Exception:
            pass

        bg_db = db_mod.SessionLocal()
        try:
            today = datetime.datetime.now()
            today_date = today.date()
            categories = bg_db.query(db_mod.Category).all()
            all_accepted = bg_db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == 'accepted').all()
            fin_status_map = db_mod.calculate_financial_status_batch(all_accepted, bg_db)
            disciplined_by_cat = {}
            for s in all_accepted:
                if fin_status_map.get(s.id) not in ['late', 'suspended']:
                    disciplined_by_cat.setdefault(s.category, []).append(s)

            sub_ids = [s.id for subs in disciplined_by_cat.values() for s in subs]
            active_cycles = dict(
                bg_db.query(db_mod.Payment.subscriber_id, func.max(db_mod.Payment.cycle_number))
                .filter(db_mod.Payment.subscriber_id.in_(sub_ids), db_mod.Payment.due_date <= today)
                .group_by(db_mod.Payment.subscriber_id)
                .all()
            ) if sub_ids else {}

            needed_sub_cycles = {}
            for cat in categories:
                sel_c = self.selected_cycles.get(cat.name, 'auto')
                for s in disciplined_by_cat.get(cat.name, []):
                    if sel_c != 'auto' and isinstance(sel_c, int):
                        needed_sub_cycles[s.id] = sel_c
                    else:
                        needed_sub_cycles[s.id] = active_cycles.get(s.id, 1)

            needed_cycles_set = set(needed_sub_cycles.values()) if needed_sub_cycles else {1}
            payments_data = bg_db.query(
                db_mod.Payment.subscriber_id,
                db_mod.Payment.cycle_number,
                db_mod.Payment.amount,
                db_mod.Payment.due_date,
                db_mod.Payment.paid_date,
                db_mod.Payment.is_paid
            ).filter(
                db_mod.Payment.subscriber_id.in_(sub_ids),
                db_mod.Payment.cycle_number.in_(needed_cycles_set)
            ).all() if sub_ids else []

            payments_by_sub = {}
            for p in payments_data:
                if p[1] == needed_sub_cycles.get(p[0]):
                    payments_by_sub.setdefault(p[0], []).append(p)

            setting_inc = bg_db.query(db_mod.Setting).filter(db_mod.Setting.key == 'incentive_max_late_installments').first()
            max_late_allowed = int(setting_inc.value) if (setting_inc and setting_inc.value and str(setting_inc.value).isdigit()) else 1

            cat_stats = {}
            for cat in categories:
                subs = disciplined_by_cat.get(cat.name, [])
                max_inst = cat.max_installments or 0
                total_expected = (cat.amount * max_inst)
                completed = 0
                incentive = 0
                for s in subs:
                    s_payments = payments_by_sub.get(s.id, [])
                    if not s_payments: continue
                    total_paid = sum(p[2] for p in s_payments if p[5])
                    is_finished = (total_paid >= total_expected - 0.01) and all(p[5] for p in s_payments)
                    is_inc = True
                    has_paid = False
                    late_count = 0
                    for p in s_payments:
                        if not p[3]: continue
                        p_due = p[3].date()
                        is_p = p[5]
                        p_paid = p[4].date() if p[4] else None
                        if p_due <= today_date:
                            if not is_p: late_count += 1
                            else:
                                has_paid = True
                                if p_paid and p_paid > p_due: late_count += 1
                        else:
                            if is_p:
                                has_paid = True
                                if p_paid and p_paid > p_due: late_count += 1
                    if late_count > max_late_allowed:
                        is_inc = False
                    if is_finished: completed += 1
                    if is_inc and has_paid: incentive += 1
                cat_stats[cat.name] = (completed, incentive)

            self.stats_loaded.emit(cat_stats)
        except Exception as e:
            print("Error in DrawStatsLoader:", e)
        finally:
            bg_db.close()

class DrawMixin:
    def show_draw_management(self):
        page = self._ensure_page('page_draw', self.init_draw_page)
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all()
        self.content_stack.setCurrentWidget(page)
        self._update_nav_style("إدارة السحوبات")
        self.refresh_draw_categories_filter()
        self.refresh_draw_stats()
        current_idx = self.draw_tabs.currentIndex()
        if current_idx == 1:
            self.load_draw_excluded()
        elif current_idx == 2:
            self.load_recent_winners()


    def _on_draw_tab_changed(self, idx):
        if idx == 1:
            self.load_draw_excluded()
        elif idx == 2:
            self.load_recent_winners()
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
        self._draw_ex_search_timer = QTimer(page)
        self._draw_ex_search_timer.setSingleShot(True)
        self._draw_ex_search_timer.setInterval(350)
        self._draw_ex_search_timer.timeout.connect(self.load_draw_excluded)
        self.draw_ex_search.textChanged.connect(lambda: self._draw_ex_search_timer.start())
        self.draw_ex_search.returnPressed.connect(lambda: (self._draw_ex_search_timer.stop(), self.load_draw_excluded()))
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
        tab3.setStyleSheet("background-color: transparent; border: none;")
        con3 = QWidget(); lay3 = QVBoxLayout(con3); lay3.setContentsMargins(20, 20, 20, 20); lay3.setSpacing(25)
        
        # --- Weekly Draw Rules Frame ---
        weekly_frame = QFrame(); weekly_frame.setObjectName("StatCard")
        week_lay = QVBoxLayout(weekly_frame); week_lay.setContentsMargins(20, 20, 20, 20); week_lay.setSpacing(12)

        week_title_color = "color: #22c55e;" if is_dark else "color: #166534;"
        week_title = QLabel("🎯  معايير وضوابط القرعة الأسبوعية")
        week_title.setObjectName("SectionTitle")
        week_title.setStyleSheet(f"font-size: 16px; font-weight: bold; {week_title_color}")
        week_lay.addWidget(week_title)

        week_desc = QLabel(
            "• معيار التأهل: سداد كافة أقساط الدورة الحالية بنسبة 100% وبلوغ موعد الاستحقاق الأخير للدورة.\n"
            "• آلية السحب: سحب عشوائي عادل ومباشر بين كافة المشتركين المؤهلين في كل فئة مالية على حدة.\n"
            "• عدم تكرار الفوز: يُستبعد المشترك الذي فاز سابقاً في القرعة الأسبوعية لنفس الدورة تلقائياً لإتاحة الفرصة للآخرين.\n"
            "• الانضباط المالي: يُستبعد تلقائياً أي مشترك متعثر في السداد أو حالته (موقوف ⚫ / متأخر 🔴)."
        )
        week_desc.setWordWrap(True)
        week_desc.setStyleSheet(f"font-size: 13px; line-height: 1.6; {lbl_muted}")
        week_lay.addWidget(week_desc)
        lay3.addWidget(weekly_frame)

        # --- Incentive Prize Eligibility Settings ---
        incentive_frame = QFrame(); incentive_frame.setObjectName("StatCard")
        inc_lay = QVBoxLayout(incentive_frame); inc_lay.setContentsMargins(20, 20, 20, 20); inc_lay.setSpacing(15)

        inc_title_color = "color: #3b82f6;" if is_dark else "color: #1d4ed8;"
        inc_title = QLabel("⚙️  إعدادات المؤهلين في الجائزة التحفيزية")
        inc_title.setObjectName("SectionTitle")
        inc_title.setStyleSheet(f"font-size: 16px; font-weight: bold; {inc_title_color}")
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

        # --- Grand Prize Settings ---
        settings_frame = QFrame(); settings_frame.setObjectName("StatCard")
        set_lay = QVBoxLayout(settings_frame); set_lay.setContentsMargins(20, 20, 20, 20); set_lay.setSpacing(15)
        
        set_title_color = "color: #f59e0b;" if is_dark else "color: #b45309;"
        set_title = QLabel("👑  إعدادات الجائزة الكبرى")
        set_title.setObjectName("SectionTitle")
        set_title.setStyleSheet(f"font-size: 16px; font-weight: bold; {set_title_color}")
        set_lay.addWidget(set_title)
        
        form_layout = QFormLayout()
        
        self.spin_grand_periods = QSpinBox()
        self.spin_grand_periods.setMinimum(1)
        self.spin_grand_periods.setMaximum(50)
        self.spin_grand_periods.setValue(1)
        self.spin_grand_periods.valueChanged.connect(self.update_grand_period_summary)

        self.spin_grand_weeks_per_period = QSpinBox()
        self.spin_grand_weeks_per_period.setMinimum(1)
        self.spin_grand_weeks_per_period.setMaximum(52)
        self.spin_grand_weeks_per_period.setValue(12)
        self.spin_grand_weeks_per_period.valueChanged.connect(self.update_grand_period_summary)

        self.spin_winners = QSpinBox()
        self.spin_winners.setMinimum(1)
        self.spin_winners.setMaximum(1000)

        self.dt_start = QDateEdit()
        self.dt_start.setCalendarPopup(True)
        self.dt_start.setDisplayFormat("yyyy-MM-dd")
        
        self.dt_end = QDateEdit()
        self.dt_end.setCalendarPopup(True)
        self.dt_end.setDisplayFormat("yyyy-MM-dd")
        
        form_layout.addRow("عدد الفترات:", self.spin_grand_periods)
        form_layout.addRow("عدد الأسابيع في كل فترة:", self.spin_grand_weeks_per_period)
        form_layout.addRow("عدد الفائزين (لكل فترة):", self.spin_winners)
        form_layout.addRow("من تاريخ:", self.dt_start)
        form_layout.addRow("إلى تاريخ:", self.dt_end)
        
        set_lay.addLayout(form_layout)
        
        self.lbl_grand_calc_info = QLabel()
        self.lbl_grand_calc_info.setWordWrap(True)
        self.lbl_grand_calc_info.setStyleSheet("background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 8px; padding: 10px; font-size: 13px; color: #f59e0b;")
        set_lay.addWidget(self.lbl_grand_calc_info)

        btn_save = QPushButton("حفظ إعدادات الجائزة الكبرى")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.clicked.connect(self.save_draw_settings)
        set_lay.addWidget(btn_save)
        
        lay3.addWidget(settings_frame)
        lay3.addStretch()

        tab3.setWidget(con3)
        self.draw_tabs.addTab(tab3, "إعداد القرعات")
        self.draw_tabs.currentChanged.connect(self._on_draw_tab_changed)
        
        # تأجيل تحميل إعدادات السحب لما بعد رسم الواجهة لتجنب التجميد عند الفتح
        QTimer.singleShot(300, self.load_draw_settings)
        
        layout.addWidget(self.draw_tabs)
        return page

    def update_grand_period_summary(self):
        periods = self.spin_grand_periods.value()
        weeks = self.spin_grand_weeks_per_period.value()
        total_weeks = periods * weeks
        text = (
            f"👑 نظام فترات الجائزة الكبرى: تم ضبط {periods} فترات، وكل فترة مدتها {weeks} أسابيع "
            f"(إجمالي مدة الدورة: {total_weeks} أسبوعاً).\n"
            f"يتم السحب على الجائزة الكبرى بنهاية كل فترة للمشتركين الذين أتموا أقساط الفترة المحددة."
        )
        self.lbl_grand_calc_info.setText(text)

    def load_draw_settings(self):
        try:
            start_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_start_date").first()
            end_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_end_date").first()
            count_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_winners_count").first()
            periods_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_periods_count").first()
            weeks_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_weeks_per_period").first()
            
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

            if periods_setting and periods_setting.value.isdigit():
                self.spin_grand_periods.setValue(int(periods_setting.value))
            else:
                self.spin_grand_periods.setValue(1)

            if weeks_setting and weeks_setting.value.isdigit():
                self.spin_grand_weeks_per_period.setValue(int(weeks_setting.value))
            else:
                self.spin_grand_weeks_per_period.setValue(12)

            self.update_grand_period_summary()

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
            periods_val = str(self.spin_grand_periods.value())
            weeks_val = str(self.spin_grand_weeks_per_period.value())
            
            settings = {
                "grand_prize_start_date": start_val,
                "grand_prize_end_date": end_val,
                "grand_prize_winners_count": count_val,
                "grand_prize_periods_count": periods_val,
                "grand_prize_weeks_per_period": weeks_val
            }
            
            for key, val in settings.items():
                setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
                if setting:
                    setting.value = val
                else:
                    self.db.add(db_mod.Setting(key=key, value=val))
            
            self.db.commit()
            ModernDialog(self, "نجاح", "تم حفظ إعدادات الجائزة الكبرى بنجاح.").exec()
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
        if not subs_in_cat:
            return 0, 0

        # جلب الحالات المالية دفعة واحدة
        fin_status_map = db_mod.calculate_financial_status_batch(subs_in_cat, self.db)
        disciplined_subs = [s for s in subs_in_cat if fin_status_map.get(s.id) not in ["late", "suspended"]]
        if not disciplined_subs:
            return 0, 0

        sub_ids = [s.id for s in disciplined_subs]

        # جلب الدورات الحالية دفعة واحدة
        if target_cycle and target_cycle != "auto" and isinstance(target_cycle, int):
            active_cycles = {sid: target_cycle for sid in sub_ids}
        else:
            try:
                active_cycles = dict(
                    self.db.query(db_mod.Payment.subscriber_id, func.max(db_mod.Payment.cycle_number))
                    .filter(db_mod.Payment.subscriber_id.in_(sub_ids), db_mod.Payment.due_date <= today)
                    .group_by(db_mod.Payment.subscriber_id)
                    .all()
                )
            except Exception:
                active_cycles = {}

        # جلب دفعات هؤلاء المشتركين للدورات المطلوبة فقط (تجنب تحميل 14 ألف سجل وتجميد الواجهة)
        needed_cycles = set(active_cycles.values()) if active_cycles else {1}
        payments_data = self.db.query(
            db_mod.Payment.subscriber_id,
            db_mod.Payment.cycle_number,
            db_mod.Payment.amount,
            db_mod.Payment.due_date,
            db_mod.Payment.paid_date,
            db_mod.Payment.is_paid
        ).filter(
            db_mod.Payment.subscriber_id.in_(sub_ids),
            db_mod.Payment.cycle_number.in_(needed_cycles)
        ).all()

        payments_by_sub = {}
        for p in payments_data:
            payments_by_sub.setdefault(p[0], []).append(p)

        max_late_allowed = self._get_incentive_max_late()
        completed_cycle_count = 0
        incentive_count = 0
        max_inst = cat.max_installments if cat else 0
        total_expected_for_cycle = (cat.amount * max_inst) if cat else 0
        today_date = today.date()

        for sub in disciplined_subs:
            sub_current_cycle = active_cycles.get(sub.id, 1)
            all_s_p = payments_by_sub.get(sub.id, [])
            cycle_payments = [p for p in all_s_p if p[1] == sub_current_cycle]
            if not cycle_payments:
                continue

            total_paid_in_cycle = sum(p[2] for p in cycle_payments if p[5])
            is_cycle_finished = (total_paid_in_cycle >= total_expected_for_cycle - 0.01) and all(p[5] for p in cycle_payments)

            is_incentive = True
            has_paid_something = False
            late_count = 0

            for p in cycle_payments:
                if not p[3]:
                    continue
                p_due = p[3].date()
                is_p = p[5]
                p_paid = p[4].date() if p[4] else None

                if p_due <= today_date:
                    if not is_p:
                        late_count += 1
                    else:
                        has_paid_something = True
                        if p_paid and p_paid > p_due:
                            late_count += 1
                else:
                    if is_p:
                        has_paid_something = True
                        if p_paid and p_paid > p_due:
                            late_count += 1

            if late_count > max_late_allowed:
                is_incentive = False

            if is_cycle_finished:
                completed_cycle_count += 1
            if is_incentive and has_paid_something:
                incentive_count += 1

        return completed_cycle_count, incentive_count

    def refresh_draw_stats(self):
        """إعادة رسم إحصائيات السحب بشكل غير متزامن تماماً لتجنب التجميد."""
        if not hasattr(self, "category_selected_cycles"):
            self.category_selected_cycles = {}

        # إظهار حالة التحميل فوراً دون أي استعلام DB
        for i in reversed(range(self.draw_stats_layout.count())):
            item = self.draw_stats_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
            elif item and item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().setParent(None)

        loading_lbl = QLabel("⏳ جاري تحميل إحصائيات السحب...")
        loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_lbl.setStyleSheet("color: #94a3b8; font-size: 14px; padding: 20px;")
        self.draw_stats_layout.addWidget(loading_lbl)

        # تشغيل العامل في الخلفية لجلب البيانات
        if hasattr(self, '_draw_stats_loader') and self._draw_stats_loader.isRunning():
            self._draw_stats_loader.quit()
            self._draw_stats_loader.wait(100)
        self._draw_stats_loader = DrawStatsLoader(self.category_selected_cycles)
        self._draw_stats_loader.stats_loaded.connect(self._on_draw_stats_loaded_full)
        self._draw_stats_loader.start()

    def _on_draw_stats_loaded_full(self, cat_stats):
        """يُستدعى من الخيط الخلفي بعد تحميل الإحصائيات - يبني واجهة البطاقات."""
        if not hasattr(self, '_draw_stats_cache'):
            self._draw_stats_cache = {}
        self._draw_stats_cache.update(cat_stats)

        # مسح عنصر التحميل
        for i in reversed(range(self.draw_stats_layout.count())):
            item = self.draw_stats_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
            elif item and item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().setParent(None)

        # جلب الفئات والدورات في استعلام واحد خفيف
        try:
            categories = self.db.query(db_mod.Category).all()
        except Exception:
            categories = []
        
        today = datetime.datetime.now()
        try:
            active_cycles_by_cat = dict(
                self.db.query(db_mod.Subscriber.category, func.max(db_mod.Payment.cycle_number))
                .join(db_mod.Payment, db_mod.Subscriber.id == db_mod.Payment.subscriber_id)
                .filter(db_mod.Payment.due_date <= today)
                .group_by(db_mod.Subscriber.category)
                .all()
            )
        except Exception:
            active_cycles_by_cat = {}

        try:
            max_cycles_by_cat = dict(
                self.db.query(db_mod.Subscriber.category, func.max(db_mod.Payment.cycle_number))
                .join(db_mod.Payment, db_mod.Subscriber.id == db_mod.Payment.subscriber_id)
                .group_by(db_mod.Subscriber.category)
                .all()
            )
        except Exception:
            max_cycles_by_cat = {}

        if not categories:
            no_cat_lbl = QLabel("لا توجد فئات مسجلة حالياً.")
            no_cat_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.draw_stats_layout.addWidget(no_cat_lbl)
            return

        grid = QGridLayout()
        grid.setSpacing(15)
        self.draw_stats_layout.addLayout(grid)
        self._draw_stats_labels = {}
        cols = 2

        for idx, cat in enumerate(categories):
            active_cycle = active_cycles_by_cat.get(cat.name, 1)
            cat_max = cat.max_cycles or 1
            max_p_cycle = max_cycles_by_cat.get(cat.name, 1)
            total_cycles = max(cat_max, max_p_cycle)

            selected_cycle = self.category_selected_cycles.get(cat.name, "auto")
            cached_val = self._draw_stats_cache.get(cat.name)
            init_w = str(cached_val[0]) if cached_val else "—"
            init_i = str(cached_val[1]) if cached_val else "—"

            cat_card = QFrame()
            cat_card.setObjectName("StatCard")
            v_lay = QVBoxLayout(cat_card)
            v_lay.setSpacing(12)

            header_row = QHBoxLayout()
            header = QLabel(f"📊 {cat.name}")
            header.setObjectName("SectionTitle")
            header.setStyleSheet("font-size: 16px;")

            combo_cycle = QComboBox()
            combo_cycle.setMinimumWidth(170)
            combo_cycle.addItem(f"الدورة الحالية تلقائياً (دورة {active_cycle})", "auto")
            for c_i in range(1, total_cycles + 1):
                combo_cycle.addItem(f"الدورة {c_i}", c_i)

            if selected_cycle == "auto" or selected_cycle is None:
                combo_cycle.setCurrentIndex(0)
            else:
                found_idx = combo_cycle.findData(selected_cycle)
                combo_cycle.setCurrentIndex(found_idx if found_idx >= 0 else 0)

            header_row.addWidget(header)
            header_row.addStretch()
            header_row.addWidget(QLabel("تصفية الدورة:"))
            header_row.addWidget(combo_cycle)
            v_lay.addLayout(header_row)

            stats_row = QHBoxLayout()
            w_vbox = QVBoxLayout()
            w_val = QLabel(init_w)
            w_val.setStyleSheet("font-size: 24px; font-weight: 800; color: #2e7d32;")
            w_lbl = QLabel("أتموا الدورة")
            w_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
            w_vbox.addWidget(w_val)
            w_vbox.addWidget(w_lbl)

            i_vbox = QVBoxLayout()
            i_val = QLabel(init_i)
            i_val.setStyleSheet("font-size: 24px; font-weight: 800; color: #1b5e20;")
            i_lbl = QLabel("مؤهلين التحفيزية")
            i_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
            i_vbox.addWidget(i_val)
            i_vbox.addWidget(i_lbl)

            stats_row.addLayout(w_vbox)
            stats_row.addStretch()
            stats_row.addLayout(i_vbox)
            v_lay.addLayout(stats_row)

            self._draw_stats_labels[cat.name] = (w_val, i_val)

            # عند تغيير الدورة: تحديث النتائج بالخلفية لا على main thread
            def make_on_change(c_box, cat_obj, w_l, i_l):
                def on_change():
                    val = c_box.currentData()
                    self.category_selected_cycles[cat_obj.name] = val
                    w_l.setText("...")
                    i_l.setText("...")
                    # إعادة تشغيل الـ loader للفئة المحددة فقط
                    if hasattr(self, '_draw_stats_loader') and self._draw_stats_loader.isRunning():
                        return  # لا تزيد حمل الخيط إذا كان يعمل
                    self._draw_stats_loader = DrawStatsLoader(self.category_selected_cycles)
                    self._draw_stats_loader.stats_loaded.connect(self._on_draw_stats_loaded)
                    self._draw_stats_loader.start()
                return on_change

            combo_cycle.currentIndexChanged.connect(make_on_change(combo_cycle, cat, w_val, i_val))

            cat_card.setMinimumWidth(300)
            grid.addWidget(cat_card, idx // cols, idx % cols)

    def _on_draw_stats_loaded(self, cat_stats):
        """تحديث الأرقام في البطاقات الموجودة (للتحديث عند تغيير الدورة)."""
        if not hasattr(self, '_draw_stats_cache'):
            self._draw_stats_cache = {}
        self._draw_stats_cache.update(cat_stats)
        if hasattr(self, '_draw_stats_labels'):
            for cat_name, (w_cnt, i_cnt) in cat_stats.items():
                if cat_name in self._draw_stats_labels:
                    w_l, i_l = self._draw_stats_labels[cat_name]
                    w_l.setText(str(w_cnt))
                    i_l.setText(str(i_cnt))

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
        fin_status_map = db_mod.calculate_financial_status_batch(all_subs, self.db)
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

            fin_status = fin_status_map.get(sub.id, "pending")
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

        selected_period = 1
        periods_count = 1
        weeks_per_period = 12
        if draw_name == "الجائزة الكبرى":
            periods_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_periods_count").first()
            weeks_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_weeks_per_period").first()
            periods_count = int(periods_setting.value) if periods_setting and periods_setting.value.isdigit() else 1
            weeks_per_period = int(weeks_setting.value) if weeks_setting and weeks_setting.value.isdigit() else 12

            if periods_count > 1:
                dlg = GrandPrizePeriodDialog(self, periods_count, weeks_per_period)
                if not dlg.exec():
                    return
                selected_period = dlg.get_selected_period()

        # 1. Get accepted subscribers
        all_subs = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted").all()
        qualified_subs = []
        qualified_by_category = {}
        disqualified_count = 0
        
        today = datetime.datetime.now()
        
        # تحسين فائق: حساب الانضباط المالي دفعة واحدة لكافة المشتركين
        fin_status_map = db_mod.calculate_financial_status_batch(all_subs, self.db)
        cats_map = {c.name: c for c in self.db.query(db_mod.Category).all()}
        
        disciplined_subs = []
        for s in all_subs:
            fin_status = fin_status_map.get(s.id)
            if fin_status in ["late", "suspended"]:
                disqualified_count += 1
            else:
                disciplined_subs.append(s)
                
        sub_ids = [s.id for s in disciplined_subs]
        
        # جلب الدورات النشطة دفعة واحدة
        active_cycles = dict(
            self.db.query(db_mod.Payment.subscriber_id, func.max(db_mod.Payment.cycle_number))
            .filter(db_mod.Payment.subscriber_id.in_(sub_ids), db_mod.Payment.due_date <= today)
            .group_by(db_mod.Payment.subscriber_id)
            .all()
        ) if sub_ids else {}

        # تحديد الدورة المطلوبة لكل مشترك
        needed_sub_cycles = {}
        for sub in disciplined_subs:
            cat_selected = self.category_selected_cycles.get(sub.category, "auto")
            if cat_selected != "auto" and isinstance(cat_selected, int):
                sub_current_cycle = cat_selected
            else:
                sub_current_cycle = active_cycles.get(sub.id, 1)
            needed_sub_cycles[sub.id] = sub_current_cycle

        # جلب جميع أقساط الدورات المطلوبة بهؤلاء المشتركين فقط دفعة واحدة
        needed_cycles_set = set(needed_sub_cycles.values()) if needed_sub_cycles else {1}
        raw_payments = self.db.query(db_mod.Payment).filter(
            db_mod.Payment.subscriber_id.in_(sub_ids),
            db_mod.Payment.cycle_number.in_(needed_cycles_set)
        ).order_by(db_mod.Payment.installment_number.asc()).all() if sub_ids else []

        payments_by_sub = {}
        for p in raw_payments:
            if p.cycle_number == needed_sub_cycles.get(p.subscriber_id):
                payments_by_sub.setdefault(p.subscriber_id, []).append(p)

        max_late_allowed = self._get_incentive_max_late()

        for sub in disciplined_subs:
            payments = payments_by_sub.get(sub.id, [])
            if not payments:
                continue

            # Find category for max_installments
            cat = cats_map.get(sub.category)
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
                # الجائزة الكبرى: فحص الأهلية بحسب الفترة
                if periods_count > 1:
                    already_won = self.db.query(db_mod.Winner).filter(
                        db_mod.Winner.subscriber_number == sub.subscriber_number,
                        db_mod.Winner.draw_type.contains("الجائزة الكبرى"),
                        db_mod.Winner.draw_type.contains(f"الفترة {selected_period}"),
                        (db_mod.Winner.cycle_number == sub_current_cycle) | (db_mod.Winner.cycle_number == None)
                    ).first()
                    if already_won:
                        continue

                    req_weeks = selected_period * weeks_per_period
                    period_payments = [p for p in payments if (p.installment_number or 0) <= req_weeks]
                    if not period_payments:
                        continue

                    is_period_paid = all(p.is_paid for p in period_payments)
                    last_period_date = period_payments[-1].due_date if period_payments else today
                    is_period_date_reached = today >= last_period_date

                    if is_period_paid and is_period_date_reached:
                        qualified_subs.append(sub)
                else:
                    if is_cycle_finished and is_date_reached:
                        qualified_subs.append(sub)
        
        draw_title = f"{draw_name} (الفترة {selected_period})" if (draw_name == "الجائزة الكبرى" and periods_count > 1) else draw_name
        if not qualified_subs:
            msg_alert = f"لا يوجد مشتركون مستوفون لشروط {draw_title} حالياً."
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

        msg = f"هل أنت متأكد من بدء {draw_title}؟ (عدد المؤهلين: {len(qualified_subs)})"
        if disqualified_count > 0:
            msg += f"\n\n⚠️ تم استبعاد {disqualified_count} مشتركين بسبب عدم الانضباط المالي (متأخر/موقوف)."
        if not ModernDialog(self, "تأكيد", msg, is_confirm=True).exec():
            return

        if draw_name == "الجائزة الكبرى":
            count_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_winners_count").first()
            num_winners = int(count_setting.value) if count_setting and count_setting.value.isdigit() else 1
            num_winners = min(num_winners, len(qualified_subs))
            
            winners = random.sample(qualified_subs, num_winners)
            draw_label = f"الجائزة الكبرى - الفترة {selected_period}" if periods_count > 1 else "الجائزة الكبرى"
            
            res_msg = f"مبروك للفائزين في {draw_label}!\n\n"
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
                    draw_type=draw_label,
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

