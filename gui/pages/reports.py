from sqlalchemy import func
from sqlalchemy.orm import Session
import os
import sys
import subprocess
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
from gui.utils import reshape_text, ServerWorker, draw_pdf_header, setup_excel_header, register_arabic_font
from gui.dialogs import *

class ReportsMixin:
    # ------------------------------------------------------------------ helpers
    def _get_setting(self, key, default=""):
        """دالة مساعدة مركزية لجلب إعدادات الشركة من قاعدة البيانات."""
        s = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
        return s.value if s else default

    def init_reports_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(40, 40, 40, 40); layout.setSpacing(25)
        title = QLabel("مركز التقارير المتكاملة"); title.setObjectName("PageTitle"); layout.addWidget(title)

        subtitle = QLabel("جميع التقارير التي تحتاجها للإدارة المالية ومتابعة المشتركين والمراجعة التشغيلية.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #94a3b8; font-size: 14px;")
        layout.addWidget(subtitle)

        tabs = QTabWidget()
        
        # --- Tab 1: التقارير المالية ---
        tab_fin = QScrollArea(); tab_fin.setWidgetResizable(True); con_fin = QWidget(); l_fin = QVBoxLayout(con_fin); l_fin.setSpacing(20); l_fin.setContentsMargins(20, 20, 20, 20)
        grid_fin = QGridLayout(); grid_fin.setSpacing(20)
        
        # Financial Summary Card
        fin_card = QFrame(); fin_card.setObjectName("StatCard"); f_layout = QVBoxLayout(fin_card); f_layout.setSpacing(15)
        f_title = QLabel("ملخص مالي عام"); f_title.setObjectName("SectionTitle"); f_layout.addWidget(f_title)
        f_desc = QLabel("تقرير يجمع الإيرادات والمصروفات والأقساط المتبقية في ملف Excel."); f_desc.setWordWrap(True); f_desc.setStyleSheet("color: #94a3b8;")
        f_layout.addWidget(f_desc)
        btn_fin = QPushButton("Excel"); btn_fin.setObjectName("PrimaryBtn"); btn_fin.clicked.connect(self.generate_overall_financial_summary_report)
        f_layout.addWidget(btn_fin)
        grid_fin.addWidget(fin_card, 0, 0)

        # Custom Payment Report Card
        cust_card = QFrame(); cust_card.setObjectName("StatCard"); cu_layout = QVBoxLayout(cust_card); cu_layout.setSpacing(15)
        cu_title = QLabel("التقرير المخصص للأقساط"); cu_title.setObjectName("SectionTitle"); cu_layout.addWidget(cu_title)
        cu_desc = QLabel("حدد الفئة والحالة والفترة لتوليد تقرير الأقساط المخصص بصيغة Excel."); cu_desc.setWordWrap(True); cu_desc.setStyleSheet("color: #94a3b8;")
        cu_layout.addWidget(cu_desc)
        form = QFormLayout()
        self.rep_date_start = QDateEdit(); self.rep_date_start.setCalendarPopup(True); self.rep_date_start.setDate(QDate.currentDate().addMonths(-1))
        self.rep_date_end = QDateEdit(); self.rep_date_end.setCalendarPopup(True); self.rep_date_end.setDate(QDate.currentDate())
        self.rep_status = QComboBox(); self.rep_status.addItems(["الكل", "مدفوع", "غير مدفوع"])
        self.rep_cat_filter = QComboBox()
        self.rep_cat_filter.addItem("الكل", None)
        form.addRow("من تاريخ:", self.rep_date_start)
        form.addRow("إلى تاريخ:", self.rep_date_end)
        form.addRow("الحالة:", self.rep_status)
        form.addRow("الفئة:", self.rep_cat_filter)
        cu_layout.addLayout(form)
        btn_cust = QPushButton("Excel"); btn_cust.setObjectName("PrimaryBtn"); btn_cust.clicked.connect(self.generate_custom_report)
        cu_layout.addWidget(btn_cust)
        grid_fin.addWidget(cust_card, 0, 1)

        # Expense Report Card
        exp_card = QFrame(); exp_card.setObjectName("StatCard"); exp_layout = QVBoxLayout(exp_card); exp_layout.setSpacing(15)
        exp_title = QLabel("تقرير المصاريف"); exp_title.setObjectName("SectionTitle"); exp_layout.addWidget(exp_title)
        exp_desc = QLabel("تصدير مصاريف التشغيل مع فلترة حسب التاريخ والتصنيف."); exp_desc.setWordWrap(True); exp_desc.setStyleSheet("color: #94a3b8;")
        exp_layout.addWidget(exp_desc)
        exp_form = QFormLayout()
        self.exp_rep_date_start = QDateEdit(); self.exp_rep_date_start.setCalendarPopup(True); self.exp_rep_date_start.setDate(QDate.currentDate().addMonths(-1))
        self.exp_rep_date_end = QDateEdit(); self.exp_rep_date_end.setCalendarPopup(True); self.exp_rep_date_end.setDate(QDate.currentDate())
        self.exp_rep_exp_cat_filter = QComboBox()
        self.exp_rep_exp_cat_filter.addItem("الكل")
        exp_form.addRow("من تاريخ:", self.exp_rep_date_start)
        exp_form.addRow("إلى تاريخ:", self.exp_rep_date_end)
        exp_form.addRow("التصنيف:", self.exp_rep_exp_cat_filter)
        exp_layout.addLayout(exp_form)
        btn_exp = QPushButton("Excel"); btn_exp.setObjectName("PrimaryBtn"); btn_exp.clicked.connect(self.generate_expense_summary_report)
        exp_layout.addWidget(btn_exp)
        l_fin.addLayout(grid_fin); l_fin.addWidget(exp_card); l_fin.addStretch()
        tab_fin.setWidget(con_fin)
        tabs.addTab(tab_fin, "التقارير المالية")

        # --- Tab 2: تقارير المشتركين ---
        tab_sub = QScrollArea(); tab_sub.setWidgetResizable(True); con_sub = QWidget(); l_sub = QVBoxLayout(con_sub); l_sub.setSpacing(20); l_sub.setContentsMargins(20, 20, 20, 20)
        grid_sub = QGridLayout(); grid_sub.setSpacing(20)
        
        # Subscriber Statement Card
        sub_card = QFrame(); sub_card.setObjectName("StatCard"); s_layout = QVBoxLayout(sub_card); s_layout.setSpacing(15)
        s_title = QLabel("كشف حساب مشترك"); s_title.setObjectName("SectionTitle"); s_layout.addWidget(s_title)
        s_desc = QLabel("اختر مشتركاً لتصدير كشف حسابه بتنسيق Excel أو PDF."); s_desc.setWordWrap(True); s_desc.setStyleSheet("color: #94a3b8;")
        s_layout.addWidget(s_desc)
        row1 = QHBoxLayout()
        self.rep_sub_cb = QComboBox(); self.rep_sub_cb.setEditable(True); self.rep_sub_cb.setPlaceholderText("اختر أو ابحث عن مشترك...")
        row1.addWidget(self.rep_sub_cb, 1)
        s_layout.addLayout(row1)
        row1_buttons = QHBoxLayout()
        btn_sub_ex = QPushButton("Excel"); btn_sub_ex.setObjectName("PrimaryBtn"); btn_sub_ex.clicked.connect(lambda: self.generate_subscriber_report("excel"))
        btn_sub_pdf = QPushButton("PDF"); btn_sub_pdf.setObjectName("DangerBtn"); btn_sub_pdf.clicked.connect(lambda: self.generate_subscriber_report("pdf"))
        row1_buttons.addWidget(btn_sub_ex); row1_buttons.addWidget(btn_sub_pdf)
        s_layout.addLayout(row1_buttons)
        grid_sub.addWidget(sub_card, 0, 0)

        # Subscriber Contact List Card
        contact_card = QFrame(); contact_card.setObjectName("StatCard"); contact_layout = QVBoxLayout(contact_card); contact_layout.setSpacing(15)
        contact_title = QLabel("قائمة المشتركين"); contact_title.setObjectName("SectionTitle"); contact_layout.addWidget(contact_title)
        contact_desc = QLabel("تصدير قائمة المشتركين مع بيانات الاتصال والفئات."); contact_desc.setWordWrap(True); contact_desc.setStyleSheet("color: #94a3b8;")
        contact_layout.addWidget(contact_desc)
        contact_buttons = QHBoxLayout()
        btn_contact_excel = QPushButton("Excel"); btn_contact_excel.setObjectName("PrimaryBtn"); btn_contact_excel.clicked.connect(lambda: self.generate_subscriber_contact_list_report("excel"))
        btn_contact_pdf = QPushButton("PDF"); btn_contact_pdf.setObjectName("PrimaryBtn"); btn_contact_pdf.clicked.connect(lambda: self.generate_subscriber_contact_list_report("pdf"))
        contact_buttons.addWidget(btn_contact_excel); contact_buttons.addWidget(btn_contact_pdf)
        contact_layout.addLayout(contact_buttons)
        grid_sub.addWidget(contact_card, 0, 1)

        # Category Summary Card
        cat_card = QFrame(); cat_card.setObjectName("StatCard"); c_layout = QVBoxLayout(cat_card); c_layout.setSpacing(15)
        c_title = QLabel("ملخص الفئات"); c_title.setObjectName("SectionTitle"); c_layout.addWidget(c_title)
        c_desc = QLabel("تقرير يوضح عدد المشتركين والمبالغ لكل فئة."); c_desc.setWordWrap(True); c_desc.setStyleSheet("color: #94a3b8;")
        c_layout.addWidget(c_desc)
        btn_cat = QPushButton("PDF"); btn_cat.setObjectName("PrimaryBtn"); btn_cat.clicked.connect(self.generate_categories_report)
        c_layout.addWidget(btn_cat)
        l_sub.addLayout(grid_sub); l_sub.addWidget(cat_card); l_sub.addStretch()
        tab_sub.setWidget(con_sub)
        tabs.addTab(tab_sub, "تقارير المشتركين")

        # --- Tab 3: تقارير السحوبات ---
        tab_draw = QScrollArea(); tab_draw.setWidgetResizable(True); con_draw = QWidget(); l_draw = QVBoxLayout(con_draw); l_draw.setSpacing(20); l_draw.setContentsMargins(20, 20, 20, 20)
        
        # Winner Report Card
        win_card = QFrame(); win_card.setObjectName("StatCard"); w_layout = QVBoxLayout(win_card); w_layout.setSpacing(15)
        w_title = QLabel("تقرير الفائزين"); w_title.setObjectName("SectionTitle"); w_layout.addWidget(w_title)
        w_desc = QLabel("سجل كامل بالفائزين يمكن فلترته حسب نوع الجائزة وتصديره."); w_desc.setWordWrap(True); w_desc.setStyleSheet("color: #94a3b8;")
        w_layout.addWidget(w_desc)
        
        row_w = QHBoxLayout()
        row_w.addWidget(QLabel("نوع السحب:"))
        self.rep_win_type = QComboBox()
        self.rep_win_type.addItems(["الكل", "القرعة الاسبوعية", "الجائزة التحفيزية", "الجائزة الكبرى"])
        row_w.addWidget(self.rep_win_type)
        row_w.addStretch()
        w_layout.addLayout(row_w)
        
        btn_win = QPushButton("Excel"); btn_win.setObjectName("PrimaryBtn"); btn_win.clicked.connect(self.generate_winners_report)
        w_layout.addWidget(btn_win)
        l_draw.addWidget(win_card); l_draw.addStretch()
        tab_draw.setWidget(con_draw)
        tabs.addTab(tab_draw, "السحوبات والجوائز")

        # --- Tab 4: تقارير الموظفين ---
        tab_staff = QScrollArea(); tab_staff.setWidgetResizable(True); con_staff = QWidget(); l_staff = QVBoxLayout(con_staff); l_staff.setSpacing(20); l_staff.setContentsMargins(20, 20, 20, 20)
        
        staff_card = QFrame(); staff_card.setObjectName("StatCard"); st_layout = QVBoxLayout(staff_card); st_layout.setSpacing(15)
        st_title = QLabel("تقرير عمليات الموظفين"); st_title.setObjectName("SectionTitle"); st_layout.addWidget(st_title)
        st_desc = QLabel("تصدير تقرير بالأقساط والمبالغ التي قام كل موظف بتحصيلها خلال فترة معينة."); st_desc.setWordWrap(True); st_desc.setStyleSheet("color: #94a3b8;")
        st_layout.addWidget(st_desc)
        
        st_form = QFormLayout()
        self.rep_staff_cb = QComboBox()
        self.rep_staff_cb.addItem("الكل", None)
        self.rep_staff_date_start = QDateEdit(); self.rep_staff_date_start.setCalendarPopup(True); self.rep_staff_date_start.setDate(QDate.currentDate().addMonths(-1))
        self.rep_staff_date_end = QDateEdit(); self.rep_staff_date_end.setCalendarPopup(True); self.rep_staff_date_end.setDate(QDate.currentDate())
        
        st_form.addRow("الموظف:", self.rep_staff_cb)
        st_form.addRow("من تاريخ:", self.rep_staff_date_start)
        st_form.addRow("إلى تاريخ:", self.rep_staff_date_end)
        st_layout.addLayout(st_form)
        
        btn_staff = QPushButton("Excel"); btn_staff.setObjectName("PrimaryBtn"); btn_staff.clicked.connect(self.generate_staff_report)
        st_layout.addWidget(btn_staff)
        l_staff.addWidget(staff_card); l_staff.addStretch()
        tab_staff.setWidget(con_staff)
        tabs.addTab(tab_staff, "تقارير الموظفين")

        # --- Tab 5: مركز المستندات ---
        tab_up = QScrollArea(); tab_up.setWidgetResizable(True); con_up = QWidget(); l_up = QVBoxLayout(con_up); l_up.setSpacing(20); l_up.setContentsMargins(20, 20, 20, 20)
        
        # Upload Center
        up_card = QFrame(); up_card.setObjectName("StatCard"); up_layout = QVBoxLayout(up_card); up_layout.setSpacing(15)
        up_title = QLabel("رفع مستندات وتقارير"); up_title.setObjectName("SectionTitle"); up_layout.addWidget(up_title)
        up_desc = QLabel("يمكنك رفع ملفات PDF أو Excel ومراجعتها لاحقاً من هنا."); up_desc.setWordWrap(True); up_desc.setStyleSheet("color: #94a3b8;")
        up_layout.addWidget(up_desc)
        row_up = QHBoxLayout()
        self.btn_upload_report = QPushButton("رفع ملف جديد"); self.btn_upload_report.setObjectName("PrimaryBtn"); self.btn_upload_report.setFixedHeight(40); self.btn_upload_report.clicked.connect(self.upload_new_report)
        row_up.addWidget(self.btn_upload_report); row_up.addStretch()
        up_layout.addLayout(row_up)
        self.list_uploaded_reports = QListWidget()
        self.list_uploaded_reports.setMinimumHeight(150)
        self.list_uploaded_reports.itemDoubleClicked.connect(lambda item: self.open_uploaded_file(item.text().split("  |")[0].strip()))
        self.list_uploaded_reports.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_uploaded_reports.customContextMenuRequested.connect(self.show_upload_context_menu)
        up_layout.addWidget(self.list_uploaded_reports)
        l_up.addWidget(up_card); l_up.addStretch()
        tab_up.setWidget(con_up)
        tabs.addTab(tab_up, "مركز المستندات المحفوظة")

        # --- Tab 6: تقارير مؤهلي السحوبات والجوائز ---
        tab_qual = QScrollArea(); tab_qual.setWidgetResizable(True); con_qual = QWidget(); l_qual = QVBoxLayout(con_qual); l_qual.setSpacing(20); l_qual.setContentsMargins(20, 20, 20, 20)
        
        qual_card = QFrame(); qual_card.setObjectName("StatCard"); q_layout = QVBoxLayout(qual_card); q_layout.setSpacing(15)
        q_title = QLabel("مركز تقارير المؤهلين لدخول السحوبات والجوائز"); q_title.setObjectName("SectionTitle"); q_layout.addWidget(q_title)
        q_desc = QLabel("حدد نوع السحب والفئة ورقم الدورة لاستعراض وتوليد كشف المشتركين المؤهلين بشكل رسمي ومطابق لشروط المنظومة."); q_desc.setWordWrap(True); q_desc.setStyleSheet("color: #94a3b8;")
        q_layout.addWidget(q_desc)
        
        q_form = QFormLayout()
        q_form.setSpacing(12)
        
        self.rep_qual_draw_type = QComboBox()
        self.rep_qual_draw_type.addItems(["الكل", "القرعة الاسبوعية", "الجائزة التحفيزية", "الجائزة الكبرى"])
        self.rep_qual_draw_type.currentIndexChanged.connect(self.refresh_qualified_draw_table)
        q_form.addRow("نوع السحب / الجائزة:", self.rep_qual_draw_type)
        
        self.rep_qual_category = QComboBox()
        self.rep_qual_category.addItem("كل الفئات", None)
        self.rep_qual_category.currentIndexChanged.connect(self.on_qual_category_changed)
        q_form.addRow("الفئة المالية:", self.rep_qual_category)
        
        self.rep_qual_cycle = QComboBox()
        self.rep_qual_cycle.addItem("الدورة الحالية (تلقائي)", "auto")
        for cyc in range(1, 21):
            self.rep_qual_cycle.addItem(f"الدورة رقم {cyc}", cyc)
        self.rep_qual_cycle.currentIndexChanged.connect(self.refresh_qualified_draw_table)
        q_form.addRow("رقم الدورة المستهدفة:", self.rep_qual_cycle)
        
        self.rep_qual_status_filter = QComboBox()
        self.rep_qual_status_filter.addItem("الكل (مؤهلين وغير مؤهلين)", "all")
        self.rep_qual_status_filter.addItem("🟢 المؤهلون فقط", "qualified")
        self.rep_qual_status_filter.addItem("🔴 غير المؤهلين فقط", "not_qualified")
        self.rep_qual_status_filter.currentIndexChanged.connect(self.refresh_qualified_draw_table)
        q_form.addRow("تصفية بالأهلية:", self.rep_qual_status_filter)
        
        self.rep_qual_search = QLineEdit()
        self.rep_qual_search.setPlaceholderText("ابحث باسم المشترك، رقم الحساب، أو الهاتف...")
        self.rep_qual_search.textChanged.connect(self.refresh_qualified_draw_table)
        q_form.addRow("بحث سريع:", self.rep_qual_search)
        
        q_layout.addLayout(q_form)
        
        btn_row = QHBoxLayout()
        btn_qual_ex = QPushButton("تصدير Excel رسمياً")
        btn_qual_ex.setObjectName("PrimaryBtn")
        btn_qual_ex.clicked.connect(lambda: self.export_qualified_draw_report("excel"))
        
        btn_qual_pdf = QPushButton("تصدير PDF رسمياً")
        btn_qual_pdf.setObjectName("DangerBtn")
        btn_qual_pdf.clicked.connect(lambda: self.export_qualified_draw_report("pdf"))
        
        btn_qual_save_doc = QPushButton("حفظ التقرير في مركز المستندات")
        btn_qual_save_doc.setStyleSheet("background-color: #8b5cf6; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
        btn_qual_save_doc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_qual_save_doc.clicked.connect(self.save_qualified_report_to_documents)
        
        btn_row.addWidget(btn_qual_ex)
        btn_row.addWidget(btn_qual_pdf)
        btn_row.addWidget(btn_qual_save_doc)
        btn_row.addStretch()
        q_layout.addLayout(btn_row)
        
        l_qual.addWidget(qual_card)
        
        self.table_rep_draw_qualified = QTableWidget()
        self.table_rep_draw_qualified.setColumnCount(9)
        self.table_rep_draw_qualified.setHorizontalHeaderLabels([
            "اسم المشترك", "الهاتف", "الفئة", "رقم الحساب", "نوع السحب", "الدورة", "سداد الدورة", "الانضباط", "حالة الأهلية"
        ])
        self.table_rep_draw_qualified.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_rep_draw_qualified.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_rep_draw_qualified.setMinimumHeight(300)
        l_qual.addWidget(self.table_rep_draw_qualified)
        
        tab_qual.setWidget(con_qual)
        tabs.addTab(tab_qual, "تقارير مؤهلي السحوبات")

        layout.addWidget(tabs)
        return page
    def refresh_reports_sub_list(self):
        self.rep_sub_cb.clear()
        subs = self.db.query(db_mod.Subscriber).all()
        for s in subs:
            self.rep_sub_cb.addItem(f"{s.name} ({s.phone})", s.id)

        self.rep_cat_filter.clear()
        self.rep_cat_filter.addItem("الكل", None)
        self.exp_rep_exp_cat_filter.clear()
        self.exp_rep_exp_cat_filter.addItem("الكل")
        for c in self.db.query(db_mod.Category).all():
            self.rep_cat_filter.addItem(c.name, c.name)
            self.exp_rep_exp_cat_filter.addItem(c.name)
            
        if hasattr(self, 'rep_staff_cb'):
            self.rep_staff_cb.clear()
            self.rep_staff_cb.addItem("الكل", None)
            for st in self.db.query(db_mod.Staff).all():
                self.rep_staff_cb.addItem(st.name, st.id)

        if hasattr(self, 'rep_qual_category'):
            self.rep_qual_category.blockSignals(True)
            self.rep_qual_category.clear()
            self.rep_qual_category.addItem("كل الفئات", None)
            for c in self.db.query(db_mod.Category).all():
                self.rep_qual_category.addItem(c.name, c.name)
            self.rep_qual_category.blockSignals(False)
            self.on_qual_category_changed()
    def generate_subscriber_report(self, fmt):
        sid = self.rep_sub_cb.currentData()
        if not sid: return
        
        try:
            sub = self.db.get(db_mod.Subscriber, sid)
            payments = self.db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sid).order_by(
                db_mod.Payment.cycle_number.desc(),
                db_mod.Payment.installment_number.desc()
            ).all()
            
            total_paid = sum(p.amount for p in payments if p.is_paid)
            total_due = sum(p.amount for p in payments if not p.is_paid)
            
            if fmt == "excel":
                default_name = f"statement_{sub.phone}.xlsx"
                file_path, _ = QFileDialog.getSaveFileName(self, "حفظ كشف الحساب (Excel)", default_name, "Excel Files (*.xlsx)")
                if not file_path: return

                data = []
                for p in payments: data.append({
                    "التاريخ": (p.due_date.strftime("%Y-%m-%d") if p.due_date else "-"),
                    "المبلغ": p.amount,
                    "القسط": p.installment_number,
                    "الدورة": p.cycle_number,
                    "الحالة": "مدفوع" if p.is_paid else "غير مدفوع",
                    "الملاحظة": (p.note or "-").split("|")[0].strip()
                })
                
                df = pd.DataFrame(data)

                company_name = self._get_setting("company_name", "هكبة المليون")
                company_logo_path = self._get_setting("company_logo_path", "")

                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Statement', index=False, startrow=8)
                    workbook = writer.book
                    worksheet = writer.sheets['Statement']
                    setup_excel_header(
                        workbook=workbook, worksheet=worksheet, df=df,
                        title="كشف حساب المشترك",
                        subtitle=f"{sub.name} ({sub.subscriber_number})",
                        company_name=company_name, company_logo_path=company_logo_path,
                        start_row=8
                    )

                    summary_header_format = workbook.add_format({'bold': True, 'bg_color': '#e8f5e9', 'color': '#0a3d0e', 'border': 1, 'font_name': 'Arial', 'font_size': 11})
                    summary_value_format = workbook.add_format({'bg_color': '#e8f5e9', 'border': 1, 'num_format': '#,##0.00', 'font_name': 'Arial', 'font_size': 11})
                    worksheet.write('A5', 'إجمالي المسدد', summary_header_format); worksheet.write('B5', total_paid, summary_value_format)
                    worksheet.write('C5', 'إجمالي المتبقي', summary_header_format); worksheet.write('D5', total_due, summary_value_format)
                    worksheet.write('E5', 'تاريخ التقرير', summary_header_format); worksheet.write('F5', datetime.datetime.now().strftime('%Y-%m-%d'), summary_value_format)

                ModernDialog(self, "نجاح", f"تم حفظ التقرير بنجاح في:\n{file_path}").exec()
            else:
                default_name = f"statement_{sub.phone}.pdf"
                file_path, _ = QFileDialog.getSaveFileName(self, "حفظ كشف الحساب (PDF)", default_name, "PDF Files (*.pdf)")
                if not file_path: return

                c = canvas.Canvas(file_path, pagesize=A4)
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

                company_name       = self._get_setting("company_name",             "هكبة المليون")
                company_legal_name = self._get_setting("company_legal_name",       "الاسبوعية")
                company_record     = self._get_setting("company_commercial_record", "")
                company_logo_path  = self._get_setting("company_logo_path",        "")

                def draw_ar(cv, x, y, text, size=10, color=colors.black):
                    cv.setFont(font_name, size)
                    cv.setFillColor(color)
                    cv.drawString(x, y, reshape_text(str(text)))

                def draw_header(cv, page_num=1):
                    draw_pdf_header(
                        c=cv, title="كشف حساب المشترك", subtitle="", page_num=page_num,
                        W=W, H=H, M=M, font_name=font_name,
                        company_name=company_name, company_legal_name=company_legal_name,
                        company_record=company_record, company_logo_path=company_logo_path
                    )

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
                c.roundRect(M + 6, y - 20, half - 12, 16, 3, fill=1, stroke=0)
                c.roundRect(M + half + 6, y - 20, half - 12, 16, 3, fill=1, stroke=0)
                draw_ar(c, M + 12, y - 15, "بيانات المشترك", size=9, color=GOLD)
                draw_ar(c, M + half + 12, y - 15, "بيانات المنظومة", size=9, color=GOLD)
                sub_rows = [("الاسم الكامل", sub.name or "—"), ("رقم المشترك", sub.subscriber_number or "—"), ("رقم الهاتف", sub.phone or "—"), ("الفئة", sub.category or "—")]
                yi = y - 34
                for lbl, val in sub_rows:
                    draw_ar(c, M + 12, yi, f"{lbl}:", size=8, color=GREY_TXT)
                    draw_ar(c, M + 90, yi, val, size=8, color=DARK_GREEN)
                    yi -= 14
                total_all = total_paid + total_due
                hak_rows = [("اسم المنظومة", company_name), ("النوع", company_legal_name or "منظومة ادخار"), ("إجمالي المسدّد", f"{total_paid:,.0f} ريال"), ("المتبقي", f"{total_due:,.0f} ريال")]
                yi = y - 34
                for lbl, val in hak_rows:
                    draw_ar(c, M + half + 12, yi, f"{lbl}:", size=8, color=GREY_TXT)
                    draw_ar(c, M + half + 90, yi, val, size=8, color=DARK_GREEN)
                    yi -= 14
                y -= BOX_H + 12
                c.setFillColor(MID_GREEN)
                c.roundRect(M, y - 18, W - 2*M, 18, 4, fill=1, stroke=0)
                draw_ar(c, M + 10, y - 13, "سجل الأقساط التفصيلي", size=10, color=GOLD)
                y -= 22
                COL_X = [M, M+52, M+120, M+200, M+290, M+375]
                HDRS  = ["الدورة/القسط", "المبلغ", "تاريخ الاستحقاق", "تاريخ السداد", "الحالة", "ملاحظة"]
                ROW_H = 17
                def draw_table_header(cv, y_pos):
                    cv.setFillColor(DARK_GREEN)
                    cv.rect(M, y_pos - ROW_H, W - 2*M, ROW_H, fill=1, stroke=0)
                    for idx, h in enumerate(HDRS): draw_ar(cv, COL_X[idx] + 3, y_pos - 12, h, size=8, color=GOLD)
                    return y_pos - ROW_H
                y = draw_table_header(c, y)
                for idx, p in enumerate(payments):
                    if y < M + 75:
                        c.showPage(); page_num += 1; draw_header(c, page_num)
                        y = H - 158; y = draw_table_header(c, y)
                    row_color = ROW_EVEN if idx % 2 == 0 else ROW_ALT
                    c.setFillColor(row_color); c.setStrokeColor(BORDER_CLR); c.setLineWidth(0.25)
                    c.rect(M, y - ROW_H, W - 2*M, ROW_H, fill=1, stroke=1)
                    due_date  = p.due_date.strftime('%Y-%m-%d') if isinstance(p.due_date, datetime.datetime) else str(p.due_date or "—")
                    paid_date = p.paid_date.strftime('%Y-%m-%d') if isinstance(p.paid_date, datetime.datetime) else "—"
                    status_lbl = "مدفوع ✓" if p.is_paid else "غير مدفوع"
                    status_fg  = PAID_COLOR if p.is_paid else UNPAID_CLR
                    note_short = (p.note or "").split("|")[0].strip()[:28]
                    txt_clr    = colors.HexColor("#1a2e1b")
                    draw_ar(c, COL_X[0]+3, y-12, f"{p.cycle_number or '-'}/{p.installment_number or '-'}", size=8, color=txt_clr)
                    draw_ar(c, COL_X[1]+3, y-12, f"{p.amount or 0:,.0f}", size=8, color=txt_clr)
                    draw_ar(c, COL_X[2]+3, y-12, due_date, size=7, color=txt_clr)
                    draw_ar(c, COL_X[3]+3, y-12, paid_date, size=7, color=txt_clr)
                    draw_ar(c, COL_X[4]+3, y-12, status_lbl, size=8, color=status_fg)
                    draw_ar(c, COL_X[5]+3, y-12, note_short, size=7, color=GREY_TXT)
                    y -= ROW_H
                if y < M + 58: c.showPage(); page_num += 1; draw_header(c, page_num); y = H - 160
                y -= 12; c.setStrokeColor(GOLD); c.setLineWidth(1); c.line(M, y, W - M, y); y -= 6
                c.setFillColor(DARK_GREEN); c.roundRect(M, y - 50, W - 2*M, 50, 6, fill=1, stroke=0)
                blk_w = (W - 2*M) / 3
                summary = [("إجمالي الأقساط", f"{total_all:,.0f} ريال", colors.white), ("إجمالي المسدّد", f"{total_paid:,.0f} ريال", colors.HexColor("#69f0ae")), ("المتبقي", f"{total_due:,.0f} ريال", colors.HexColor("#ff8a80"))]
                for idx, (lbl, val, clr) in enumerate(summary):
                    bx = M + idx * blk_w
                    if idx > 0: c.setStrokeColor(colors.HexColor("#1b5e20")); c.setLineWidth(0.4); c.line(bx, y - 8, bx, y - 44)
                    draw_ar(c, bx + 8, y - 18, lbl, size=8, color=colors.HexColor("#a5d6a7"))
                    draw_ar(c, bx + 8, y - 36, val, size=13, color=clr)
                c.setFont(font_name, 7); c.setFillColor(GREY_TXT)
                c.drawCentredString(W / 2, M + 8, reshape_text(f"صادر تلقائياً من منظومة {company_name} — {datetime.date.today().strftime('%Y-%m-%d')}"))

                c.save()
                ModernDialog(self, "نجاح", f"تم حفظ التقرير بنجاح في:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", str(e)).exec()
    def generate_winners_report(self):
        """Generates an Excel report of all winners."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير الفائزين", "winners_report.xlsx", "Excel Files (*.xlsx)")
            if not file_path: return
            
            query = self.db.query(db_mod.Winner)
            if hasattr(self, 'rep_win_type'):
                win_filter = self.rep_win_type.currentText()
                if win_filter != "الكل":
                    query = query.filter(db_mod.Winner.draw_type.contains(win_filter))
            
            winners = query.order_by(db_mod.Winner.draw_date.desc()).all()
            data = [{
                "رقم المشترك الفائز": w.subscriber_number,
                "تاريخ السحب": (w.draw_date.strftime("%Y-%m-%d %H:%M") if w.draw_date else ""),
                "نوع الجائزة": w.draw_type or "سحب عام"
            } for w in winners]
            df = pd.DataFrame(data)
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='الفائزون', index=False, startrow=8)
                workbook = writer.book
                worksheet = writer.sheets['الفائزون']
                
                company_name = self._get_setting("company_name", "هكبة المليون")
                company_logo_path = self._get_setting("company_logo_path", "")

                setup_excel_header(
                    workbook=workbook, worksheet=worksheet, df=df,
                    title="تقرير الفائزين بالسحوبات", subtitle="",
                    company_name=company_name, company_logo_path=company_logo_path,
                    start_row=8
                )

            ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()
    def generate_categories_report(self):
        """Generates a PDF summary report of categories."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, reshape_text("حفظ ملخص الفئات"), "categories_summary.pdf", reshape_text("PDF Files (*.pdf)"))
            if not file_path: return

            c = canvas.Canvas(file_path, pagesize=A4); width, height = A4
            font_name = register_arabic_font()
            try: c.setFont(font_name, 12)
            except: c.setFont('Helvetica', 12)
            
            company_name = self._get_setting("company_name", "هكبة المليون")
            company_legal_name = self._get_setting("company_legal_name", "الاسبوعية")
            company_record = self._get_setting("company_commercial_record", "")
            company_logo_path = self._get_setting("company_logo_path", "")

            draw_pdf_header(
                c=c, title="ملخص الفئات والمبالغ", subtitle="", page_num=1,
                W=width, H=height, M=36, font_name=font_name,
                company_name=company_name, company_legal_name=company_legal_name,
                company_record=company_record, company_logo_path=company_logo_path
            )
            
            y = height - 160

            cats = self.db.query(db_mod.Category).all()
            if not cats:
                c.setFont(font_name, 12)
                c.drawCentredString(width / 2, y, reshape_text("لا توجد فئات مسجلة في النظام."))
                c.save()
                ModernDialog(self, reshape_text("تنبيه"), reshape_text("لا توجد فئات مسجلة، لم يتم إنشاء التقرير.")).exec()
                return

            headers = [reshape_text("اسم الفئة"), reshape_text("المبلغ اليومي"), reshape_text("عدد المشتركين"), reshape_text("إجمالي المبالغ")]
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
            start_date = datetime.datetime.combine(self.rep_date_start.date().toPyDate(), datetime.time.min)
            end_date = datetime.datetime.combine(self.rep_date_end.date().toPyDate(), datetime.time.max)
            status = self.rep_status.currentText()
            cat_name = self.rep_cat_filter.currentData()

            query = self.db.query(db_mod.Payment).filter(db_mod.Payment.due_date.between(start_date, end_date))
            if status == "مدفوع":
                query = query.filter(db_mod.Payment.is_paid == True)
            elif status == "غير مدفوع":
                query = query.filter(db_mod.Payment.is_paid == False)

            if cat_name:
                query = query.join(db_mod.Subscriber, db_mod.Payment.subscriber_id == db_mod.Subscriber.id).filter(db_mod.Subscriber.category == cat_name)

            # جلب المدفوعات مع المشتركين في استعلام واحد لتجنب مشكلة N+1
            payments = (
                query
                .join(db_mod.Subscriber, db_mod.Payment.subscriber_id == db_mod.Subscriber.id, isouter=True)
                .add_columns(db_mod.Subscriber.name.label('sub_name'), db_mod.Subscriber.category.label('sub_cat'))
                .order_by(db_mod.Payment.cycle_number.desc(), db_mod.Payment.installment_number.desc(), db_mod.Payment.due_date.desc())
                .all()
            )
            data = []
            for row in payments:
                p = row[0]
                sub_name = row.sub_name or "غير معروف"
                sub_cat  = row.sub_cat  or "-"
                data.append({
                    "المشترك": sub_name,
                    "الفئة": sub_cat,
                    "التاريخ": (p.due_date.strftime("%Y-%m-%d") if p.due_date else "-"),
                    "المبلغ": p.amount,
                    "القسط": p.installment_number,
                    "الحالة": "مدفوع" if p.is_paid else "غير مدفوع",
                    "الملاحظة": p.note or "-"
                })

            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير الأقساط", "custom_payments_report.xlsx", "Excel Files (*.xlsx)")
            if not file_path:
                return

            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='الأقساط', index=False, startrow=8)
                workbook = writer.book
                worksheet = writer.sheets['الأقساط']
                
                company_name = self._get_setting("company_name", "هكبة المليون")
                company_logo_path = self._get_setting("company_logo_path", "")

                setup_excel_header(
                    workbook=workbook, worksheet=worksheet, df=df,
                    title="التقرير المخصص للأقساط", subtitle=f"الفترة: {start_date.strftime('%Y-%m-%d')} إلى {end_date.strftime('%Y-%m-%d')}",
                    company_name=company_name, company_logo_path=company_logo_path,
                    start_row=8
                )
            ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", str(e)).exec()
    def generate_overall_financial_summary_report(self):
        """Generates an Excel report summarizing overall financial stats."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ ملخص مالي عام", "overall_financial_summary.xlsx", "Excel Files (*.xlsx)")
            if not file_path: return

            total_expected = self.db.query(func.sum(db_mod.Payment.amount)).scalar() or 0
            total_collected = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.is_paid == True).scalar() or 0
            total_remaining = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.is_paid == False).scalar() or 0
            total_expenses = self.db.query(func.sum(db_mod.Expense.amount)).scalar() or 0
            net_cash = total_collected - total_expenses

            data = {
                "البيان": [
                    "إجمالي رأس المال المتوقع",
                    "المبالغ المحصلة (الإيرادات)",
                    "النفقات التشغيلية (المصاريف)",
                    "صافي السيولة النقدية",
                    "الأقساط غير المسددة (المتأخرات)"
                ],
                "المبلغ (ر.ي)": [
                    total_expected,
                    total_collected,
                    total_expenses,
                    net_cash,
                    total_remaining
                ]
            }
            df = pd.DataFrame(data)

            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='ملخص مالي', index=False, startrow=8)
                workbook = writer.book
                worksheet = writer.sheets['ملخص مالي']
                
                company_name = self._get_setting("company_name", "هكبة المليون")
                company_logo_path = self._get_setting("company_logo_path", "")

                setup_excel_header(
                    workbook=workbook, worksheet=worksheet, df=df,
                    title="الملخص المالي العام", subtitle="",
                    company_name=company_name, company_logo_path=company_logo_path,
                    start_row=8
                )

            ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", str(e)).exec()
    def generate_subscriber_contact_list_report(self, fmt):
        """Generates a list of subscribers with contact info in Excel or PDF."""
        try:
            subs = self.db.query(db_mod.Subscriber).all()
            data = [{
                "الاسم": s.name,
                "الهاتف": s.phone,
                "رقم الحساب": s.subscriber_number,
                "الفئة": s.category
            } for s in subs]
            df = pd.DataFrame(data)

            if fmt == "excel":
                file_path, _ = QFileDialog.getSaveFileName(self, "حفظ قائمة المشتركين (Excel)", "subscriber_contact_list.xlsx", "Excel Files (*.xlsx)")
                if not file_path:
                    return
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='المشتركون', index=False, startrow=8)
                    workbook = writer.book
                    worksheet = writer.sheets['المشتركون']
                    
                    company_name = self._get_setting("company_name", "هكبة المليون")
                    company_logo_path = self._get_setting("company_logo_path", "")

                    setup_excel_header(
                        workbook=workbook, worksheet=worksheet, df=df,
                        title="قائمة المشتركين", subtitle="",
                        company_name=company_name, company_logo_path=company_logo_path,
                        start_row=8
                    )
                ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
            else: # PDF
                file_path, _ = QFileDialog.getSaveFileName(self, reshape_text("حفظ قائمة المشتركين (PDF)"), "subscriber_contact_list.pdf", reshape_text("PDF Files (*.pdf)"))
                if not file_path:
                    return
                c = canvas.Canvas(file_path, pagesize=A4)
                width, height = A4
                font_name = register_arabic_font()
                c.setFont(font_name, 10)

                company_name = self._get_setting("company_name", "هكبة المليون")
                company_legal_name = self._get_setting("company_legal_name", "الاسبوعية")
                company_record = self._get_setting("company_commercial_record", "")
                company_logo_path = self._get_setting("company_logo_path", "")

                page_num = 1
                draw_pdf_header(
                    c=c, title="قائمة المشتركين", subtitle="", page_num=page_num,
                    W=width, H=height, M=36, font_name=font_name,
                    company_name=company_name, company_legal_name=company_legal_name,
                    company_record=company_record, company_logo_path=company_logo_path
                )
                
                y = height - 160
                headers = [reshape_text("الاسم"), reshape_text("الهاتف"), reshape_text("رقم الحساب"), reshape_text("الفئة")]
                col_x = [50, 180, 310, 440]
                for i, h in enumerate(headers):
                    c.drawString(col_x[i], y, h)
                c.line(50, y-5, width-50, y-5)
                y -= 25

                for s in subs:
                    if y < 50:
                        c.showPage()
                        page_num += 1
                        draw_pdf_header(
                            c=c, title="قائمة المشتركين", subtitle="", page_num=page_num,
                            W=width, H=height, M=36, font_name=font_name,
                            company_name=company_name, company_legal_name=company_legal_name,
                            company_record=company_record, company_logo_path=company_logo_path
                        )
                        y = height - 160
                        c.setFont(font_name, 10)
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

            if expense_category != "الكل":
                query = query.filter(db_mod.Expense.category == expense_category)
            
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
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير المصاريف", "detailed_expenses_report.xlsx", "Excel Files (*.xlsx)")
            if not file_path: return
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='المصاريف', index=False, startrow=8)
                workbook = writer.book
                worksheet = writer.sheets['المصاريف']
                
                company_name = self._get_setting("company_name", "هكبة المليون")
                company_logo_path = self._get_setting("company_logo_path", "")

                subtitle = f"من: {start_date.strftime('%Y-%m-%d')} إلى: {end_date.strftime('%Y-%m-%d')}"
                if expense_category != "الكل": subtitle += f" | التصنيف: {expense_category}"

                setup_excel_header(
                    workbook=workbook, worksheet=worksheet, df=df,
                    title="تقرير المصاريف", subtitle=subtitle,
                    company_name=company_name, company_logo_path=company_logo_path,
                    start_row=8
                )
                
                total_amount = df["المبلغ (ر.ي)"].sum() if not df.empty else 0
                worksheet.write(len(df) + 9, 0, "الإجمالي الكلي:")
                worksheet.write(len(df) + 9, 1, total_amount)

            ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", str(e)).exec()
    def upload_new_report(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "اختر التقرير للرفع", "", "All Files (*);;PDF Files (*.pdf);;Excel Files (*.xlsx *.xls)")
        if file_path:
            try:
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                else:
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                upload_dir = os.path.join(base_dir, "uploaded_reports")
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
            except PermissionError: ModernDialog(self, "خطأ", "خطأ في الأذونات. لا يمكن الكتابة في مجلد 'uploaded_reports'.").exec()
            except Exception as e: ModernDialog(self, "خطأ", f"فشل الرفع: {e}").exec()
    def refresh_uploaded_reports(self):
        self.list_uploaded_reports.clear()
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        upload_dir = os.path.join(base_dir, "uploaded_reports")
        if os.path.exists(upload_dir):
            files = os.listdir(upload_dir)
            for f in files:
                try:
                    file_path = os.path.join(upload_dir, f)
                    stat = os.stat(file_path)
                    upload_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                    size_kb = stat.st_size / 1024
                    display_text = f"{f}  |  (تاريخ الرفع: {upload_time}, الحجم: {size_kb:.1f} KB)"
                    self.list_uploaded_reports.addItem(QListWidgetItem(QIcon.fromTheme("document-new"), display_text))
                except Exception: self.list_uploaded_reports.addItem(QListWidgetItem(QIcon.fromTheme("document-new"), f)) # Fallback
    def open_uploaded_file(self, filename):
        # If a full display text was passed (e.g. "name  |  (meta)"), extract the real filename
        if isinstance(filename, str) and "  |" in filename:
            filename = filename.split("  |")[0].strip()
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        file_path = os.path.abspath(os.path.join(base_dir, "uploaded_reports", filename))
        # التحقق من وجود الملف قبل محاولة فتحه
        if os.path.isfile(file_path):
            try:
                if sys.platform == "win32": os.startfile(file_path)
                else: subprocess.run(["open", file_path] if sys.platform == "darwin" else ["xdg-open", file_path])
            except Exception as e: ModernDialog(self, "خطأ", f"فشل فتح الملف: {e}").exec()
        else:
            ModernDialog(self, "تنبيه", f"الملف '{filename}' غير موجود أو تم حذفه.").exec()
            self.refresh_uploaded_reports()
    def show_upload_context_menu(self, pos):
        item = self.list_uploaded_reports.itemAt(pos)
        if not item: return
        
        filename = item.text().split("  |")[0].strip() # استخلاص اسم الملف فقط
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
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                else:
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                file_to_delete = os.path.join(base_dir, "uploaded_reports", filename)
                if os.path.exists(file_to_delete):
                    os.remove(file_to_delete)
                self.refresh_uploaded_reports()
            except Exception as e: ModernDialog(self, "خطأ", str(e)).exec()
            
    def generate_staff_report(self):
        """Generates an Excel report of staff activity (payments collected)."""
        try:
            start_date = datetime.datetime.combine(self.rep_staff_date_start.date().toPyDate(), datetime.time.min)
            end_date = datetime.datetime.combine(self.rep_staff_date_end.date().toPyDate(), datetime.time.max)
            staff_id = self.rep_staff_cb.currentData()

            query = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.paid_date.between(start_date, end_date),
                db_mod.Payment.is_paid == True
            )

            if staff_id:
                query = query.filter(db_mod.Payment.staff_id == staff_id)
            
            payments = query.order_by(db_mod.Payment.paid_date.desc()).all()
            
            data = []
            for p in payments:
                staff = self.db.get(db_mod.Staff, p.staff_id) if p.staff_id else None
                sub = self.db.get(db_mod.Subscriber, p.subscriber_id) if p.subscriber_id else None
                
                data.append({
                    "الموظف المحصل": staff.name if staff else "غير محدد",
                    "المشترك": sub.name if sub else "غير محدد",
                    "رقم القسط": p.installment_number,
                    "المبلغ (ر.ي)": p.amount,
                    "تاريخ التحصيل": p.paid_date.strftime("%Y-%m-%d %H:%M") if p.paid_date else "-",
                    "حالة التسوية": "تمت التسوية" if p.is_staff_settled else "غير مسوى"
                })
            
            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير الموظفين", "staff_report.xlsx", "Excel Files (*.xlsx)")
            if not file_path: return
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='تحصيلات الموظفين', index=False, startrow=8)
                workbook = writer.book
                worksheet = writer.sheets['تحصيلات الموظفين']

                company_name = self._get_setting("company_name", "هكبة المليون")
                company_logo_path = self._get_setting("company_logo_path", "")

                setup_excel_header(
                    workbook=workbook, worksheet=worksheet, df=df,
                    title="تقرير عمليات الموظفين", subtitle=f"الفترة: {start_date.strftime('%Y-%m-%d')} إلى {end_date.strftime('%Y-%m-%d')}",
                    company_name=company_name, company_logo_path=company_logo_path,
                    start_row=8
                )
                
                # Add summary
                total_collected = df["المبلغ (ر.ي)"].sum() if not df.empty else 0
                worksheet.write(len(df) + 9, 0, "إجمالي التحصيلات:")
                worksheet.write(len(df) + 9, 3, total_collected)

            ModernDialog(self, "نجاح", f"تم تصدير التقرير بنجاح إلى:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", str(e)).exec()

    def on_qual_category_changed(self):
        """Update cycle numbers dynamically based on the selected category."""
        if not hasattr(self, 'rep_qual_cycle') or not hasattr(self, 'rep_qual_category'):
            return

        sel_cat_name = self.rep_qual_category.currentData()

        self.rep_qual_cycle.blockSignals(True)
        self.rep_qual_cycle.clear()
        self.rep_qual_cycle.addItem("الدورة الحالية (تلقائي)", "auto")

        if sel_cat_name:
            # Load cycles for the specific selected category
            cat_obj = self.db.query(db_mod.Category).filter(db_mod.Category.name == sel_cat_name).first()
            max_cycles = cat_obj.max_cycles if (cat_obj and cat_obj.max_cycles) else 10
            for cyc in range(1, max_cycles + 1):
                self.rep_qual_cycle.addItem(f"الدورة رقم {cyc}", cyc)
        else:
            # All categories: show union of all cycles (max of all max_cycles)
            all_cats = self.db.query(db_mod.Category).all()
            if all_cats:
                max_cycles = max((c.max_cycles or 10) for c in all_cats)
            else:
                max_cycles = 10
            for cyc in range(1, max_cycles + 1):
                self.rep_qual_cycle.addItem(f"الدورة رقم {cyc}", cyc)

        self.rep_qual_cycle.blockSignals(False)
        self.refresh_qualified_draw_table()


    def get_qualified_subscribers_list(self):
        sel_draw = self.rep_qual_draw_type.currentText() if hasattr(self, 'rep_qual_draw_type') else "الكل"
        sel_cat = self.rep_qual_category.currentData() if hasattr(self, 'rep_qual_category') else None
        sel_cycle = self.rep_qual_cycle.currentData() if hasattr(self, 'rep_qual_cycle') else "auto"
        search_txt = self.rep_qual_search.text().strip().lower() if hasattr(self, 'rep_qual_search') else ""
        
        query = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted")
        if sel_cat:
            query = query.filter(db_mod.Subscriber.category == sel_cat)
            
        all_subs = query.all()
        today = datetime.datetime.now()
        
        setting_inc = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "incentive_max_late_installments").first()
        max_late_allowed = int(setting_inc.value) if (setting_inc and setting_inc.value.isdigit()) else 1
        
        result = []
        for sub in all_subs:
            sub_name = sub.name or "غير محدد"
            sub_phone = sub.phone or "-"
            sub_cat = sub.category or "-"
            sub_num = sub.subscriber_number or "-"
            
            if search_txt:
                match = (search_txt in sub_name.lower()) or (search_txt in sub_phone.lower()) or (search_txt in sub_num.lower())
                if not match:
                    continue
                    
            fin_status = db_mod.calculate_financial_status(sub, self.db)
            is_disciplined = (fin_status not in ["late", "suspended"])
            
            if sel_cycle != "auto" and isinstance(sel_cycle, int):
                target_cycle = sel_cycle
            else:
                active_p = self.db.query(db_mod.Payment).filter(
                    db_mod.Payment.subscriber_id == sub.id,
                    db_mod.Payment.due_date <= today
                ).order_by(db_mod.Payment.due_date.desc()).first()
                target_cycle = active_p.cycle_number if active_p else 1
                
            payments = self.db.query(db_mod.Payment).filter(
                db_mod.Payment.subscriber_id == sub.id,
                db_mod.Payment.cycle_number == target_cycle
            ).order_by(db_mod.Payment.installment_number.asc()).all()
            
            cat_obj = self.db.query(db_mod.Category).filter(db_mod.Category.name == sub.category).first()
            max_inst = cat_obj.max_installments if cat_obj else 12
            cat_amount = cat_obj.amount if cat_obj else 0.0
            
            total_expected_cycle = cat_amount * max_inst
            total_paid_cycle = sum(p.amount for p in payments if p.is_paid) if payments else 0.0
            
            pay_ratio = (total_paid_cycle / total_expected_cycle * 100) if total_expected_cycle > 0 else 0.0
            
            is_cycle_finished = (total_paid_cycle >= total_expected_cycle - 0.01) and (all(p.is_paid for p in payments) if payments else False)
            last_p_date = payments[-1].due_date if payments else today
            is_date_reached = (today >= last_p_date)
            
            is_incentive = True
            has_paid_something = False
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
                
            won_weekly = self.db.query(db_mod.Winner).filter(
                db_mod.Winner.subscriber_number == sub_num,
                db_mod.Winner.draw_type.contains("القرعة الاسبوعية")
            ).first() is not None
            
            qual_weekly = is_disciplined and is_cycle_finished and is_date_reached and (not won_weekly)
            qual_incentive = is_disciplined and is_incentive and has_paid_something
            qual_grand = is_disciplined and is_cycle_finished and is_date_reached
            
            if sel_draw == "القرعة الاسبوعية":
                is_qualified = qual_weekly
                draw_label = "القرعة الاسبوعية"
            elif sel_draw == "الجائزة التحفيزية":
                is_qualified = qual_incentive
                draw_label = "الجائزة التحفيزية"
            elif sel_draw == "الجائزة الكبرى":
                is_qualified = qual_grand
                draw_label = "الجائزة الكبرى"
            else:
                is_qualified = qual_weekly or qual_incentive or qual_grand
                draw_label = "كل السحوبات"
                
            result.append({
                "sub": sub,
                "name": sub_name,
                "phone": sub_phone,
                "category": sub_cat,
                "number": sub_num,
                "draw_type": draw_label,
                "cycle": target_cycle,
                "pay_ratio": pay_ratio,
                "total_paid": total_paid_cycle,
                "total_expected": total_expected_cycle,
                "fin_status": fin_status,
                "is_qualified": is_qualified
            })
            
        return result

    def refresh_qualified_draw_table(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all()
        
        all_items = self.get_qualified_subscribers_list()
        
        # Apply qualification status filter
        status_filter = self.rep_qual_status_filter.currentData() if hasattr(self, 'rep_qual_status_filter') else "all"
        if status_filter == "qualified":
            items = [it for it in all_items if it["is_qualified"]]
        elif status_filter == "not_qualified":
            items = [it for it in all_items if not it["is_qualified"]]
        else:
            items = all_items
            
        self.table_rep_draw_qualified.setRowCount(len(items))
        
        for i, item in enumerate(items):
            name_cell = QTableWidgetItem(item["name"])
            name_cell.setData(Qt.ItemDataRole.UserRole, item["sub"].id)
            
            self.table_rep_draw_qualified.setItem(i, 0, name_cell)
            self.table_rep_draw_qualified.setItem(i, 1, QTableWidgetItem(item["phone"]))
            self.table_rep_draw_qualified.setItem(i, 2, QTableWidgetItem(item["category"]))
            self.table_rep_draw_qualified.setItem(i, 3, QTableWidgetItem(item["number"]))
            self.table_rep_draw_qualified.setItem(i, 4, QTableWidgetItem(item["draw_type"]))
            self.table_rep_draw_qualified.setItem(i, 5, QTableWidgetItem(f"دورة {item['cycle']}"))
            self.table_rep_draw_qualified.setItem(i, 6, QTableWidgetItem(f"{item['pay_ratio']:.1f}%"))
            
            fin_st = item["fin_status"]
            fin_lbl = "ملتزم" if fin_st == "committed" else ("بانتظار الدفع" if fin_st == "pending_payment" else ("متأخر" if fin_st == "late" else "موقوف"))
            fin_item = QTableWidgetItem(fin_lbl)
            if fin_st in ["late", "suspended"]:
                fin_item.setForeground(QColor("#ef4444"))
                fin_item.setFont(QFont("Tajawal", 9, QFont.Weight.Bold))
            else:
                fin_item.setForeground(QColor("#16a34a"))
            self.table_rep_draw_qualified.setItem(i, 7, fin_item)
            
            qual_w = QWidget()
            q_lay = QHBoxLayout(qual_w)
            q_lay.setContentsMargins(4, 2, 4, 2)
            q_lbl = QLabel()
            q_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if item["is_qualified"]:
                q_lbl.setText("🟢 مؤهل للدخول")
                q_lbl.setStyleSheet("background-color: #dcfce7; color: #15803d; font-weight: bold; border-radius: 4px; padding: 4px 8px;")
            else:
                q_lbl.setText("🔴 غير مؤهل")
                q_lbl.setStyleSheet("background-color: #fee2e2; color: #b91c1c; font-weight: bold; border-radius: 4px; padding: 4px 8px;")
            q_lay.addWidget(q_lbl)
            self.table_rep_draw_qualified.setCellWidget(i, 8, qual_w)

    def export_qualified_draw_report(self, fmt):
        try:
            items = self.get_qualified_subscribers_list()
            qual_items = [it for it in items if it["is_qualified"]]
            
            sel_draw = self.rep_qual_draw_type.currentText() if hasattr(self, 'rep_qual_draw_type') else "الكل"
            sel_cat = self.rep_qual_category.currentText() if (hasattr(self, 'rep_qual_category') and self.rep_qual_category.currentData()) else "كل الفئات"
            sel_cycle_text = self.rep_qual_cycle.currentText() if hasattr(self, 'rep_qual_cycle') else "التلقائية"
            
            report_title = f"تقرير المشتركين المؤهلين للسحب ({sel_draw})"
            subtitle = f"الفئة: {sel_cat} | الدورة: {sel_cycle_text} | عدد المؤهلين: {len(qual_items)}"
            
            if fmt == "excel":
                default_name = f"qualified_draw_subscribers_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
                file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير المؤهلين (Excel)", default_name, "Excel Files (*.xlsx)")
                if not file_path: return
                
                data = []
                for it in qual_items:
                    data.append({
                        "اسم المشترك": it["name"],
                        "رقم الهاتف": it["phone"],
                        "الفئة المالية": it["category"],
                        "رقم الحساب": it["number"],
                        "نوع السحب / الجائزة": it["draw_type"],
                        "رقم الدورة": f"دورة {it['cycle']}",
                        "المبلغ المسدد بالدورة": it["total_paid"],
                        "المبلغ المطلوب بالدورة": it["total_expected"],
                        "نسبة السداد": f"{it['pay_ratio']:.1f}%",
                        "حالة الأهلية": "مؤهل للدخول ✓"
                    })
                    
                df = pd.DataFrame(data)
                company_name = self._get_setting("company_name", "هكبة المليون")
                company_logo_path = self._get_setting("company_logo_path", "")
                
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='المؤهلون للسحب', index=False, startrow=8)
                    workbook = writer.book
                    worksheet = writer.sheets['المؤهلون للسحب']
                    
                    setup_excel_header(
                        workbook=workbook, worksheet=worksheet, df=df,
                        title=report_title, subtitle=subtitle,
                        company_name=company_name, company_logo_path=company_logo_path,
                        start_row=8
                    )
                    
                ModernDialog(self, "نجاح", f"تم حفظ التقرير بنجاح في:\n{file_path}").exec()
                
            else: # PDF
                default_name = f"qualified_draw_subscribers_{datetime.date.today().strftime('%Y%m%d')}.pdf"
                file_path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير المؤهلين (PDF)", default_name, "PDF Files (*.pdf)")
                if not file_path: return
                
                c = canvas.Canvas(file_path, pagesize=A4)
                W, H = A4
                M = 36
                font_name = register_arabic_font()
                
                GOLD        = colors.HexColor("#c9a84c")
                DARK_GREEN  = colors.HexColor("#052109")
                BORDER_CLR  = colors.HexColor("#c8e6c9")
                ROW_EVEN    = colors.white
                ROW_ALT     = colors.HexColor("#f1f8f1")
                
                company_name       = self._get_setting("company_name", "هكبة المليون")
                company_legal_name = self._get_setting("company_legal_name", "الاسبوعية")
                company_record     = self._get_setting("company_commercial_record", "")
                company_logo_path  = self._get_setting("company_logo_path", "")
                
                def draw_ar(cv, x, y, text, size=9, color=colors.black):
                    cv.setFont(font_name, size)
                    cv.setFillColor(color)
                    cv.drawString(x, y, reshape_text(str(text)))
                    
                page_num = 1
                draw_pdf_header(
                    c=c, title=report_title, subtitle=subtitle, page_num=page_num,
                    W=W, H=H, M=M, font_name=font_name,
                    company_name=company_name, company_legal_name=company_legal_name,
                    company_record=company_record, company_logo_path=company_logo_path
                )
                
                y = H - 150
                COL_X = [M, M+120, M+200, M+280, M+370, M+450]
                HDRS  = ["الاسم", "الهاتف", "الفئة", "رقم الحساب", "نوع السحب", "الدورة"]
                ROW_H = 18
                
                def draw_tbl_header(cv, y_pos):
                    cv.setFillColor(DARK_GREEN)
                    cv.rect(M, y_pos - ROW_H, W - 2*M, ROW_H, fill=1, stroke=0)
                    for idx, h in enumerate(HDRS):
                        draw_ar(cv, COL_X[idx] + 4, y_pos - 13, h, size=8, color=GOLD)
                    return y_pos - ROW_H
                    
                y = draw_tbl_header(c, y)
                for idx, it in enumerate(qual_items):
                    if y < M + 60:
                        c.showPage(); page_num += 1
                        draw_pdf_header(
                            c=c, title=report_title, subtitle=subtitle, page_num=page_num,
                            W=W, H=H, M=M, font_name=font_name,
                            company_name=company_name, company_legal_name=company_legal_name,
                            company_record=company_record, company_logo_path=company_logo_path
                        )
                        y = H - 150
                        y = draw_tbl_header(c, y)
                        
                    row_color = ROW_EVEN if idx % 2 == 0 else ROW_ALT
                    c.setFillColor(row_color); c.setStrokeColor(BORDER_CLR); c.setLineWidth(0.25)
                    c.rect(M, y - ROW_H, W - 2*M, ROW_H, fill=1, stroke=1)
                    
                    draw_ar(c, COL_X[0]+4, y-13, it["name"][:20], size=8)
                    draw_ar(c, COL_X[1]+4, y-13, it["phone"], size=8)
                    draw_ar(c, COL_X[2]+4, y-13, it["category"], size=8)
                    draw_ar(c, COL_X[3]+4, y-13, it["number"], size=8)
                    draw_ar(c, COL_X[4]+4, y-13, it["draw_type"], size=8)
                    draw_ar(c, COL_X[5]+4, y-13, f"دورة {it['cycle']}", size=8)
                    y -= ROW_H
                    
                c.save()
                ModernDialog(self, "نجاح", f"تم حفظ التقرير بنجاح في:\n{file_path}").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", str(e)).exec()

    def save_qualified_report_to_documents(self):
        try:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            upload_dir = os.path.join(base_dir, "uploaded_reports")
            if not os.path.exists(upload_dir): os.makedirs(upload_dir)
            
            sel_draw = self.rep_qual_draw_type.currentText() if hasattr(self, 'rep_qual_draw_type') else "عام"
            filename = f"تقرير_المؤهلين_{sel_draw}_{datetime.date.today().strftime('%Y%m%d_%H%M')}.xlsx"
            dest_path = os.path.join(upload_dir, filename)
            
            items = [it for it in self.get_qualified_subscribers_list() if it["is_qualified"]]
            data = []
            for it in items:
                data.append({
                    "اسم المشترك": it["name"],
                    "رقم الهاتف": it["phone"],
                    "الفئة المالية": it["category"],
                    "رقم الحساب": it["number"],
                    "نوع السحب / الجائزة": it["draw_type"],
                    "رقم الدورة": f"دورة {it['cycle']}",
                    "المبلغ المسدد بالدورة": it["total_paid"],
                    "نسبة السداد": f"{it['pay_ratio']:.1f}%",
                    "حالة الأهلية": "مؤهل للدخول ✓"
                })
            df = pd.DataFrame(data)
            company_name = self._get_setting("company_name", "هكبة المليون")
            company_logo_path = self._get_setting("company_logo_path", "")
            
            with pd.ExcelWriter(dest_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='المؤهلون للسحب', index=False, startrow=8)
                workbook = writer.book
                worksheet = writer.sheets['المؤهلون للسحب']
                setup_excel_header(
                    workbook=workbook, worksheet=worksheet, df=df,
                    title=f"تقرير المشتركين المؤهلين بالسحب ({sel_draw})",
                    subtitle=f"عدد المؤهلين: {len(items)}",
                    company_name=company_name, company_logo_path=company_logo_path,
                    start_row=8
                )
                
            self.refresh_uploaded_reports()
            ModernDialog(self, "نجاح", f"تم حفظ التقرير في مركز المستندات المرفوعة باسم:\n{filename}").exec()
        except Exception as err:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء حفظ المستند: {err}").exec()
