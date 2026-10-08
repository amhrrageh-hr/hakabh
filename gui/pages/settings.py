from sqlalchemy import func
from sqlalchemy.orm import Session
import sys
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
import security
from gui.utils import reshape_text, ServerWorker
from gui.dialogs import *

class SettingsMixin:
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
        

        # Add Category
        f1 = QFrame(); f1.setObjectName("StatCard"); v_lay1 = QVBoxLayout(f1)
        v_lay1.addWidget(QLabel("إضافة فئة جديدة"))
        form_cat = QFormLayout()
        self.en1 = QLineEdit(); self.en2 = QLineEdit(); self.en3 = QLineEdit()
        form_cat.addRow("اسم الفئة:", self.en1)
        form_cat.addRow("المبلغ اليومي:", self.en2)
        form_cat.addRow("مبلغ الجائزة:", self.en3)
        v_lay1.addLayout(form_cat)
        ba = QPushButton("إضافة فئة"); ba.setObjectName("PrimaryBtn"); ba.clicked.connect(self.add_category); v_lay1.addWidget(ba)
        
        # Categories header with action button
        cat_header_lay = QHBoxLayout()
        cat_title_lbl = QLabel("الفئات والمجموعات الحالية:")
        cat_title_lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #1e3a8a; margin-top: 10px;")
        cat_header_lay.addWidget(cat_title_lbl)
        cat_header_lay.addStretch()

        btn_top_batch = QPushButton("➕ فتح مجموعة / دفعة جديدة")
        btn_top_batch.setObjectName("PrimaryBtn")
        btn_top_batch.setStyleSheet("background-color: #059669; color: white; padding: 6px 14px; font-weight: bold; font-size: 12px;")
        btn_top_batch.clicked.connect(self.create_new_group_batch_from_top)
        cat_header_lay.addWidget(btn_top_batch)
        v_lay1.addLayout(cat_header_lay)

        self.table_cats = QTableWidget()
        self.table_cats.setColumnCount(5)
        self.table_cats.setHorizontalHeaderLabels(["اسم الفئة / المجموعة", "المبلغ اليومي", "مبلغ الجائزة", "إجمالي الأرقام", "إجراء"])
        self.table_cats.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_cats.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_cats.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_cats.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_cats.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table_cats.setColumnWidth(4, 270)
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

    def init_company_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("إعدادات الشركة والمستخدمين")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.company_settings_tabs = QTabWidget()

        # --- TAB 1: Company Info ---
        tab_info = QScrollArea()
        tab_info.setWidgetResizable(True)
        con_info = QWidget()
        lay_info = QVBoxLayout(con_info)
        lay_info.setContentsMargins(20, 20, 20, 20)
        lay_info.setSpacing(20)

        # Theme Switch
        theme_card = QFrame(); theme_card.setObjectName("StatCard"); theme_lay = QHBoxLayout(theme_card); theme_lay.setContentsMargins(20, 20, 20, 20)
        theme_lay.addWidget(QLabel("ثيم لوحة التحكم (داكن / فاتح):"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["الوضع الداكن", "الوضع الفاتح"])
        theme_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "admin_theme").first()
        if theme_setting and theme_setting.value == "light": self.theme_combo.setCurrentIndex(1)
        self.theme_combo.currentIndexChanged.connect(lambda i: self.set_theme("dark" if i == 0 else "light"))
        theme_lay.addStretch(); theme_lay.addWidget(self.theme_combo)
        lay_info.addWidget(theme_card)

        form = QFormLayout()
        self.company_name_input = QLineEdit()
        self.company_legal_name_input = QLineEdit()
        self.company_record_input = QLineEdit()
        self.company_est_date = QDateEdit()
        self.company_est_date.setCalendarPopup(True)
        self.company_est_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("اسم الشركة:", self.company_name_input)
        form.addRow("الاسم القانوني:", self.company_legal_name_input)
        form.addRow("السجل التجاري:", self.company_record_input)
        form.addRow("تاريخ التأسيس:", self.company_est_date)
        lay_info.addLayout(form)

        logo_layout = QHBoxLayout()
        self.company_logo_label = QLabel("لا يوجد شعار بعد")
        self.company_logo_label.setFixedSize(220, 220)
        self.company_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.company_logo_label.setStyleSheet("border: 1px solid #cbd5e1; background: #ffffff;")
        logo_layout.addWidget(self.company_logo_label)

        logo_button_layout = QVBoxLayout()
        logo_button_layout.setSpacing(10)
        btn_logo = QPushButton("إضافة شعار الشركة")
        btn_logo.setObjectName("PrimaryBtn")
        btn_logo.clicked.connect(self.select_company_logo)
        logo_button_layout.addWidget(btn_logo)
        logo_button_layout.addStretch()
        logo_layout.addLayout(logo_button_layout)
        lay_info.addLayout(logo_layout)

        btn_save_company = QPushButton("حفظ بيانات الشركة")
        btn_save_company.setObjectName("PrimaryBtn")
        btn_save_company.setFixedHeight(45)
        btn_save_company.clicked.connect(self.save_company_info)
        lay_info.addWidget(btn_save_company)
        lay_info.addStretch()

        tab_info.setWidget(con_info)
        self.company_settings_tabs.addTab(tab_info, "معلومات الشركة")

        # --- TAB 2: Users and Permissions ---
        tab_users = QScrollArea()
        tab_users.setWidgetResizable(True)
        con_users = QWidget()
        lay_users = QVBoxLayout(con_users)
        lay_users.setContentsMargins(20, 20, 20, 20)
        lay_users.setSpacing(20)

        header = QHBoxLayout()
        header.addWidget(QLabel("المستخدمين والصلاحيات"))
        header.addStretch()
        self.user_search_input = QLineEdit()
        self.user_search_input.setPlaceholderText("ابحث باسم الموظف أو الهاتف...")
        self.user_search_input.textChanged.connect(self.refresh_user_permissions_table)
        header.addWidget(self.user_search_input, 1)
        btn_add_user = QPushButton("إضافة مستخدم")
        btn_add_user.setObjectName("PrimaryBtn")
        btn_add_user.clicked.connect(self.add_user_from_settings)
        header.addWidget(btn_add_user)
        lay_users.addLayout(header)

        self.table_user_permissions = QTableWidget()
        self.table_user_permissions.setColumnCount(5)
        self.table_user_permissions.setHorizontalHeaderLabels([
            "اسم الموظف", "الهاتف", "رقم الموظف", "الصلاحية", "إجراء"
        ])
        self.table_user_permissions.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_user_permissions.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_user_permissions.setMinimumHeight(420)
        lay_users.addWidget(self.table_user_permissions)
        lay_users.addStretch()

        tab_users.setWidget(con_users)
        self.company_settings_tabs.addTab(tab_users, "المستخدمين والصلاحيات")

        # --- TAB 3: Backup and Restore ---
        tab_backup = QScrollArea(); tab_backup.setWidgetResizable(True)
        con_backup = QWidget(); lay_backup = QVBoxLayout(con_backup); lay_backup.setContentsMargins(20, 20, 20, 20); lay_backup.setSpacing(25)
        
        f_backup = QFrame(); f_backup.setObjectName("StatCard"); l_backup = QVBoxLayout(f_backup)
        l_backup.addWidget(QLabel("النسخ الاحتياطي واستعادة البيانات"))
        
        btn_backup = QPushButton("إنشاء نسخة احتياطية")
        btn_backup.setObjectName("PrimaryBtn")
        btn_backup.clicked.connect(self.create_backup)
        l_backup.addWidget(btn_backup)
        
        btn_restore = QPushButton("استعادة نسخة احتياطية")
        btn_restore.setObjectName("DangerBtn")
        btn_restore.clicked.connect(self.restore_backup)
        l_backup.addWidget(btn_restore)
        
        lay_backup.addWidget(f_backup)
        lay_backup.addStretch()
        tab_backup.setWidget(con_backup)
        self.company_settings_tabs.addTab(tab_backup, "النسخ الاحتياطي")

        # --- TAB 4: Server & Central Database Connection ---
        tab_db = QScrollArea()
        tab_db.setWidgetResizable(True)
        con_db = QWidget()
        lay_db = QVBoxLayout(con_db)
        lay_db.setContentsMargins(20, 20, 20, 20)
        lay_db.setSpacing(20)

        f_db = QFrame()
        f_db.setObjectName("StatCard")
        l_db = QVBoxLayout(f_db)
        l_db.setSpacing(15)

        title_db = QLabel("إعدادات الربط الشبكي وقاعدة البيانات المركزية (PostgreSQL / SQLite)")
        title_db.setStyleSheet("font-weight: bold; font-size: 16px; color: #1e293b;")
        l_db.addWidget(title_db)

        lbl_desc = QLabel(
            "تتيح لك هذه الشاشة تحويل التطبيق للعمل مع قاعدة بيانات مركزية PostgreSQL على سيرفر خارجي (VPS)\n"
            "أو العمل المحلي المفرد عبر ملف SQLite."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #64748b; font-size: 13px;")
        l_db.addWidget(lbl_desc)

        form_db = QFormLayout()
        form_db.setSpacing(12)

        self.db_mode_combo = QComboBox()
        self.db_mode_combo.addItems(["محلي (SQLite - hakbah.db)", "سيرفر خارجي (PostgreSQL مركزي)"])
        self.db_mode_combo.currentIndexChanged.connect(self.on_db_mode_changed)
        form_db.addRow("نوع قاعدة البيانات:", self.db_mode_combo)

        self.db_host_input = QLineEdit()
        self.db_host_input.setPlaceholderText("مثال: 123.45.67.89 أو db.hakbah.com")
        form_db.addRow("عنوان السيرفر (IP / Host):", self.db_host_input)

        self.db_port_input = QLineEdit("5432")
        self.db_port_input.setPlaceholderText("5432")
        form_db.addRow("منفذ الاتصال (Port):", self.db_port_input)

        self.db_name_input = QLineEdit("hakbah_db")
        self.db_name_input.setPlaceholderText("hakbah_db")
        form_db.addRow("اسم قاعدة البيانات:", self.db_name_input)

        self.db_user_input = QLineEdit("hakbah_user")
        self.db_user_input.setPlaceholderText("hakbah_user")
        form_db.addRow("اسم المستخدم:", self.db_user_input)

        self.db_pass_input = QLineEdit()
        self.db_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_pass_input.setPlaceholderText("كلمة المرور")
        form_db.addRow("كلمة المرور:", self.db_pass_input)

        l_db.addLayout(form_db)

        # Status indicator
        self.lbl_db_status = QLabel("حالة الاتصال الحالية: غير محدد")
        self.lbl_db_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #0284c7;")
        l_db.addWidget(self.lbl_db_status)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        btn_test_db = QPushButton("اختبار الاتصال بالسيرفر")
        btn_test_db.setObjectName("PrimaryBtn")
        btn_test_db.setStyleSheet("background-color: #3b82f6; color: white;")
        btn_test_db.clicked.connect(self.test_db_connection)
        btn_box.addWidget(btn_test_db)

        btn_save_db = QPushButton("حفظ وإعادة الاتصال")
        btn_save_db.setObjectName("PrimaryBtn")
        btn_save_db.setStyleSheet("background-color: #10b981; color: white;")
        btn_save_db.clicked.connect(self.save_db_connection)
        btn_box.addWidget(btn_save_db)

        l_db.addLayout(btn_box)
        lay_db.addWidget(f_db)
        lay_db.addStretch()

        tab_db.setWidget(con_db)
        self.company_settings_tabs.addTab(tab_db, "الاتصال بالسيرفر")

        # --- TAB 5: Hosting & Deployment Settings ---
        tab_hosting = QScrollArea()
        tab_hosting.setWidgetResizable(True)
        con_hosting = QWidget()
        lay_hosting = QVBoxLayout(con_hosting)
        lay_hosting.setContentsMargins(20, 20, 20, 20)
        lay_hosting.setSpacing(20)

        # --- Card 1: Hosting Provider ---
        f_provider = QFrame()
        f_provider.setObjectName("StatCard")
        l_provider = QVBoxLayout(f_provider)
        l_provider.setSpacing(12)

        title_hosting = QLabel("إعدادات الاستضافة ونشر الموقع")
        title_hosting.setStyleSheet("font-weight: bold; font-size: 16px; color: #1e293b;")
        l_provider.addWidget(title_hosting)

        lbl_hosting_desc = QLabel(
            "من هنا يمكنك ضبط إعدادات استضافة الموقع الإلكتروني (FastAPI Web App) على سيرفر خارجي أو منصة استضافة سحابية.\n"
            "عند حفظ الإعدادات يتم تخزينها محلياً ويمكنك استخدامها لاحقاً للنشر أو إدارة السيرفر."
        )
        lbl_hosting_desc.setWordWrap(True)
        lbl_hosting_desc.setStyleSheet("color: #64748b; font-size: 13px;")
        l_provider.addWidget(lbl_hosting_desc)

        form_hosting = QFormLayout()
        form_hosting.setSpacing(12)

        self.hosting_provider_combo = QComboBox()
        self.hosting_provider_combo.addItems([
            "VPS / سيرفر خاص (SSH)",
            "Render",
            "Railway",
            "Heroku",
            "DigitalOcean App Platform",
            "استضافة أخرى"
        ])
        self.hosting_provider_combo.currentIndexChanged.connect(self.on_hosting_provider_changed)
        form_hosting.addRow("منصة الاستضافة:", self.hosting_provider_combo)

        self.hosting_domain_input = QLineEdit()
        self.hosting_domain_input.setPlaceholderText("مثال: hmillionair.com أو myapp.onrender.com")
        form_hosting.addRow("اسم النطاق / رابط الموقع:", self.hosting_domain_input)

        self.hosting_port_input = QLineEdit("8000")
        self.hosting_port_input.setPlaceholderText("8000")
        form_hosting.addRow("منفذ التطبيق (Port):", self.hosting_port_input)

        l_provider.addLayout(form_hosting)
        lay_hosting.addWidget(f_provider)

        # --- Card 2: VPS / SSH Settings ---
        self.f_vps = QFrame()
        self.f_vps.setObjectName("StatCard")
        l_vps = QVBoxLayout(self.f_vps)
        l_vps.setSpacing(12)

        title_vps = QLabel("إعدادات السيرفر الخاص (VPS / SSH)")
        title_vps.setStyleSheet("font-weight: bold; font-size: 15px; color: #1e293b;")
        l_vps.addWidget(title_vps)

        form_vps = QFormLayout()
        form_vps.setSpacing(10)

        self.vps_host_input = QLineEdit()
        self.vps_host_input.setPlaceholderText("مثال: 123.45.67.89")
        form_vps.addRow("عنوان السيرفر (IP):", self.vps_host_input)

        self.vps_ssh_port_input = QLineEdit("22")
        self.vps_ssh_port_input.setPlaceholderText("22")
        form_vps.addRow("منفذ SSH:", self.vps_ssh_port_input)

        self.vps_user_input = QLineEdit("root")
        self.vps_user_input.setPlaceholderText("root")
        form_vps.addRow("اسم المستخدم (SSH):", self.vps_user_input)

        self.vps_password_input = QLineEdit()
        self.vps_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.vps_password_input.setPlaceholderText("كلمة مرور SSH (اختياري إذا تستخدم مفتاح)")
        form_vps.addRow("كلمة مرور SSH:", self.vps_password_input)

        self.vps_project_path_input = QLineEdit("/var/www/project-hakbah")
        self.vps_project_path_input.setPlaceholderText("/var/www/project-hakbah")
        form_vps.addRow("مسار المشروع على السيرفر:", self.vps_project_path_input)

        self.vps_service_name_input = QLineEdit("hakbah-web")
        self.vps_service_name_input.setPlaceholderText("hakbah-web")
        form_vps.addRow("اسم خدمة Systemd:", self.vps_service_name_input)

        l_vps.addLayout(form_vps)
        lay_hosting.addWidget(self.f_vps)

        # --- Card 3: Cloud Platform Settings ---
        self.f_cloud = QFrame()
        self.f_cloud.setObjectName("StatCard")
        l_cloud = QVBoxLayout(self.f_cloud)
        l_cloud.setSpacing(12)

        title_cloud = QLabel("إعدادات المنصة السحابية")
        title_cloud.setStyleSheet("font-weight: bold; font-size: 15px; color: #1e293b;")
        l_cloud.addWidget(title_cloud)

        lbl_cloud_desc = QLabel(
            "أدخل بيانات الاتصال بمنصة الاستضافة السحابية المختارة.\n"
            "يمكنك العثور على هذه البيانات في لوحة تحكم المنصة."
        )
        lbl_cloud_desc.setWordWrap(True)
        lbl_cloud_desc.setStyleSheet("color: #64748b; font-size: 12px;")
        l_cloud.addWidget(lbl_cloud_desc)

        form_cloud = QFormLayout()
        form_cloud.setSpacing(10)

        self.cloud_api_key_input = QLineEdit()
        self.cloud_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.cloud_api_key_input.setPlaceholderText("API Key أو Token الخاص بالمنصة")
        form_cloud.addRow("مفتاح API / Token:", self.cloud_api_key_input)

        self.cloud_project_id_input = QLineEdit()
        self.cloud_project_id_input.setPlaceholderText("معرف المشروع أو اسم التطبيق على المنصة")
        form_cloud.addRow("معرف المشروع / اسم التطبيق:", self.cloud_project_id_input)

        self.cloud_region_combo = QComboBox()
        self.cloud_region_combo.addItems([
            "تلقائي (Auto)",
            "أوروبا (EU - Frankfurt)",
            "أمريكا الشمالية (US - Oregon)",
            "آسيا (Asia - Singapore)",
            "الشرق الأوسط (ME - Bahrain)"
        ])
        form_cloud.addRow("المنطقة الجغرافية:", self.cloud_region_combo)

        l_cloud.addLayout(form_cloud)
        lay_hosting.addWidget(self.f_cloud)

        # --- Card 4: Status & Actions ---
        f_actions = QFrame()
        f_actions.setObjectName("StatCard")
        l_actions = QVBoxLayout(f_actions)
        l_actions.setSpacing(12)

        title_actions = QLabel("حالة الموقع والإجراءات السريعة")
        title_actions.setStyleSheet("font-weight: bold; font-size: 15px; color: #1e293b;")
        l_actions.addWidget(title_actions)

        self.lbl_hosting_status = QLabel("حالة الموقع: غير محدد")
        self.lbl_hosting_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #64748b;")
        l_actions.addWidget(self.lbl_hosting_status)

        btn_box_hosting = QHBoxLayout()
        btn_box_hosting.setSpacing(10)

        btn_check_site = QPushButton("فحص حالة الموقع")
        btn_check_site.setObjectName("PrimaryBtn")
        btn_check_site.setStyleSheet("background-color: #3b82f6; color: white;")
        btn_check_site.clicked.connect(self.check_hosting_status)
        btn_box_hosting.addWidget(btn_check_site)

        btn_open_site = QPushButton("فتح الموقع في المتصفح")
        btn_open_site.setObjectName("PrimaryBtn")
        btn_open_site.setStyleSheet("background-color: #8b5cf6; color: white;")
        btn_open_site.clicked.connect(self.open_hosted_website)
        btn_box_hosting.addWidget(btn_open_site)

        l_actions.addLayout(btn_box_hosting)

        btn_box_hosting2 = QHBoxLayout()
        btn_box_hosting2.setSpacing(10)

        btn_save_hosting = QPushButton("حفظ إعدادات الاستضافة")
        btn_save_hosting.setObjectName("PrimaryBtn")
        btn_save_hosting.setStyleSheet("background-color: #10b981; color: white;")
        btn_save_hosting.clicked.connect(self.save_hosting_settings)
        btn_box_hosting2.addWidget(btn_save_hosting)

        btn_copy_deploy_guide = QPushButton("عرض دليل النشر")
        btn_copy_deploy_guide.setObjectName("PrimaryBtn")
        btn_copy_deploy_guide.setStyleSheet("background-color: #f59e0b; color: white;")
        btn_copy_deploy_guide.clicked.connect(self.show_deploy_guide)
        btn_box_hosting2.addWidget(btn_copy_deploy_guide)

        l_actions.addLayout(btn_box_hosting2)
        lay_hosting.addWidget(f_actions)

        lay_hosting.addStretch()
        tab_hosting.setWidget(con_hosting)
        self.company_settings_tabs.addTab(tab_hosting, "الاستضافة والنشر")

        layout.addWidget(self.company_settings_tabs)
        return page
    def refresh_cat_list(self):
        self.com.clear()
        cats = self.db.query(db_mod.Category).all()
        for c in cats: self.com.addItem(c.name, c.id)
        self.refresh_numbers_list()
        self.refresh_cat_table(cats)

    def load_company_settings(self):
        keys = [
            "company_name",
            "company_legal_name",
            "company_commercial_record",
            "company_establishment_date",
            "company_logo_path"
        ]
        settings = {s.key: s.value for s in self.db.query(db_mod.Setting).filter(db_mod.Setting.key.in_(keys)).all()}
        self.company_name_input.setText(settings.get("company_name", ""))
        self.company_legal_name_input.setText(settings.get("company_legal_name", ""))
        self.company_record_input.setText(settings.get("company_commercial_record", ""))
        est_date = settings.get("company_establishment_date", "")
        if est_date:
            try:
                dt = datetime.datetime.strptime(est_date, "%Y-%m-%d").date()
                self.company_est_date.setDate(QDate(dt.year, dt.month, dt.day))
            except Exception:
                pass
        logo_path = settings.get("company_logo_path", "")
        self.company_logo_path = logo_path
        self.update_company_logo_preview(logo_path)
        self.refresh_user_permissions_table()
        if hasattr(self, "load_db_connection_settings"):
            self.load_db_connection_settings()
        if hasattr(self, "load_hosting_settings"):
            self.load_hosting_settings()

    def set_setting(self, key, value):
        setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
        if not setting:
            setting = db_mod.Setting(key=key, value=value)
            self.db.add(setting)
        else:
            setting.value = value
        self.db.commit()

    def save_company_info(self):
        self.set_setting("company_name", self.company_name_input.text().strip())
        self.set_setting("company_legal_name", self.company_legal_name_input.text().strip())
        self.set_setting("company_commercial_record", self.company_record_input.text().strip())
        self.set_setting("company_establishment_date", self.company_est_date.date().toString("yyyy-MM-dd"))
        if hasattr(self, "company_logo_path") and self.company_logo_path:
            self.set_setting("company_logo_path", self.company_logo_path)
        ModernDialog(self, "نجاح", "تم حفظ بيانات الشركة بنجاح.").exec()

    def select_company_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "اختر شعار الشركة", "", "صور (*.png *.jpg *.jpeg)")
        if not file_path:
            return
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        uploads_dir = os.path.join(base_dir, "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        ext = os.path.splitext(file_path)[1]
        dest = os.path.join(uploads_dir, f"company_logo{ext}")
        try:
            shutil.copy(file_path, dest)
            self.company_logo_path = dest
            self.update_company_logo_preview(dest)
            self.set_setting("company_logo_path", dest)
            ModernDialog(self, "نجاح", "تم حفظ شعار الشركة بنجاح.").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء حفظ الشعار: {e}").exec()

    def update_company_logo_preview(self, logo_path):
        if logo_path and os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            if not pix.isNull():
                self.company_logo_label.setPixmap(pix.scaled(self.company_logo_label.width(), self.company_logo_label.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                return
        self.company_logo_label.setText("لا يوجد شعار بعد")
        self.company_logo_label.setPixmap(QPixmap())

    def refresh_user_permissions_table(self):
        search_txt = self.user_search_input.text().strip()
        query = self.db.query(db_mod.Staff)
        if search_txt:
            query = query.filter((db_mod.Staff.name.like(f"%{search_txt}%")) | (db_mod.Staff.phone.like(f"%{search_txt}%")))
        staff_members = query.order_by(db_mod.Staff.created_at.desc()).all()
        self.table_user_permissions.setRowCount(len(staff_members))
        roles = ["مدير", "محاسب", "موظف", "مشاهد"]
        for i, s in enumerate(staff_members):
            self.table_user_permissions.setItem(i, 0, QTableWidgetItem(s.name))
            self.table_user_permissions.setItem(i, 1, QTableWidgetItem(s.phone))
            self.table_user_permissions.setItem(i, 2, QTableWidgetItem(s.staff_id_code))
            role_combo = QComboBox()
            role_combo.addItems(roles)
            if s.role and s.role in roles:
                role_combo.setCurrentText(s.role)
            else:
                role_combo.setCurrentText("موظف")
            role_combo.currentIndexChanged.connect(lambda _, sid=s.id, combo=role_combo: self.update_staff_role(sid, combo.currentText()))
            self.table_user_permissions.setCellWidget(i, 3, role_combo)
            btn_delete = QPushButton("حذف")
            btn_delete.setObjectName("DangerBtn")
            btn_delete.clicked.connect(lambda _, sid=s.id: self.delete_staff_from_settings(sid))
            self.table_user_permissions.setCellWidget(i, 4, btn_delete)

    def update_staff_role(self, sid, role):
        staff = self.db.get(db_mod.Staff, sid)
        if not staff:
            return
        staff.role = role
        self.db.commit()

    def delete_staff_from_settings(self, sid):
        if ModernDialog(self, "تأكيد", "هل أنت متأكد من حذف هذا الموظف؟", is_confirm=True).exec():
            staff = self.db.get(db_mod.Staff, sid)
            if staff:
                self.db.delete(staff)
                self.db.commit()
                self.refresh_user_permissions_table()

    def add_user_from_settings(self):
        dlg = AddStaffDialog(self)
        if dlg.exec():
            name = dlg.ent_name.text().strip()
            phone = dlg.ent_phone.text().strip()
            s_id = dlg.ent_staff_id.text().strip()
            pwd = dlg.ent_pwd.text().strip()
            role = dlg.role_combo.currentText() if hasattr(dlg, 'role_combo') else "موظف"
            exists = self.db.query(db_mod.Staff).filter(db_mod.Staff.staff_id_code == s_id).first()
            if exists:
                ModernDialog(self, "خطأ", "رقم الموظف هذا مسجل مسبقاً").exec()
                return
            try:
                new_staff = db_mod.Staff(
                    name=name,
                    phone=phone,
                    staff_id_code=s_id,
                    password=security.hash_password(pwd),
                    role=role
                )
                self.db.add(new_staff)
                self.db.commit()
                self.refresh_user_permissions_table()
                ModernDialog(self, "نجاح", "تم إنشاء حساب الموظف بنجاح").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", str(e)).exec()
    def refresh_cat_table(self, cats):
        self.table_cats.setRowCount(len(cats))
        for i, c in enumerate(cats):
            self.table_cats.setItem(i, 0, QTableWidgetItem(c.name))
            self.table_cats.setItem(i, 1, QTableWidgetItem(f"{c.amount:,.2f}"))
            
            prize = getattr(c, 'prize_amount', 0.0)
            self.table_cats.setItem(i, 2, QTableWidgetItem(f"{prize:,.2f}"))
            
            # Number count & reservations
            nums = c.available_numbers if hasattr(c, 'available_numbers') and c.available_numbers else []
            total_n = len(nums)
            res_n = sum(1 for n in nums if n.is_reserved)
            num_item = QTableWidgetItem(f"{total_n} رقم ({res_n} محجوز)" if total_n > 0 else "لا توجد أرقام")
            if total_n > 0 and res_n >= total_n:
                num_item.setForeground(QColor("#ef4444")) # Red if full
            elif total_n > 0:
                num_item.setForeground(QColor("#059669")) # Green if has capacity
            else:
                num_item.setForeground(QColor("#94a3b8"))
            self.table_cats.setItem(i, 3, num_item)

            # Action buttons container
            container = QWidget()
            btn_layout = QHBoxLayout(container)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(6)

            btn_grp = QPushButton("➕ مجموعة جديدة")
            btn_grp.setObjectName("PrimaryBtn")
            btn_grp.setStyleSheet("background-color: #059669; color: white; border: none; font-size: 11px; padding: 4px 8px; font-weight: bold;")
            btn_grp.setToolTip("فتح وتوليد مجموعة جديدة فوراً بنفس إعدادات هذه الفئة")
            btn_grp.clicked.connect(lambda checked, cid=c.id: self.create_new_group_batch(cid))
            btn_layout.addWidget(btn_grp)

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

            self.table_cats.setCellWidget(i, 4, container)

    def create_new_group_batch_from_top(self):
        cats = self.db.query(db_mod.Category).all()
        selected_cat = cats[0] if cats else None
        self.create_new_group_batch(selected_cat.id if selected_cat else None)
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
        prize_str = self.en3.text().strip()
        
        if not name or not amount_str:
            ModernDialog(self, "خطأ", "يرجى ملء الحقول المطلوبة").exec()
            return
            
        try:
            amount = float(amount_str)
            prize = float(prize_str) if prize_str else 0.0
            # Check if name exists
            exists = self.db.query(db_mod.Category).filter(db_mod.Category.name == name).first()
            if exists:
                ModernDialog(self, "خطأ", "هذا الاسم موجود بالفعل").exec()
                return
                
            self.db.add(db_mod.Category(name=name, amount=amount, prize_amount=prize))
            self.db.commit()
            self.en1.clear(); self.en2.clear(); self.en3.clear(); self.refresh_cat_list()
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
                new_prize_str = dialog.ent_prize.text().strip()
                
                if not new_name or not new_amount_str:
                    ModernDialog(self, "خطأ", "يرجى ملء الحقول المطلوبة").exec()
                    return
                    
                new_amount = float(new_amount_str)
                new_prize = float(new_prize_str) if new_prize_str else 0.0
                
                if new_name != old_name:
                    exists = self.db.query(db_mod.Category).filter(db_mod.Category.name == new_name).first()
                    if exists:
                        ModernDialog(self, "خطأ", "هذا الاسم موجود بالفعل").exec()
                        return
                    # Update all subscribers with the new category name string
                    self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == old_name).update({db_mod.Subscriber.category: new_name})
                
                cat.name = new_name
                cat.amount = new_amount
                cat.prize_amount = new_prize
                self.db.commit()
                self.refresh_cat_list()
                ModernDialog(self, "نجاح", "تم تعديل الفئة بنجاح").exec()
            except ValueError:
                ModernDialog(self, "خطأ", "المبلغ يجب أن يكون رقماً").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ: {e}").exec()
    def create_new_group_batch(self, cid):
        cat = self.db.get(db_mod.Category, cid)
        if not cat: return
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
                
                self.refresh_cat_list()
                ModernDialog(self, "نجاح", f"تم إنشاء المجموعة '{name}' بنجاح وتوليد {len(nums_to_add)} رقماً لها.").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء إنشاء المجموعة: {e}").exec()

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

    def create_backup(self):
        try:
            import sys
            import sqlite3
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            db_path = os.path.join(base_dir, 'hakbah.db')
            if not os.path.exists(db_path):
                ModernDialog(self, "خطأ", "قاعدة البيانات غير موجودة").exec()
                return

            file_path, _ = QFileDialog.getSaveFileName(self, "حفظ النسخة الاحتياطية", "", "Database Files (*.db)")
            if not file_path:
                return
                
            # استخدام مكتبة sqlite3 لعمل نسخة احتياطية آمنة (متوافقة مع وضع WAL)
            source = sqlite3.connect(db_path)
            dest = sqlite3.connect(file_path)
            with source:
                source.backup(dest)
            dest.close()
            source.close()
            
            ModernDialog(self, "نجاح", "تم إنشاء النسخة الاحتياطية بنجاح").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء إنشاء النسخة الاحتياطية: {e}").exec()

    def restore_backup(self):
        if not ModernDialog(self, "تأكيد", "هل أنت متأكد من استعادة النسخة الاحتياطية؟ سيتم مسح البيانات الحالية. التطبيق سيحتاج لإعادة التشغيل.", is_confirm=True).exec():
            return
            
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "اختر ملف النسخة الاحتياطية", "", "Database Files (*.db)")
            if not file_path:
                return
    
            import sys
            import database as db_mod
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                
            db_path = os.path.join(base_dir, 'hakbah.db')
            
            # Close db session before overwrite
            try:
                self.db.close()
                db_mod.engine.dispose()
            except Exception as e:
                print(f"Could not close DB session before restore: {e}")
            
            # إزالة ملفات WAL المؤقتة لتجنب تعارض البيانات
            wal_path = db_path + "-wal"
            shm_path = db_path + "-shm"
            if os.path.exists(wal_path):
                try:
                    os.remove(wal_path)
                except OSError as e:
                    print(f"Error removing WAL file: {e}")
            if os.path.exists(shm_path):
                try:
                    os.remove(shm_path)
                except OSError as e:
                    print(f"Error removing SHM file: {e}")

            # استخدام sqlite3.backup لاستعادة النسخة بدلاً من النسخ المباشر
            # لضمان توافقية أفضل مع WAL وعدم تعارض الملفات
            import sqlite3
            source = sqlite3.connect(file_path)
            dest = sqlite3.connect(db_path)
            with dest:
                source.backup(dest)
            dest.close()
            source.close()
            
            ModernDialog(self, "نجاح", "تم استعادة النسخة الاحتياطية بنجاح. سيتم إعادة تشغيل التطبيق تلقائياً الآن لتحديث البيانات.").exec()
            
            import subprocess
            import sys
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable] + sys.argv[1:])
            else:
                subprocess.Popen([sys.executable] + sys.argv)
                
            QApplication.quit()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء استعادة النسخة الاحتياطية: {e}").exec()

    def on_db_mode_changed(self, index):
        is_remote = (index == 1)
        self.db_host_input.setEnabled(is_remote)
        self.db_port_input.setEnabled(is_remote)
        self.db_name_input.setEnabled(is_remote)
        self.db_user_input.setEnabled(is_remote)
        self.db_pass_input.setEnabled(is_remote)

    def load_db_connection_settings(self):
        # 1. استخراج بيانات السيرفر المحفوظة مسبقاً وتعبئتها في الحقول حتى لا يضطر المستخدم لكتابتها كل مرة
        server_url = db_mod.get_server_database_url()
        if server_url:
            import re
            m = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)", server_url)
            if m:
                user, password, host, port, dbname = m.groups()
                self.db_user_input.setText(user or "hakbah_user")
                self.db_pass_input.setText(password or "")
                self.db_host_input.setText(host or "")
                self.db_port_input.setText(port or "5432")
                self.db_name_input.setText(dbname or "hakbah_db")

        # 2. تحديد نوع الاتصال الحالي الفعال
        current_url = db_mod.DATABASE_URL or ""
        if current_url.startswith("postgresql://") or current_url.startswith("postgres://"):
            self.db_mode_combo.setCurrentIndex(1)
            host_name = self.db_host_input.text() or "سيرفر خارجي"
            self.lbl_db_status.setText(f"حالة الاتصال الفعالة الآن: متصل بالسيرفر الخارجي (PostgreSQL: {host_name}) 🟢")
            self.lbl_db_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #16a34a;")
        else:
            self.db_mode_combo.setCurrentIndex(0)
            self.lbl_db_status.setText("حالة الاتصال الفعالة الآن: متصل بقاعدة البيانات المحلية (SQLite - hakbah.db) 🟢")
            self.lbl_db_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #0284c7;")
        self.on_db_mode_changed(self.db_mode_combo.currentIndex())

    def get_configured_db_url(self):
        if self.db_mode_combo.currentIndex() == 0:
            return db_mod.get_local_database_url()
        else:
            host = self.db_host_input.text().strip()
            port = self.db_port_input.text().strip() or "5432"
            dbname = self.db_name_input.text().strip() or "hakbah_db"
            user = self.db_user_input.text().strip() or "hakbah_user"
            password = self.db_pass_input.text().strip()
            return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

    def test_db_connection(self):
        url = self.get_configured_db_url()
        if self.db_mode_combo.currentIndex() == 0:
            ModernDialog(self, "نجاح الاتصال", "قاعدة البيانات المحلية (SQLite) جاهزة ومتصلة بنجاح!").exec()
            return

        try:
            from sqlalchemy import create_engine, text
            test_engine = create_engine(url, connect_args={"connect_timeout": 5})
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            test_engine.dispose()
            ModernDialog(self, "نجاح الاتصال", "تم الاتصال بالسيرفر بنجاح! السيرفر يعمل واستجاب للطلب.").exec()
        except Exception as e:
            ModernDialog(self, "فشل الاتصال بالسيرفر", f"تعذر الاتصال بالسيرفر المحدد:\n{e}").exec()

    def update_env_file(self, env_vars):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env_path = os.path.join(base_dir, ".env")
        
        existing = {}
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        existing[k.strip()] = v.strip()
                        
        existing.update(env_vars)
        
        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")
        
        for k, v in env_vars.items():
            os.environ[k] = v

    def save_db_connection(self):
        if self.db_mode_combo.currentIndex() == 0:
            # التحويل إلى قاعدة البيانات المحلية SQLite
            try:
                local_url = db_mod.get_local_database_url()
                self.update_env_file({"DB_MODE": "local"})
                db_mod.reconnect_engine(local_url)
                self.db = db_mod.SessionLocal()
                db_mod.init_db()
                self.load_db_connection_settings()
                ModernDialog(self, "نجاح", "تم التبديل بنجاح إلى قاعدة البيانات المحلية (SQLite).").exec()
            except Exception as e:
                ModernDialog(self, "خطأ", f"حدث خطأ أثناء التبديل للقاعدة المحلية:\n{e}").exec()
            return

        # التحويل إلى السيرفر الخارجي PostgreSQL
        host = self.db_host_input.text().strip()
        port = self.db_port_input.text().strip() or "5432"
        dbname = self.db_name_input.text().strip() or "hakbah_db"
        user = self.db_user_input.text().strip() or "hakbah_user"
        password = self.db_pass_input.text().strip()

        if not host:
            ModernDialog(self, "خطأ", "يرجى إدخال عنوان السيرفر (IP أو Host).").exec()
            return
        if not password:
            ModernDialog(self, "خطأ", "يرجى إدخال كلمة مرور قاعدة البيانات.").exec()
            return

        new_pg_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

        # اختبار الاتصال أولاً قبل الحفظ والتطبيق
        try:
            from sqlalchemy import create_engine, text
            test_engine = create_engine(new_pg_url, connect_args={"connect_timeout": 5})
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            test_engine.dispose()
        except Exception as e:
            ModernDialog(self, "خطأ الاتصال بالسيرفر", f"فشل الاتصال بالسيرفر، يرجى التأكد من تشغيل السيرفر وصحة البيانات:\n{e}").exec()
            return

        try:
            self.update_env_file({
                "SERVER_DATABASE_URL": new_pg_url,
                "DB_MODE": "server"
            })
            db_mod.reconnect_engine(new_pg_url)
            self.db = db_mod.SessionLocal()
            db_mod.init_db()
            self.load_db_connection_settings()
            ModernDialog(self, "نجاح الاتصال", f"تم الاتصال بالسيرفر بنجاح ({host}) وتحديث قاعدة البيانات!").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء إعادة ضبط الاتصال:\n{e}").exec()

    # ==================== Hosting & Deployment Settings ====================

    def on_hosting_provider_changed(self, index):
        """إظهار/إخفاء حقول الإعدادات حسب نوع منصة الاستضافة"""
        is_vps = (index == 0)  # VPS / SSH
        is_cloud = (index in (1, 2, 3, 4))  # Render, Railway, Heroku, DigitalOcean
        self.f_vps.setVisible(is_vps)
        self.f_cloud.setVisible(is_cloud)

    def load_hosting_settings(self):
        """تحميل إعدادات الاستضافة المحفوظة من قاعدة البيانات"""
        keys = [
            "hosting_provider", "hosting_domain", "hosting_port",
            "vps_host", "vps_ssh_port", "vps_user", "vps_password",
            "vps_project_path", "vps_service_name",
            "cloud_api_key", "cloud_project_id", "cloud_region"
        ]
        settings = {s.key: s.value for s in self.db.query(db_mod.Setting).filter(db_mod.Setting.key.in_(keys)).all()}

        provider_index = int(settings.get("hosting_provider", "0") or "0")
        if 0 <= provider_index < self.hosting_provider_combo.count():
            self.hosting_provider_combo.setCurrentIndex(provider_index)

        self.hosting_domain_input.setText(settings.get("hosting_domain", ""))
        self.hosting_port_input.setText(settings.get("hosting_port", "8000"))

        self.vps_host_input.setText(settings.get("vps_host", ""))
        self.vps_ssh_port_input.setText(settings.get("vps_ssh_port", "22"))
        self.vps_user_input.setText(settings.get("vps_user", "root"))
        self.vps_password_input.setText(settings.get("vps_password", ""))
        self.vps_project_path_input.setText(settings.get("vps_project_path", "/var/www/project-hakbah"))
        self.vps_service_name_input.setText(settings.get("vps_service_name", "hakbah-web"))

        self.cloud_api_key_input.setText(settings.get("cloud_api_key", ""))
        self.cloud_project_id_input.setText(settings.get("cloud_project_id", ""))

        region_index = int(settings.get("cloud_region", "0") or "0")
        if 0 <= region_index < self.cloud_region_combo.count():
            self.cloud_region_combo.setCurrentIndex(region_index)

        self.on_hosting_provider_changed(provider_index)

        # تحديث حالة الموقع
        domain = settings.get("hosting_domain", "")
        if domain:
            self.lbl_hosting_status.setText(f"الموقع المسجل: {domain}")
            self.lbl_hosting_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #0284c7;")
        else:
            self.lbl_hosting_status.setText("لم يتم ضبط إعدادات الاستضافة بعد")
            self.lbl_hosting_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #64748b;")

    def save_hosting_settings(self):
        """حفظ جميع إعدادات الاستضافة في قاعدة البيانات"""
        settings_to_save = {
            "hosting_provider": str(self.hosting_provider_combo.currentIndex()),
            "hosting_domain": self.hosting_domain_input.text().strip(),
            "hosting_port": self.hosting_port_input.text().strip() or "8000",
            "vps_host": self.vps_host_input.text().strip(),
            "vps_ssh_port": self.vps_ssh_port_input.text().strip() or "22",
            "vps_user": self.vps_user_input.text().strip() or "root",
            "vps_password": self.vps_password_input.text().strip(),
            "vps_project_path": self.vps_project_path_input.text().strip() or "/var/www/project-hakbah",
            "vps_service_name": self.vps_service_name_input.text().strip() or "hakbah-web",
            "cloud_api_key": self.cloud_api_key_input.text().strip(),
            "cloud_project_id": self.cloud_project_id_input.text().strip(),
            "cloud_region": str(self.cloud_region_combo.currentIndex()),
        }

        try:
            for key, value in settings_to_save.items():
                self.set_setting(key, value)
            self.load_hosting_settings()
            ModernDialog(self, "نجاح", "تم حفظ إعدادات الاستضافة بنجاح!").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء حفظ إعدادات الاستضافة:\n{e}").exec()

    def check_hosting_status(self):
        """فحص حالة الموقع عبر إرسال طلب HTTP للتأكد من أنه يعمل"""
        domain = self.hosting_domain_input.text().strip()
        if not domain:
            ModernDialog(self, "تنبيه", "يرجى إدخال اسم النطاق أو رابط الموقع أولاً.").exec()
            return

        # تنظيف الرابط
        if not domain.startswith("http"):
            url = f"https://{domain}"
        else:
            url = domain

        self.lbl_hosting_status.setText("جاري فحص حالة الموقع...")
        self.lbl_hosting_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #f59e0b;")
        QApplication.processEvents()

        try:
            import urllib.request
            import urllib.error
            req = urllib.request.Request(url, method='GET')
            req.add_header('User-Agent', 'HakbahAdmin/1.0')
            response = urllib.request.urlopen(req, timeout=10)
            status_code = response.getcode()

            if status_code == 200:
                self.lbl_hosting_status.setText(f"الموقع يعمل بنجاح! ({url}) - الحالة: {status_code}")
                self.lbl_hosting_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #16a34a;")
            else:
                self.lbl_hosting_status.setText(f"الموقع يستجيب لكن بكود: {status_code}")
                self.lbl_hosting_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #f59e0b;")
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 307, 308):
                self.lbl_hosting_status.setText(f"الموقع يستجيب (إعادة توجيه: {e.code})")
                self.lbl_hosting_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #0284c7;")
            else:
                self.lbl_hosting_status.setText(f"خطأ HTTP: {e.code} - {e.reason}")
                self.lbl_hosting_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #dc2626;")
        except Exception as e:
            # محاولة ثانية مع http بدلاً من https
            try:
                url_http = url.replace("https://", "http://")
                req = urllib.request.Request(url_http, method='GET')
                req.add_header('User-Agent', 'HakbahAdmin/1.0')
                response = urllib.request.urlopen(req, timeout=10)
                status_code = response.getcode()
                self.lbl_hosting_status.setText(f"الموقع يعمل عبر HTTP ({url_http}) - الحالة: {status_code}")
                self.lbl_hosting_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #f59e0b;")
            except Exception:
                self.lbl_hosting_status.setText(f"الموقع لا يستجيب: {e}")
                self.lbl_hosting_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #dc2626;")

    def open_hosted_website(self):
        """فتح الموقع المستضاف في المتصفح الافتراضي"""
        domain = self.hosting_domain_input.text().strip()
        if not domain:
            ModernDialog(self, "تنبيه", "يرجى إدخال اسم النطاق أو رابط الموقع أولاً.").exec()
            return

        if not domain.startswith("http"):
            url = f"https://{domain}"
        else:
            url = domain

        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            ModernDialog(self, "خطأ", f"تعذر فتح المتصفح:\n{e}").exec()

    def show_deploy_guide(self):
        """عرض دليل النشر في نافذة حوار مفصلة"""
        provider_index = self.hosting_provider_combo.currentIndex()
        provider_name = self.hosting_provider_combo.currentText()

        domain = self.hosting_domain_input.text().strip() or "example.com"
        port = self.hosting_port_input.text().strip() or "8000"
        vps_host = self.vps_host_input.text().strip() or "YOUR_SERVER_IP"
        vps_user = self.vps_user_input.text().strip() or "root"
        vps_path = self.vps_project_path_input.text().strip() or "/var/www/project-hakbah"
        service_name = self.vps_service_name_input.text().strip() or "hakbah-web"

        if provider_index == 0:  # VPS
            guide = (
                f"===  دليل نشر الموقع على VPS  ===\n\n"
                f"1. الاتصال بالسيرفر:\n"
                f"   ssh {vps_user}@{vps_host}\n\n"
                f"2. رفع ملفات المشروع إلى:\n"
                f"   {vps_path}\n\n"
                f"3. تثبيت المتطلبات:\n"
                f"   cd {vps_path}\n"
                f"   python3 -m venv .venv\n"
                f"   source .venv/bin/activate\n"
                f"   pip install -r requirements.txt\n\n"
                f"4. إنشاء ملف .env على السيرفر بإعدادات PostgreSQL:\n"
                f"   DB_MODE=server\n"
                f"   SERVER_DATABASE_URL=postgresql://hakbah_user:PASSWORD@localhost:5432/hakbah_db\n\n"
                f"5. إنشاء خدمة Systemd ({service_name}.service):\n"
                f"   ExecStart={vps_path}/.venv/bin/uvicorn main:app --host 0.0.0.0 --port {port}\n\n"
                f"6. تفعيل الخدمة:\n"
                f"   sudo systemctl enable {service_name}\n"
                f"   sudo systemctl start {service_name}\n\n"
                f"7. إعداد Nginx وشهادة SSL لنطاق {domain}\n\n"
                f"للتفاصيل الكاملة راجع ملف deploy_vps_guide.md"
            )
        elif provider_index == 1:  # Render
            guide = (
                f"===  دليل نشر الموقع على Render  ===\n\n"
                f"1. أنشئ حساباً على render.com\n"
                f"2. اربط مستودع GitHub الخاص بالمشروع\n"
                f"3. أنشئ Web Service جديد:\n"
                f"   - Build Command: pip install -r requirements.txt\n"
                f"   - Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT\n\n"
                f"4. أضف متغيرات البيئة في Render Dashboard:\n"
                f"   DB_MODE=server\n"
                f"   SERVER_DATABASE_URL=postgresql://...\n"
                f"   SECRET_KEY=...\n\n"
                f"5. أضف قاعدة بيانات PostgreSQL من Render\n"
                f"6. سيعمل الموقع تلقائياً على رابط .onrender.com\n"
                f"7. لربط نطاق مخصص ({domain}) اذهب إلى Settings > Custom Domains"
            )
        elif provider_index == 2:  # Railway
            guide = (
                f"===  دليل نشر الموقع على Railway  ===\n\n"
                f"1. أنشئ حساباً على railway.app\n"
                f"2. أنشئ مشروعاً جديداً واربط GitHub\n"
                f"3. أضف Plugin: PostgreSQL\n"
                f"4. أضف متغيرات البيئة:\n"
                f"   DB_MODE=server\n"
                f"   SERVER_DATABASE_URL=${{DATABASE_URL}}\n\n"
                f"5. سيتعرف Railway تلقائياً على Procfile\n"
                f"6. لربط نطاق ({domain}): Settings > Domains > Custom Domain"
            )
        elif provider_index == 3:  # Heroku
            guide = (
                f"===  دليل نشر الموقع على Heroku  ===\n\n"
                f"1. ثبت Heroku CLI وسجل الدخول:\n"
                f"   heroku login\n\n"
                f"2. أنشئ تطبيقاً:\n"
                f"   heroku create hakbah-app\n\n"
                f"3. أضف PostgreSQL:\n"
                f"   heroku addons:create heroku-postgresql:mini\n\n"
                f"4. ضبط متغيرات البيئة:\n"
                f"   heroku config:set DB_MODE=server\n"
                f"   heroku config:set SECRET_KEY=...\n\n"
                f"5. انشر المشروع:\n"
                f"   git push heroku main\n\n"
                f"6. لربط نطاق ({domain}):\n"
                f"   heroku domains:add {domain}"
            )
        elif provider_index == 4:  # DigitalOcean
            guide = (
                f"===  دليل نشر على DigitalOcean App Platform  ===\n\n"
                f"1. أنشئ حساباً على digitalocean.com\n"
                f"2. اذهب إلى App Platform > Create App\n"
                f"3. اربط مستودع GitHub\n"
                f"4. اختر Resources > Add Database (PostgreSQL)\n"
                f"5. أضف متغيرات البيئة:\n"
                f"   DB_MODE=server\n"
                f"   SERVER_DATABASE_URL=${{DATABASE_URL}}\n\n"
                f"6. Run Command: uvicorn main:app --host 0.0.0.0 --port {port}\n"
                f"7. لربط نطاق ({domain}): Settings > Domains"
            )
        else:
            guide = (
                f"===  دليل نشر عام  ===\n\n"
                f"المتطلبات الأساسية لنشر الموقع على أي منصة:\n\n"
                f"1. Python 3.10+ مع المكتبات في requirements.txt\n"
                f"2. قاعدة بيانات PostgreSQL\n"
                f"3. متغيرات البيئة:\n"
                f"   DB_MODE=server\n"
                f"   SERVER_DATABASE_URL=postgresql://user:pass@host:5432/dbname\n"
                f"   SECRET_KEY=your_secret_key\n\n"
                f"4. أمر التشغيل:\n"
                f"   uvicorn main:app --host 0.0.0.0 --port {port}\n\n"
                f"5. الملفات المتوفرة: Procfile, Dockerfile\n"
                f"6. لربط النطاق ({domain}) راجع وثائق المنصة"
            )

        ModernDialog(self, f"دليل النشر - {provider_name}", guide).exec()
