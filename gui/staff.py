from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import database as db_mod
import security
from gui.dialogs import ModernDialog, AddStaffDialog

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
        for i in reversed(range(self.staff_grid.count())): 
            self.staff_grid.itemAt(i).widget().setParent(None)
            
        staff_members = self.db.query(db_mod.Staff).all()
        cols = 3
        for idx, s in enumerate(staff_members):
            card = self.create_staff_card(s)
            self.staff_grid.addWidget(card, idx // cols, idx % cols)
        
        self.staff_grid.setRowStretch(self.staff_grid.rowCount(), 1)

    def create_staff_card(self, s):
        card = QFrame()
        card.setObjectName("StatCard")
        card.setMinimumHeight(180)
        card.setStyleSheet("QFrame#StatCard { border: 1px solid #e2e8f0; border-radius: 12px; background: white; }")
        
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 20, 20, 20)
        
        name_lbl = QLabel(s.name)
        name_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        lay.addWidget(name_lbl)
        
        id_lbl = QLabel(f"رقم الموظف: {s.staff_id_code}")
        id_lbl.setStyleSheet("color: #64748b;")
        lay.addWidget(id_lbl)
        
        phone_lbl = QLabel(f"الهاتف: {s.phone}")
        phone_lbl.setStyleSheet("color: #64748b;")
        lay.addWidget(phone_lbl)
        
        lay.addStretch()
        
        btn_del = QPushButton("حذف الموظف")
        btn_del.setObjectName("DangerBtn")
        btn_del.setFixedHeight(30)
        btn_del.clicked.connect(lambda: self.delete_staff(s.id))
        lay.addWidget(btn_del)
        
        return card

    def add_new_staff(self):
        dlg = AddStaffDialog(self)
        if dlg.exec():
            name = dlg.ent_name.text()
            phone = dlg.ent_phone.text()
            s_id = dlg.ent_staff_id.text()
            pwd = dlg.ent_pwd.text()
            
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
                    password=security.hash_password(pwd)
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