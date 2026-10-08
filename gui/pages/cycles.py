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

class CyclesMixin:
    def init_cycles_page(self):
        page = QScrollArea(); page.setWidgetResizable(True); container = QWidget(); layout = QVBoxLayout(container); layout.setContentsMargins(40, 40, 40, 40); layout.setSpacing(30)
        title = QLabel("إدارة الدورات والأقساط"); title.setObjectName("PageTitle"); layout.addWidget(title)
        
        f1 = QFrame(); f1.setObjectName("StatCard"); form = QFormLayout(f1); form.setSpacing(15)
        
        self.cyc_cat = QComboBox()
        self.cyc_cat.currentIndexChanged.connect(self.load_category_cycle_settings)
        self.cyc_count = QLineEdit(); self.cyc_count.setPlaceholderText("مثال: 2")
        self.cyc_inst_count = QLineEdit(); self.cyc_inst_count.setPlaceholderText("مثال: 12")
        
        self.cyc_start = QDateEdit(); self.cyc_start.setCalendarPopup(True); self.cyc_start.setDate(QDate.currentDate())
        self.cyc_end = QDateEdit(); self.cyc_end.setCalendarPopup(True); self.cyc_end.setDate(QDate.currentDate().addYears(1))
        
        # Auto-calculate end date
        self.cyc_start.dateChanged.connect(self.update_auto_end_date)
        self.cyc_count.textChanged.connect(lambda: self.update_auto_end_date())
        self.cyc_inst_count.textChanged.connect(lambda: self.update_auto_end_date())
        
        form.addRow("اختر الفئة:", self.cyc_cat)
        form.addRow("إجمالي عدد الدورات:", self.cyc_count)
        form.addRow("عدد الأقساط في كل دورة:", self.cyc_inst_count)
        form.addRow("تاريخ بداية أول دورة:", self.cyc_start)
        form.addRow("تاريخ نهاية آخر دورة:", self.cyc_end)
        
        btn_save_settings = QPushButton("حفظ الإعدادات لهذه الفئة فقط")
        btn_save_settings.setObjectName("PrimaryBtn")
        btn_save_settings.setFixedHeight(50)
        btn_save_settings.clicked.connect(self.save_cycle_settings)
        
        btn_gen = QPushButton("توليد جدول الأقساط لجميع المشتركين")
        btn_gen.setObjectName("PrimaryBtn")
        btn_gen.setFixedHeight(50)
        btn_gen.clicked.connect(self.generate_cycle_schedule)
        
        layout.addWidget(f1)
        layout.addWidget(btn_save_settings)
        layout.addWidget(btn_gen)
        
        info = QLabel("تنبيه: هذا الإجراء سيقوم بإنشاء سجلات دفع مستقبلية لجميع المشتركين في الفئة المختارة بناءً على الإعدادات أعلاه.")
        info.setStyleSheet("color: #94a3b8; font-size: 13px;")
        layout.addWidget(info)
        
        layout.addStretch(); page.setWidget(container); return page
    def refresh_cycles_cat_list(self):
        self.cyc_cat.clear()
        for c in self.db.query(db_mod.Category).all(): self.cyc_cat.addItem(c.name, c.id)
    def load_category_cycle_settings(self):
        cat_id = self.cyc_cat.currentData()
        if not cat_id: return
        cat = self.db.get(db_mod.Category, cat_id)
        if cat:
            self.cyc_count.setText(str(cat.max_cycles))
            self.cyc_inst_count.setText(str(cat.max_installments))
            if cat.start_date:
                self.cyc_start.setDate(QDate(cat.start_date.year, cat.start_date.month, cat.start_date.day))
            if cat.end_date:
                self.cyc_end.setDate(QDate(cat.end_date.year, cat.end_date.month, cat.end_date.day))
    def update_auto_end_date(self):
        try:
            c_text = self.cyc_count.text().strip()
            i_text = self.cyc_inst_count.text().strip()
            if not c_text or not i_text: return
            
            cycles = int(c_text)
            inst = int(i_text)
            start = self.cyc_start.date().toPyDate()
            
            total_inst = cycles * inst
            if total_inst > 0:
                # Daily Hakbah logic: 1 day per installment
                days = (total_inst - 1) * 1
                end = start + datetime.timedelta(days=days)
                self.cyc_end.setDate(QDate(end.year, end.month, end.day))
        except:
            pass
    def save_cycle_settings(self):
        cat_id = self.cyc_cat.currentData()
        if not cat_id: return
        
        try:
            cycles = int(self.cyc_count.text().strip())
            inst_per_cycle = int(self.cyc_inst_count.text().strip())
            
            cat = self.db.get(db_mod.Category, cat_id)
            cat.max_cycles = cycles
            cat.max_installments = inst_per_cycle
            cat.start_date = datetime.datetime.combine(self.cyc_start.date().toPyDate(), datetime.time.min)
            cat.end_date = datetime.datetime.combine(self.cyc_end.date().toPyDate(), datetime.time.min)
            self.db.commit()
            
            ModernDialog(self, "نجاح", f"تم حفظ إعدادات الفئة {cat.name} بنجاح").exec()
        except ValueError:
            ModernDialog(self, "خطأ", "يرجى إدخال أرقام صحيحة للدورات والأقساط").exec()
    def generate_cycle_schedule(self):
        cat_id = self.cyc_cat.currentData()
        if not cat_id: return
        
        try:
            cycles = int(self.cyc_count.text().strip())
            inst_per_cycle = int(self.cyc_inst_count.text().strip())
            start_date = self.cyc_start.date().toPyDate()
            
            total_installments = cycles * inst_per_cycle
            if total_installments < 1:
                ModernDialog(self, "خطأ", "يجب أن يكون إجمالي الأقساط قسطاً واحداً على الأقل").exec()
                return
            
            cat = self.db.get(db_mod.Category, cat_id)
            cat.max_cycles = cycles
            cat.max_installments = inst_per_cycle
            self.db.commit()
            
            subs = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == cat.name).all()
            
            if not subs:
                ModernDialog(self, "تنبيه", "لا يوجد مشتركون في هذه الفئة حالياً").exec()
                return
            
            if ModernDialog(self, "تأكيد", f"سيتم إنشاء {total_installments} سجل دفع (بمعدل قسط واحد يومياً) لكل مشترك. هل أنت متأكد؟", is_confirm=True).exec():
                total_created = 0
                for c_idx in range(1, cycles + 1):
                    for i_idx in range(1, inst_per_cycle + 1):
                        # Calculate global installment index
                        global_idx = (c_idx - 1) * inst_per_cycle + (i_idx - 1)
                        days_to_add = global_idx
                        
                        due_date = start_date + datetime.timedelta(days=days_to_add)
                        due_datetime = datetime.datetime.combine(due_date, datetime.time.min)
                        
                        for sub in subs:
                            exists = self.db.query(db_mod.Payment).filter(
                                db_mod.Payment.subscriber_id == sub.id,
                                db_mod.Payment.cycle_number == c_idx,
                                db_mod.Payment.installment_number == i_idx
                            ).first()
                            
                            if not exists:
                                new_p = db_mod.Payment(
                                    subscriber_id=sub.id,
                                    amount=cat.amount,
                                    due_date=due_datetime,
                                    is_paid=False,
                                    cycle_number=c_idx,
                                    installment_number=i_idx,
                                    note=f"دورة {c_idx} - قسط {i_idx}"
                                )
                                self.db.add(new_p)
                                total_created += 1
                
                self.db.commit()
                ModernDialog(self, "نجاح", f"تم توليد {total_created} سجل دفع بنجاح لـ {len(subs)} مشترك").exec()
        except ValueError:
            ModernDialog(self, "خطأ", "يرجى إدخال أرقام صحيحة للدورات والأقساط").exec()
        except Exception as e:
            self.db.rollback()
            ModernDialog(self, "خطأ", str(e)).exec()
