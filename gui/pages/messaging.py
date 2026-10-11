from sqlalchemy import func, or_
from sqlalchemy.orm import Session
import os
import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, 
    QScrollArea, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, 
    QHeaderView, QMessageBox, QDialog, QFormLayout, QCheckBox, 
    QTextEdit, QTabWidget, QSpinBox, QDateTimeEdit, QAbstractItemView,
    QGridLayout, QGroupBox
)
from PyQt6.QtCore import Qt, QDateTime, QDate, QTime
from PyQt6.QtGui import QColor, QFont
import database as db_mod
from gui.dialogs import ModernDialog

class SubscriberMessageEditDialog(QDialog):
    def __init__(self, parent=None, message=None, categories=None):
        super().__init__(parent)
        self.message = message
        self.categories = categories or []
        self.setWindowTitle("تعديل الرسالة" if message else "إضافة رسالة جديدة للمشتركين")
        self.setMinimumWidth(550)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        title_lbl = QLabel("بيانات الرسالة التوعوية / التذكيرية للموقع")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #10b981; margin-bottom: 5px;")
        layout.addWidget(title_lbl)

        form_frame = QFrame()
        form_frame.setObjectName("StatCard")
        form = QFormLayout(form_frame)
        form.setSpacing(12)

        # 1. Title
        self.in_title = QLineEdit()
        self.in_title.setPlaceholderText("مثال: نصيحة هامة حول سداد الأقساط أو موعد السحب القادم")
        form.addRow("عنوان الرسالة *:", self.in_title)

        # 2. Type
        self.in_type = QComboBox()
        self.in_type.addItem("💡 رسالة توعوية (Awareness)", "awareness")
        self.in_type.addItem("📚 رسالة تعليمية (Educational)", "educational")
        self.in_type.addItem("⏰ رسالة تذكيرية (Reminder)", "reminder")
        self.in_type.addItem("⚠️ تنبيه هام / عاجل (Urgent)", "urgent")
        self.in_type.addItem("📢 إعلان عام (General)", "general")
        form.addRow("نوع وتصنيف الرسالة:", self.in_type)

        # 3. Content
        self.in_content = QTextEdit()
        self.in_content.setPlaceholderText("اكتب نص الرسالة التي ستظهر للمشتركين في شريط حساباتهم بالموقع...")
        self.in_content.setMinimumHeight(100)
        form.addRow("نص ومحتوى الرسالة *:", self.in_content)

        # 4. Display duration in seconds
        duration_layout = QHBoxLayout()
        self.in_duration = QSpinBox()
        self.in_duration.setRange(3, 60)
        self.in_duration.setValue(7)
        self.in_duration.setSuffix(" ثواني")
        self.in_duration.setFixedWidth(120)
        duration_hint = QLabel("(مدة بقاء الرسالة قبل التبديل للرسالة التالية تلقائياً)")
        duration_hint.setStyleSheet("color: #64748b; font-size: 12px;")
        duration_layout.addWidget(self.in_duration)
        duration_layout.addWidget(duration_hint)
        duration_layout.addStretch()
        form.addRow("مدة العرض بالشريط:", duration_layout)

        # 5. Target category
        self.in_category = QComboBox()
        self.in_category.addItem("جميع المشتركين (كافة الفئات)", "all")
        for cat in self.categories:
            self.in_category.addItem(f"فئة: {cat.name}", cat.name)
        form.addRow("الفئة المستهدفة:", self.in_category)

        # 6. Expiration Date & Time (وقت الانقطاع)
        exp_box = QGroupBox("وقت وتاريخ انتهاء وانقطاع الرسالة (Expiration)")
        exp_layout = QVBoxLayout(exp_box)
        exp_layout.setSpacing(10)

        self.chk_has_expiry = QCheckBox("تحديد موعد لانقطاع وانتهاء الرسالة تلقائياً")
        self.chk_has_expiry.setChecked(False)
        self.chk_has_expiry.toggled.connect(self.toggle_expiry_inputs)
        exp_layout.addWidget(self.chk_has_expiry)

        self.exp_inputs_widget = QWidget()
        exp_inputs_layout = QVBoxLayout(self.exp_inputs_widget)
        exp_inputs_layout.setContentsMargins(0, 0, 0, 0)
        exp_inputs_layout.setSpacing(8)

        self.in_expiry = QDateTimeEdit()
        self.in_expiry.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.in_expiry.setCalendarPopup(True)
        # Default expiry: 7 days from now
        now_dt = QDateTime.currentDateTime().addDays(7)
        self.in_expiry.setDateTime(now_dt)
        exp_inputs_layout.addWidget(self.in_expiry)

        # Quick preset buttons
        quick_btn_layout = QHBoxLayout()
        quick_btn_layout.setSpacing(6)
        
        btn_1d = QPushButton("+ يوم واحد")
        btn_1d.clicked.connect(lambda: self.in_expiry.setDateTime(QDateTime.currentDateTime().addDays(1)))
        btn_3d = QPushButton("+ 3 أيام")
        btn_3d.clicked.connect(lambda: self.in_expiry.setDateTime(QDateTime.currentDateTime().addDays(3)))
        btn_1w = QPushButton("+ أسبوع")
        btn_1w.clicked.connect(lambda: self.in_expiry.setDateTime(QDateTime.currentDateTime().addDays(7)))
        btn_1m = QPushButton("+ شهر")
        btn_1m.clicked.connect(lambda: self.in_expiry.setDateTime(QDateTime.currentDateTime().addMonths(1)))
        
        for b in [btn_1d, btn_3d, btn_1w, btn_1m]:
            b.setStyleSheet("background-color: #f1f5f9; color: #334155; font-size: 11px; padding: 4px 8px; border-radius: 6px;")
            quick_btn_layout.addWidget(b)
        quick_btn_layout.addStretch()
        exp_inputs_layout.addLayout(quick_btn_layout)

        self.exp_inputs_widget.setVisible(False)
        exp_layout.addWidget(self.exp_inputs_widget)

        form.addRow("", exp_box)

        # 7. Priority & Active status
        status_layout = QHBoxLayout()
        self.chk_is_active = QCheckBox("تفعيل الرسالة فوراً في الموقع")
        self.chk_is_active.setChecked(True)
        status_layout.addWidget(self.chk_is_active)
        status_layout.addSpacing(20)

        status_layout.addWidget(QLabel("ترتيب الأولوية:"))
        self.in_priority = QSpinBox()
        self.in_priority.setRange(1, 100)
        self.in_priority.setValue(1)
        self.in_priority.setFixedWidth(70)
        status_layout.addWidget(self.in_priority)
        status_layout.addStretch()

        form.addRow("حالة الظهور:", status_layout)

        layout.addWidget(form_frame)

        # Buttons
        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(10)
        btn_save = QPushButton("حفظ الرسالة")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setFixedHeight(45)
        btn_save.clicked.connect(self.save_data)

        btn_cancel = QPushButton("إلغاء")
        btn_cancel.setFixedHeight(45)
        btn_cancel.clicked.connect(self.reject)

        btns_layout.addWidget(btn_save)
        btns_layout.addWidget(btn_cancel)
        layout.addLayout(btns_layout)

        # Populate if editing
        if self.message:
            self.in_title.setText(self.message.title or "")
            self.in_content.setPlainText(self.message.content or "")
            self.in_duration.setValue(self.message.display_duration or 7)
            self.in_priority.setValue(self.message.priority or 1)
            self.chk_is_active.setChecked(bool(self.message.is_active))
            
            # Select type
            type_idx = self.in_type.findData(self.message.msg_type)
            if type_idx >= 0:
                self.in_type.setCurrentIndex(type_idx)

            # Select category
            cat_idx = self.in_category.findData(self.message.target_category or "all")
            if cat_idx >= 0:
                self.in_category.setCurrentIndex(cat_idx)

            # Expiry
            if self.message.end_date:
                self.chk_has_expiry.setChecked(True)
                self.exp_inputs_widget.setVisible(True)
                qdt = QDateTime(
                    self.message.end_date.year, self.message.end_date.month, self.message.end_date.day,
                    self.message.end_date.hour, self.message.end_date.minute, self.message.end_date.second
                )
                self.in_expiry.setDateTime(qdt)

    def toggle_expiry_inputs(self, checked):
        self.exp_inputs_widget.setVisible(checked)

    def save_data(self):
        title = self.in_title.text().strip()
        content = self.in_content.toPlainText().strip()

        if not title:
            ModernDialog(self, "تنبيه", "يرجى كتابة عنوان للرسالة").exec()
            return
        if not content:
            ModernDialog(self, "تنبيه", "يرجى كتابة نص ومحتوى الرسالة").exec()
            return

        end_date = None
        if self.chk_has_expiry.isChecked():
            qdt = self.in_expiry.dateTime()
            py_dt = datetime.datetime(
                qdt.date().year(), qdt.date().month(), qdt.date().day(),
                qdt.time().hour(), qdt.time().minute(), qdt.time().second()
            )
            if py_dt <= datetime.datetime.now():
                ModernDialog(self, "تنبيه", "تاريخ الانتهاء يجب أن يكون في المستقبل").exec()
                return
            end_date = py_dt

        self.result_data = {
            "title": title,
            "content": content,
            "msg_type": self.in_type.currentData(),
            "display_duration": self.in_duration.value(),
            "target_category": self.in_category.currentData(),
            "end_date": end_date,
            "is_active": self.chk_is_active.isChecked(),
            "priority": self.in_priority.value()
        }
        self.accept()


class MessagingMixin:
    def init_messaging_page(self):
        page = QScrollArea()
        page.setWidgetResizable(True)
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # Header Title
        title = QLabel("إدارة الرسائل والتوعية والتنبيهات للموقع")
        title.setObjectName("PageTitle")
        main_layout.addWidget(title)

        # Main Tab Widget
        self.msg_tabs = QTabWidget()
        self.msg_tabs.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        # =========================================================================
        # Tab 1: إدارة رسائل شريط الموقع للمشتركين (Awareness & Educational Banners)
        # =========================================================================
        tab_sub_messages = QWidget()
        sub_msg_layout = QVBoxLayout(tab_sub_messages)
        sub_msg_layout.setContentsMargins(20, 20, 20, 20)
        sub_msg_layout.setSpacing(15)

        # Top Stats Cards
        stats_frame = QHBoxLayout()
        stats_frame.setSpacing(15)

        self.stat_msg_total = self._create_stat_card("إجمالي الرسائل", "0", "#3b82f6")
        self.stat_msg_active = self._create_stat_card("الرسائل المعروضة في الموقع", "0", "#10b981")
        self.stat_msg_expired = self._create_stat_card("الرسائل المنتهية الصلاحية", "0", "#ef4444")
        
        stats_frame.addWidget(self.stat_msg_total)
        stats_frame.addWidget(self.stat_msg_active)
        stats_frame.addWidget(self.stat_msg_expired)
        sub_msg_layout.addLayout(stats_frame)

        # Action & Filter Bar
        action_bar = QHBoxLayout()
        action_bar.setSpacing(12)

        btn_add_msg = QPushButton("+ إضافة رسالة جديدة للموقع")
        btn_add_msg.setObjectName("PrimaryBtn")
        btn_add_msg.setFixedHeight(42)
        btn_add_msg.clicked.connect(self.add_subscriber_message_dialog)
        action_bar.addWidget(btn_add_msg)

        btn_refresh_msg = QPushButton("🔄 تحديث")
        btn_refresh_msg.setFixedHeight(42)
        btn_refresh_msg.clicked.connect(self.load_subscriber_messages)
        action_bar.addWidget(btn_refresh_msg)

        action_bar.addSpacing(15)

        action_bar.addWidget(QLabel("تصفية حسب النوع:"))
        self.filter_msg_type = QComboBox()
        self.filter_msg_type.addItem("الكل", "all")
        self.filter_msg_type.addItem("💡 توعوية", "awareness")
        self.filter_msg_type.addItem("📚 تعليمية", "educational")
        self.filter_msg_type.addItem("⏰ تذكيرية", "reminder")
        self.filter_msg_type.addItem("⚠️ تنبيه هام", "urgent")
        self.filter_msg_type.addItem("📢 إعلان عام", "general")
        self.filter_msg_type.currentIndexChanged.connect(self.load_subscriber_messages)
        action_bar.addWidget(self.filter_msg_type)

        action_bar.addWidget(QLabel("الحالة:"))
        self.filter_msg_status = QComboBox()
        self.filter_msg_status.addItem("الكل", "all")
        self.filter_msg_status.addItem("النشطة فقط 🟢", "active")
        self.filter_msg_status.addItem("المعطلة ⚪", "inactive")
        self.filter_msg_status.addItem("المنتهية ⌛", "expired")
        self.filter_msg_status.currentIndexChanged.connect(self.load_subscriber_messages)
        action_bar.addWidget(self.filter_msg_status)

        action_bar.addStretch()
        sub_msg_layout.addLayout(action_bar)

        # Messages Table
        self.tbl_sub_messages = QTableWidget()
        self.tbl_sub_messages.setColumnCount(8)
        self.tbl_sub_messages.setHorizontalHeaderLabels([
            "#", "نوع الرسالة", "عنوان الرسالة", "نص ومحتوى الرسالة", 
            "مدة العرض", "وقت الانتهاء / الانقطاع", "الحالة", "الإجراءات"
        ])
        self.tbl_sub_messages.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tbl_sub_messages.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_sub_messages.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl_sub_messages.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_sub_messages.setAlternatingRowColors(True)
        self.tbl_sub_messages.verticalHeader().setDefaultSectionSize(55)
        sub_msg_layout.addWidget(self.tbl_sub_messages)

        self.msg_tabs.addTab(tab_sub_messages, "📣 رسائل وتوعية المشتركين في الموقع")

        # =========================================================================
        # Tab 2: إعدادات بوابة SMS ونماذج الإشعارات التلقائية
        # =========================================================================
        tab_sms_settings = QWidget()
        sms_layout = QVBoxLayout(tab_sms_settings)
        sms_layout.setContentsMargins(20, 20, 20, 20)
        sms_layout.setSpacing(20)

        # Section 1: Gateway Settings
        gateway_card = QFrame()
        gateway_card.setObjectName("StatCard")
        g_layout = QVBoxLayout(gateway_card)
        g_layout.setSpacing(15)
        g_title = QLabel("إعدادات بوابة الإرسال (SMS Gateway)")
        g_title.setObjectName("SectionTitle")
        g_layout.addWidget(g_title)
        
        form = QFormLayout()
        self.msg_api_key = QLineEdit()
        self.msg_gateway_url = QLineEdit()
        self.msg_sender_id = QLineEdit()
        form.addRow("API Key:", self.msg_api_key)
        form.addRow("Gateway URL:", self.msg_gateway_url)
        form.addRow("Sender ID:", self.msg_sender_id)
        g_layout.addLayout(form)
        sms_layout.addWidget(gateway_card)

        # Section 2: Templates
        temp_card = QFrame()
        temp_card.setObjectName("StatCard")
        t_layout = QVBoxLayout(temp_card)
        t_layout.setSpacing(15)
        t_title = QLabel("نماذج الرسائل التلقائية")
        t_title.setObjectName("SectionTitle")
        t_layout.addWidget(t_title)
        
        self.temp_welcome = QTextEdit()
        self.temp_welcome.setMaximumHeight(80)
        self.temp_welcome.setPlaceholderText("رسالة الترحيب عند التسجيل...")
        self.temp_payment = QTextEdit()
        self.temp_payment.setMaximumHeight(80)
        self.temp_payment.setPlaceholderText("تذكير موعد السداد...")
        self.temp_delivery = QTextEdit()
        self.temp_delivery.setMaximumHeight(80)
        self.temp_delivery.setPlaceholderText("إشعار استلام القسط/التسليم...")
        self.temp_winner = QTextEdit()
        self.temp_winner.setMaximumHeight(80)
        self.temp_winner.setPlaceholderText("إشعار الفوز في القرعة...")
        
        t_layout.addWidget(QLabel("رسالة الترحيب:"))
        t_layout.addWidget(self.temp_welcome)
        t_layout.addWidget(QLabel("تذكير السداد:"))
        t_layout.addWidget(self.temp_payment)
        t_layout.addWidget(QLabel("إشعار تسديد القسط:"))
        t_layout.addWidget(self.temp_delivery)
        t_layout.addWidget(QLabel("إشعار الفوز:"))
        t_layout.addWidget(self.temp_winner)
        sms_layout.addWidget(temp_card)

        # Save Button
        btn_save = QPushButton("حفظ إعدادات بوابة SMS والنماذج")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setFixedHeight(48)
        btn_save.clicked.connect(self.save_messaging_settings)
        sms_layout.addWidget(btn_save)

        # Section 3: Broadcast
        broad_card = QFrame()
        broad_card.setObjectName("StatCard")
        b_layout = QVBoxLayout(broad_card)
        b_layout.setSpacing(15)
        b_title = QLabel("إرسال رسالة جماعية (Broadcast SMS)")
        b_title.setObjectName("SectionTitle")
        b_layout.addWidget(b_title)
        
        self.broad_text = QTextEdit()
        self.broad_text.setPlaceholderText("اكتب نص الرسالة هنا لإرسالها لجميع المشتركين عبر SMS...")
        self.broad_text.setMinimumHeight(100)
        b_layout.addWidget(self.broad_text)
        
        btn_broad = QPushButton("إرسال للجميع الآن عبر SMS")
        btn_broad.setObjectName("PrimaryBtn")
        btn_broad.setFixedHeight(48)
        btn_broad.clicked.connect(self.send_broadcast)
        b_layout.addWidget(btn_broad)
        sms_layout.addWidget(broad_card)

        self.msg_tabs.addTab(tab_sms_settings, "⚙️ إعدادات بوابة SMS ونماذج الرسائل")

        main_layout.addWidget(self.msg_tabs)

        page.setWidget(container)
        return page

    def _create_stat_card(self, title, val, color="#10b981"):
        card = QFrame()
        card.setObjectName("StatCard")
        card.setStyleSheet(f"QFrame#StatCard {{ border-top: 4px solid {color}; }}")
        l = QVBoxLayout(card)
        l.setContentsMargins(15, 12, 15, 12)
        l.setSpacing(5)
        
        lbl_title = QLabel(title)
        lbl_title.setObjectName("StatTitle")
        l.addWidget(lbl_title)
        
        lbl_val = QLabel(val)
        lbl_val.setObjectName("StatValue")
        lbl_val.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: 900;")
        l.addWidget(lbl_val)
        
        card.val_label = lbl_val
        return card

    # =========================================================================
    # Methods for Subscriber Messages Management
    # =========================================================================
    def load_subscriber_messages(self):
        self.db.rollback()
        self.db.expire_all()
        now = datetime.datetime.now()

        query = self.db.query(db_mod.SubscriberMessage)

        # Filters
        type_filter = getattr(self, 'filter_msg_type', None)
        if type_filter and type_filter.currentData() != "all":
            query = query.filter(db_mod.SubscriberMessage.msg_type == type_filter.currentData())

        status_filter = getattr(self, 'filter_msg_status', None)
        if status_filter:
            st = status_filter.currentData()
            if st == "active":
                query = query.filter(
                    db_mod.SubscriberMessage.is_active == True,
                    or_(db_mod.SubscriberMessage.end_date == None, db_mod.SubscriberMessage.end_date >= now)
                )
            elif st == "inactive":
                query = query.filter(db_mod.SubscriberMessage.is_active == False)
            elif st == "expired":
                query = query.filter(
                    db_mod.SubscriberMessage.end_date != None,
                    db_mod.SubscriberMessage.end_date < now
                )

        messages = query.order_by(db_mod.SubscriberMessage.priority.asc(), db_mod.SubscriberMessage.id.desc()).all()

        # Update stats
        all_msgs = self.db.query(db_mod.SubscriberMessage).all()
        total_count = len(all_msgs)
        active_count = sum(1 for m in all_msgs if m.is_active and (m.end_date is None or m.end_date >= now))
        expired_count = sum(1 for m in all_msgs if m.end_date is not None and m.end_date < now)

        if hasattr(self, 'stat_msg_total') and hasattr(self.stat_msg_total, 'val_label'):
            self.stat_msg_total.val_label.setText(str(total_count))
        if hasattr(self, 'stat_msg_active') and hasattr(self.stat_msg_active, 'val_label'):
            self.stat_msg_active.val_label.setText(str(active_count))
        if hasattr(self, 'stat_msg_expired') and hasattr(self.stat_msg_expired, 'val_label'):
            self.stat_msg_expired.val_label.setText(str(expired_count))

        # Fill table
        self.tbl_sub_messages.setRowCount(0)
        self.tbl_sub_messages.setRowCount(len(messages))

        type_map = {
            "awareness": ("💡 توعوية", "#10b981"),
            "educational": ("📚 تعليمية", "#3b82f6"),
            "reminder": ("⏰ تذكيرية", "#f59e0b"),
            "urgent": ("⚠️ تنبيه هام", "#ef4444"),
            "general": ("📢 إعلان عام", "#8b5cf6")
        }

        for row, msg in enumerate(messages):
            # 0. ID
            item_id = QTableWidgetItem(str(msg.id))
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_sub_messages.setItem(row, 0, item_id)

            # 1. Type
            type_text, type_color = type_map.get(msg.msg_type, ("📢 إعلان", "#64748b"))
            item_type = QTableWidgetItem(type_text)
            item_type.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_type.setForeground(QColor(type_color))
            self.tbl_sub_messages.setItem(row, 1, item_type)

            # 2. Title
            item_title = QTableWidgetItem(msg.title or "")
            item_title.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_sub_messages.setItem(row, 2, item_title)

            # 3. Content preview
            clean_content = (msg.content or "").replace("\n", " ")
            if len(clean_content) > 60:
                clean_content = clean_content[:57] + "..."
            item_content = QTableWidgetItem(clean_content)
            item_content.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_content.setToolTip(msg.content or "")
            self.tbl_sub_messages.setItem(row, 3, item_content)

            # 4. Duration
            item_dur = QTableWidgetItem(f"{msg.display_duration or 7} ثواني")
            item_dur.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_sub_messages.setItem(row, 4, item_dur)

            # 5. Expiry Date
            if msg.end_date:
                is_expired = msg.end_date < now
                exp_str = msg.end_date.strftime('%Y-%m-%d %H:%M')
                item_exp = QTableWidgetItem(f"⌛ {exp_str}" if is_expired else exp_str)
                if is_expired:
                    item_exp.setForeground(QColor("#ef4444"))
            else:
                item_exp = QTableWidgetItem("♾️ مستمرة دائماً")
                item_exp.setForeground(QColor("#64748b"))
            item_exp.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_sub_messages.setItem(row, 5, item_exp)

            # 6. Status
            if not msg.is_active:
                status_text = "⚪ معطلة"
                status_color = "#94a3b8"
            elif msg.end_date and msg.end_date < now:
                status_text = "⌛ منتهية الصلاحية"
                status_color = "#ef4444"
            else:
                status_text = "🟢 نشطة بالموقع"
                status_color = "#10b981"

            item_status = QTableWidgetItem(status_text)
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_status.setForeground(QColor(status_color))
            self.tbl_sub_messages.setItem(row, 6, item_status)

            # 7. Actions Widget
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            # Toggle button
            btn_toggle = QPushButton("تعطيل" if msg.is_active else "تفعيل")
            btn_toggle.setStyleSheet("background-color: #f1f5f9; color: #334155; padding: 4px 8px; border-radius: 6px; font-size: 11px;")
            btn_toggle.clicked.connect(lambda _, m_id=msg.id: self.toggle_subscriber_message(m_id))
            actions_layout.addWidget(btn_toggle)

            # Edit button
            btn_edit = QPushButton("تعديل")
            btn_edit.setStyleSheet("background-color: #d1fae5; color: #065f46; padding: 4px 8px; border-radius: 6px; font-size: 11px;")
            btn_edit.clicked.connect(lambda _, m_id=msg.id: self.edit_subscriber_message_dialog(m_id))
            actions_layout.addWidget(btn_edit)

            # Delete button
            btn_del = QPushButton("حذف")
            btn_del.setStyleSheet("background-color: #fee2e2; color: #991b1b; padding: 4px 8px; border-radius: 6px; font-size: 11px;")
            btn_del.clicked.connect(lambda _, m_id=msg.id: self.delete_subscriber_message(m_id))
            actions_layout.addWidget(btn_del)

            self.tbl_sub_messages.setCellWidget(row, 7, actions_widget)

    def add_subscriber_message_dialog(self):
        categories = self.db.query(db_mod.Category).filter(db_mod.Category.is_active == True).all()
        dialog = SubscriberMessageEditDialog(self, categories=categories)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.result_data
            new_msg = db_mod.SubscriberMessage(
                title=data["title"],
                content=data["content"],
                msg_type=data["msg_type"],
                display_duration=data["display_duration"],
                target_category=data["target_category"],
                end_date=data["end_date"],
                is_active=data["is_active"],
                priority=data["priority"]
            )
            self.db.add(new_msg)
            self.db.commit()
            ModernDialog(self, "نجاح", "تمت إضافة الرسالة بنجاح وستظهر في الموقع وفق الإعدادات المحددة").exec()
            self.load_subscriber_messages()

    def edit_subscriber_message_dialog(self, msg_id):
        msg = self.db.query(db_mod.SubscriberMessage).filter(db_mod.SubscriberMessage.id == msg_id).first()
        if not msg:
            ModernDialog(self, "خطأ", "الرسالة غير موجودة").exec()
            return

        categories = self.db.query(db_mod.Category).filter(db_mod.Category.is_active == True).all()
        dialog = SubscriberMessageEditDialog(self, message=msg, categories=categories)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.result_data
            msg.title = data["title"]
            msg.content = data["content"]
            msg.msg_type = data["msg_type"]
            msg.display_duration = data["display_duration"]
            msg.target_category = data["target_category"]
            msg.end_date = data["end_date"]
            msg.is_active = data["is_active"]
            msg.priority = data["priority"]
            self.db.commit()
            ModernDialog(self, "نجاح", "تم تحديث بيانات الرسالة بنجاح").exec()
            self.load_subscriber_messages()

    def toggle_subscriber_message(self, msg_id):
        msg = self.db.query(db_mod.SubscriberMessage).filter(db_mod.SubscriberMessage.id == msg_id).first()
        if msg:
            msg.is_active = not msg.is_active
            self.db.commit()
            self.load_subscriber_messages()

    def delete_subscriber_message(self, msg_id):
        msg = self.db.query(db_mod.SubscriberMessage).filter(db_mod.SubscriberMessage.id == msg_id).first()
        if not msg:
            return
        if ModernDialog(self, "تأكيد الحذف", f"هل أنت متأكد من حذف الرسالة: «{msg.title}» بشكل نهائي؟", is_confirm=True).exec():
            self.db.delete(msg)
            self.db.commit()
            ModernDialog(self, "نجاح", "تم حذف الرسالة بنجاح").exec()
            self.load_subscriber_messages()

    # =========================================================================
    # Methods for SMS Settings
    # =========================================================================
    def load_messaging_settings(self):
        keys = ["msg_api_key", "msg_gateway_url", "msg_sender_id", "temp_welcome", "temp_payment", "temp_delivery", "temp_winner"]
        settings = {s.key: s.value for s in self.db.query(db_mod.Setting).filter(db_mod.Setting.key.in_(keys)).all()}
        
        if hasattr(self, 'msg_api_key'):
            self.msg_api_key.setText(settings.get("msg_api_key", ""))
            self.msg_gateway_url.setText(settings.get("msg_gateway_url", ""))
            self.msg_sender_id.setText(settings.get("msg_sender_id", ""))
            self.temp_welcome.setPlainText(settings.get("temp_welcome", "أهلاً بك في هكبة المليون، تم تسجيلك بنجاح."))
            self.temp_payment.setPlainText(settings.get("temp_payment", "عزيزي المشترك، نود تذكيرك بموعد قسط الهكبة."))
            self.temp_delivery.setPlainText(settings.get("temp_delivery", "شكراً لك، تم استلام مبلغ القسط الخاص بك بنجاح."))
            self.temp_winner.setPlainText(settings.get("temp_winner", "نبارك لك الفوز في قرعة هكبة المليون لهذا الشهر!"))
        
        self.load_subscriber_messages()

    def save_messaging_settings(self):
        data = {
            "msg_api_key": self.msg_api_key.text(),
            "msg_gateway_url": self.msg_gateway_url.text(),
            "msg_sender_id": self.msg_sender_id.text(),
            "temp_welcome": self.temp_welcome.toPlainText(),
            "temp_payment": self.temp_payment.toPlainText(),
            "temp_delivery": self.temp_delivery.toPlainText(),
            "temp_winner": self.temp_winner.toPlainText()
        }
        for k, v in data.items():
            s = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == k).first()
            if s: s.value = v
            else: self.db.add(db_mod.Setting(key=k, value=v))
        self.db.commit()
        ModernDialog(self, "نجاح", "تم حفظ إعدادات الرسائل ونماذج SMS بنجاح").exec()

    def send_broadcast(self):
        msg = self.broad_text.toPlainText().strip()
        if not msg:
            ModernDialog(self, "تنبيه", "يرجى كتابة نص الرسالة أولاً").exec()
            return
        
        count = self.db.query(db_mod.Subscriber).count()
        if ModernDialog(self, "تأكيد", f"هل أنت متأكد من إرسال هذه الرسالة إلى {count} مشترك عبر SMS؟", is_confirm=True).exec():
            ModernDialog(self, "نجاح", f"تم وضع {count} رسالة في قائمة الإرسال").exec()
            self.broad_text.clear()
