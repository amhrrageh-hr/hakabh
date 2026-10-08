from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import database as db_mod
import security
from gui.dialogs import ModernDialog, AddStaffDialog, StaffActivityDialog
from sqlalchemy import func

class StaffMixin:
    def init_staff_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        header = QHBoxLayout()
        title = QLabel("إدارة الموظفين")
        title.setObjectName("PageTitle")
        header.addWidget(title)

        btn_add = QPushButton("إنشاء حساب موظف")
        btn_add.setObjectName("PrimaryBtn")
        btn_add.setFixedHeight(40)
        btn_add.clicked.connect(self.add_new_staff)
        header.addStretch()
        header.addWidget(btn_add)
        layout.addLayout(header)

        self.staff_scroll = QScrollArea()
        self.staff_scroll.setWidgetResizable(True)
        self.staff_scroll.setStyleSheet("background: transparent; border: none;")
        
        self.staff_container = QWidget()
        self.staff_grid = QGridLayout(self.staff_container)
        self.staff_grid.setSpacing(20)
        self.staff_scroll.setWidget(self.staff_container)
        
        layout.addWidget(self.staff_scroll)
        return page

    def show_staff_management(self):
        self.content_stack.setCurrentWidget(self.page_staff)
        self._update_nav_style("إدارة الموظفين")
        self.load_staff_list()

    def load_staff_list(self):
        # Clear grid
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all()
        for i in reversed(range(self.staff_grid.count())): 
            self.staff_grid.itemAt(i).widget().setParent(None)
            
        staff_members = self.db.query(db_mod.Staff).all()
        cols = 2
        for idx, s in enumerate(staff_members):
            card = self.create_staff_card(s)
            self.staff_grid.addWidget(card, idx // cols, idx % cols)
        
        self.staff_grid.setRowStretch(self.staff_grid.rowCount(), 1)

    def create_staff_card(self, s):
        card = QFrame()
        card.setObjectName("StatCard")
        card.setMinimumHeight(240)
        card.setMinimumWidth(380)
        
        # Get theme
        theme_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "admin_theme").first()
        theme = theme_setting.value if theme_setting else "dark"
        is_dark = (theme == "dark")
        
        bg_style = "background: #1e293b; border: 1px solid #334155;" if is_dark else "background: white; border: 1px solid #e2e8f0;"
        text_color = "color: #f1f5f9;" if is_dark else "color: #1e293b;"
        lbl_muted_color = "color: #94a3b8;" if is_dark else "color: #64748b;"
        hover_border = "#4ade80" if is_dark else "#2e7d32"
        
        card.setStyleSheet(f"""
            QFrame#StatCard {{
                {bg_style}
                border-radius: 16px;
            }}
            QFrame#StatCard:hover {{
                border: 2px solid {hover_border};
            }}
        """)
        
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(15)
        
        # Header layout (Avatar + Info)
        header_lay = QHBoxLayout()
        header_lay.setSpacing(12)
        
        # Avatar
        avatar = QLabel()
        avatar.setFixedSize(50, 50)
        parts = s.name.strip().split()
        initials = "".join([p[0] for p in parts if p][:2]) if parts else "م"
        avatar.setText(initials)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Tajawal", 12, QFont.Weight.Bold))
        avatar.setStyleSheet("""
            background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #10b981, stop:1 #059669);
            color: white;
            border-radius: 25px;
        """)
        header_lay.addWidget(avatar)
        
        # Staff Details Info
        info_lay = QVBoxLayout()
        info_lay.setSpacing(3)
        
        name_lbl = QLabel(s.name)
        name_lbl.setFont(QFont("Tajawal", 13, QFont.Weight.Bold))
        name_lbl.setStyleSheet(text_color)
        info_lay.addWidget(name_lbl)
        
        id_lbl = QLabel(f"رقم الموظف: {s.staff_id_code}")
        id_lbl.setFont(QFont("Tajawal", 9))
        id_lbl.setStyleSheet(lbl_muted_color)
        info_lay.addWidget(id_lbl)
        
        phone_lbl = QLabel(f"الهاتف: {s.phone}")
        phone_lbl.setFont(QFont("Tajawal", 9))
        phone_lbl.setStyleSheet(lbl_muted_color)
        info_lay.addWidget(phone_lbl)
        
        header_lay.addLayout(info_lay)
        header_lay.addStretch()
        
        # Status Badge (Active)
        status_badge = QLabel("نشط")
        status_badge.setFont(QFont("Tajawal", 8, QFont.Weight.Bold))
        status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_badge.setStyleSheet("""
            background: #d1fae5;
            color: #065f46;
            padding: 4px 10px;
            border-radius: 10px;
        """)
        header_lay.addWidget(status_badge)
        
        lay.addLayout(header_lay)
        
        # Divider Line
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider_color = "#334155" if is_dark else "#f1f5f9"
        divider.setStyleSheet(f"background-color: {divider_color}; max-height: 1px;")
        lay.addWidget(divider)
        
        # Statistics Layout
        stats_lay = QGridLayout()
        stats_lay.setSpacing(8)
        
        # Calculate stats for this staff
        collected_count = self.db.query(db_mod.Payment).filter(db_mod.Payment.staff_id == s.id, db_mod.Payment.is_paid == True).count()
        collected_sum = self.db.query(func.sum(db_mod.Payment.amount)).filter(db_mod.Payment.staff_id == s.id, db_mod.Payment.is_paid == True).scalar() or 0
        
        lbl_col_title = QLabel("العمليات المحصلة:")
        lbl_col_title.setFont(QFont("Tajawal", 9))
        lbl_col_title.setStyleSheet(lbl_muted_color)
        stats_lay.addWidget(lbl_col_title, 0, 0)
        
        lbl_col_val = QLabel(f"{collected_count} عملية")
        lbl_col_val.setFont(QFont("Tajawal", 10, QFont.Weight.Bold))
        lbl_col_val.setStyleSheet("color: #10b981;")
        stats_lay.addWidget(lbl_col_val, 0, 1)
        
        lbl_sum_title = QLabel("إجمالي المبالغ:")
        lbl_sum_title.setFont(QFont("Tajawal", 9))
        lbl_sum_title.setStyleSheet(lbl_muted_color)
        stats_lay.addWidget(lbl_sum_title, 1, 0)
        
        lbl_sum_val = QLabel(f"{collected_sum:,.2f} ر.ي")
        lbl_sum_val.setFont(QFont("Tajawal", 10, QFont.Weight.Bold))
        lbl_sum_val.setStyleSheet("color: #3b82f6;" if is_dark else "color: #1e3a8a;")
        stats_lay.addWidget(lbl_sum_val, 1, 1)
        
        lay.addLayout(stats_lay)
        
        # Action Buttons
        actions_lay = QHBoxLayout()
        actions_lay.setSpacing(6)
        
        btn_activity = QPushButton("سجل العمليات")
        btn_activity.setObjectName("PrimaryBtn")
        btn_activity.setFixedHeight(30)
        btn_activity.setStyleSheet("font-size: 11px;")
        btn_activity.clicked.connect(lambda checked, sid=s.id: self.open_staff_activity(sid))
        actions_lay.addWidget(btn_activity, 2)
        
        btn_del = QPushButton("حذف")
        btn_del.setObjectName("DangerBtn")
        btn_del.setFixedHeight(30)
        btn_del.setStyleSheet("font-size: 11px;")
        btn_del.clicked.connect(lambda checked, sid=s.id: self.delete_staff(sid))
        actions_lay.addWidget(btn_del, 1)
        
        lay.addLayout(actions_lay)
        
        # double click on card to view activity details
        card.mouseDoubleClickEvent = lambda event: self.open_staff_activity(s.id)
        
        # Context Menu (Right Click)
        card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pos, c=card, sid=s.id: self.show_staff_context_menu(c, pos, sid))
        
        return card

    def open_staff_activity(self, sid):
        StaffActivityDialog(self, sid, self.db).exec()

    def add_new_staff(self):
        dlg = AddStaffDialog(self)
        if dlg.exec():
            name = dlg.ent_name.text()
            phone = dlg.ent_phone.text()
            s_id = dlg.ent_staff_id.text()
            pwd = dlg.ent_pwd.text()
            role = dlg.role_combo.currentText()
            
            # Check if ID exists
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
                self.load_staff_list()
                ModernDialog(self, "نجاح", "تم إنشاء حساب الموظف بنجاح").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ: {e}").exec()

    def delete_staff(self, sid):
        if ModernDialog(self, "تأكيد", "هل أنت متأكد من حذف هذا الموظف؟", is_confirm=True).exec():
            try:
                s = self.db.get(db_mod.Staff, sid)
                if s:
                    self.db.delete(s)
                    self.db.commit()
                    self.load_staff_list()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", str(e)).exec()

    def show_staff_context_menu(self, widget, pos, sid):
        menu = QMenu(widget)
        # تحديد الألوان بناءً على الثيم سيكون أفضل، لكن هذا تصميم محايد وعصري
        menu.setStyleSheet("""
            QMenu { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 5px; color: #1e293b;}
            QMenu::item { padding: 8px 30px 8px 30px; font-size: 14px; font-family: Tajawal;}
            QMenu::item:selected { background-color: #f1f5f9; color: #3b82f6; }
        """)
        
        edit_action = QAction("تعديل", widget)
        edit_action.triggered.connect(lambda: self.edit_staff(sid))
        menu.addAction(edit_action)
        
        del_action = QAction("حذف", widget)
        del_action.triggered.connect(lambda: self.delete_staff(sid))
        menu.addAction(del_action)
        
        menu.exec(widget.mapToGlobal(pos))

    def edit_staff(self, sid):
        staff = self.db.get(db_mod.Staff, sid)
        if not staff: return
        
        dlg = AddStaffDialog(self)
        dlg.setWindowTitle("تعديل بيانات الموظف")
        dlg.ent_name.setText(staff.name)
        dlg.ent_phone.setText(staff.phone)
        dlg.ent_staff_id.setText(staff.staff_id_code)
        dlg.ent_pwd.setPlaceholderText("اتركه فارغاً للإبقاء على الكلمة القديمة")
        if staff.role:
            dlg.role_combo.setCurrentText(staff.role)
        
        if dlg.exec():
            new_name = dlg.ent_name.text().strip()
            new_phone = dlg.ent_phone.text().strip()
            new_id = dlg.ent_staff_id.text().strip()
            new_pwd = dlg.ent_pwd.text().strip()
            new_role = dlg.role_combo.currentText()
            
            if not new_name or not new_id:
                ModernDialog(self, "خطأ", "يجب إدخال اسم الموظف ورقمه").exec()
                return

            if new_id != staff.staff_id_code:
                exists = self.db.query(db_mod.Staff).filter(db_mod.Staff.staff_id_code == new_id).first()
                if exists:
                    ModernDialog(self, "خطأ", "رقم الموظف الجديد مسجل مسبقاً لموظف آخر").exec()
                    return
            
            try:
                staff.name = new_name
                staff.phone = new_phone
                staff.staff_id_code = new_id
                staff.role = new_role
                if new_pwd:
                    staff.password = security.hash_password(new_pwd)
                self.db.commit()
                self.load_staff_list()
                ModernDialog(self, "نجاح", "تم تعديل بيانات الموظف بنجاح").exec()
            except Exception as e:
                self.db.rollback()
                ModernDialog(self, "خطأ", f"حدث خطأ: {e}").exec()