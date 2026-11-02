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


class _CycleScheduleWorker(QThread):
    """Worker thread لتوليد جدول الأقساط في الخلفية دون تجميد الواجهة"""
    progress = pyqtSignal(int, int, str)   # current_step, total_steps, label
    finished = pyqtSignal(int, int)        # total_created, subs_count
    error    = pyqtSignal(str)

    def __init__(self, db_url, cat_id, cycles, inst_per_cycle, start_date):
        super().__init__()
        self.db_url = db_url
        self.cat_id = cat_id
        self.cycles = cycles
        self.inst_per_cycle = inst_per_cycle
        self.start_date = start_date

    def run(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        kw = {"check_same_thread": False} if "sqlite" in self.db_url else {}
        engine  = create_engine(self.db_url, connect_args=kw)
        Session = sessionmaker(bind=engine)
        db      = Session()
        try:
            cat = db.get(db_mod.Category, self.cat_id)
            if not cat:
                self.error.emit("الفئة المحددة غير موجودة")
                return

            cat.max_cycles = self.cycles
            cat.max_installments = self.inst_per_cycle
            db.commit()

            subs = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.category == cat.name).all()
            if not subs:
                self.finished.emit(0, 0)
                return

            sub_ids = [sub.id for sub in subs]
            existing = set(
                db.query(db_mod.Payment.subscriber_id, db_mod.Payment.cycle_number, db_mod.Payment.installment_number)
                .filter(db_mod.Payment.subscriber_id.in_(sub_ids))
                .all()
            )

            total_steps = self.cycles * self.inst_per_cycle
            current_step = 0
            total_created = 0
            batch = []

            for c_idx in range(1, self.cycles + 1):
                for i_idx in range(1, self.inst_per_cycle + 1):
                    current_step += 1
                    self.progress.emit(current_step, total_steps, f"دورة {c_idx} - قسط {i_idx}")
                    global_idx = (c_idx - 1) * self.inst_per_cycle + (i_idx - 1)
                    due_date = self.start_date + datetime.timedelta(days=global_idx)
                    due_datetime = datetime.datetime.combine(due_date, datetime.time.min)

                    for sub in subs:
                        if (sub.id, c_idx, i_idx) not in existing:
                            batch.append(db_mod.Payment(
                                subscriber_id=sub.id,
                                amount=cat.amount,
                                due_date=due_datetime,
                                is_paid=False,
                                cycle_number=c_idx,
                                installment_number=i_idx,
                                note=f"دورة {c_idx} - قسط {i_idx}"
                            ))
                            existing.add((sub.id, c_idx, i_idx))
                            total_created += 1

                    if len(batch) >= 2000:
                        db.bulk_save_objects(batch)
                        db.commit()
                        batch = []

            if batch:
                db.bulk_save_objects(batch)
                db.commit()

            self.finished.emit(total_created, len(subs))
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            self.error.emit(str(e))
        finally:
            db.close()
            engine.dispose()

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
        
        self.btn_gen = QPushButton("توليد جدول الأقساط لجميع المشتركين")
        btn_gen.setObjectName("PrimaryBtn")
        btn_gen.setFixedHeight(50)
        btn_gen.clicked.connect(self.generate_cycle_schedule)
        
        layout.addWidget(f1)
        layout.addWidget(btn_save_settings)
        layout.addWidget(self.btn_gen)
        
        info = QLabel("تنبيه: هذا الإجراء سيقوم بإنشاء سجلات دفع مستقبلية لجميع المشتركين في الفئة المختارة بناءً على الإعدادات أعلاه.")
        info.setStyleSheet("color: #94a3b8; font-size: 13px;")
        layout.addWidget(info)
        
        layout.addStretch(); page.setWidget(container); return page
    def refresh_cycles_cat_list(self):
        self.cyc_cat.clear()
        curr_season_id = None
        if hasattr(self, 'combo_header_season'):
            curr_season_id = self.combo_header_season.currentData()
        if not curr_season_id:
            curr_s = db_mod.get_current_season(self.db)
            curr_season_id = curr_s.id if curr_s else None

        q = self.db.query(db_mod.Category)
        if curr_season_id and curr_season_id != -1:
            q = q.filter(db_mod.Category.season_id == curr_season_id)
        for c in q.all():
            self.cyc_cat.addItem(c.name, c.id)
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
            if not cat:
                ModernDialog(self, "خطأ", "الفئة غير موجودة").exec()
                return

            subs_count = self.db.query(func.count(db_mod.Subscriber.id)).filter(db_mod.Subscriber.category == cat.name).scalar() or 0
            if subs_count == 0:
                ModernDialog(self, "تنبيه", "لا يوجد مشتركون في هذه الفئة حالياً").exec()
                return
            
            msg = f"سيتم إنشاء {total_installments} سجل دفع (بمعدل قسط واحد يومياً) لـ {subs_count} مشترك.\nهل أنت متأكد من المتابعة؟"
            if not ModernDialog(self, "تأكيد", msg, is_confirm=True).exec():
                return

            try:
                db_url = str(self.db.get_bind().url)
            except Exception:
                db_url = db_mod.get_local_database_url()

            if hasattr(self, 'btn_gen'):
                self.btn_gen.setEnabled(False)

            self._cycle_loading = LoadingDialog(
                self,
                title="⏳ جاري توليد جدول الأقساط...",
                message=f"جاري تحضير البيانات لـ {subs_count} مشترك — يرجى الانتظار"
            )
            self._cycle_loading.progress_bar.setRange(0, total_installments)
            self._cycle_loading.progress_bar.setValue(0)
            self._cycle_loading.show()

            self._cycle_worker = _CycleScheduleWorker(
                db_url=db_url,
                cat_id=cat_id,
                cycles=cycles,
                inst_per_cycle=inst_per_cycle,
                start_date=start_date
            )
            self._cycle_worker.progress.connect(self._on_cycle_progress)
            self._cycle_worker.finished.connect(self._on_cycle_finished)
            self._cycle_worker.error.connect(self._on_cycle_error)
            self._cycle_worker.start()

        except ValueError:
            ModernDialog(self, "خطأ", "يرجى إدخال أرقام صحيحة للدورات والأقساط").exec()
        except Exception as e:
            ModernDialog(self, "خطأ", str(e)).exec()

    def _on_cycle_progress(self, current: int, total: int, step_name: str):
        if hasattr(self, '_cycle_loading') and self._cycle_loading:
            self._cycle_loading.progress_bar.setValue(current)
            self._cycle_loading.set_message(
                f"جاري معالجة: {step_name} ({current}/{total})",
                title="⏳ جاري توليد جدول الأقساط..."
            )

    def _on_cycle_finished(self, total_created: int, subs_count: int):
        self._cleanup_cycle_worker()
        try:
            self.db.expire_all()
        except Exception:
            pass
        ModernDialog(self, "نجاح", f"تم توليد {total_created} سجل دفع بنجاح لـ {subs_count} مشترك").exec()
        self.load_category_cycle_settings()

    def _on_cycle_error(self, err_msg: str):
        self._cleanup_cycle_worker()
        ModernDialog(self, "خطأ", f"حدث خطأ أثناء توليد الجدول:\n{err_msg}").exec()

    def _cleanup_cycle_worker(self):
        if hasattr(self, '_cycle_loading') and self._cycle_loading:
            self._cycle_loading.close()
            self._cycle_loading = None
        if hasattr(self, 'btn_gen'):
            self.btn_gen.setEnabled(True)
