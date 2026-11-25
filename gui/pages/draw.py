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
from gui.utils import reshape_text, ServerWorker, fit_dialog_to_screen
from gui.dialogs import *

class GrandPrizePeriodDialog(QDialog):
    def __init__(self, parent, periods_count, weeks_per_period):
        super().__init__(parent)
        self.setWindowTitle("تحديد فترة الجائزة الكبرى")
        fit_dialog_to_screen(self, 440, fixed_width=True)
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

def _read_incentive_max_late(db):
    """قراءة الحد الأقصى للأقساط المتأخرة المسموح بها في الجائزة التحفيزية من قاعدة البيانات."""
    try:
        keys = [
            "incentive_allow_late_3",
            "incentive_allow_late_2",
            "incentive_allow_late_1",
            "incentive_max_late_installments",
        ]
        rows = db.query(db_mod.Setting).filter(db_mod.Setting.key.in_(keys)).all()
        s_map = {r.key: str(r.value or "").strip() for r in rows}
        if s_map.get("incentive_allow_late_3") == "1":
            return 3
        if s_map.get("incentive_allow_late_2") == "1":
            return 2
        if s_map.get("incentive_allow_late_1") == "1":
            return 1
        legacy = s_map.get("incentive_max_late_installments", "")
        if legacy.isdigit():
            return int(legacy)
    except Exception:
        pass
    return 0


def _dedupe_cycle_payments(payments_list):
    """
    إزالة أي تكرار لرقم القسط داخل نفس الدورة مع تفضيل السجل المسدد (is_paid=True).
    كل عنصر في القائمة: (sub_id, cycle_num, inst_num, amount, due_date, paid_date, is_paid)
    """
    if not payments_list:
        return []
    by_inst = {}
    fallback_idx = 10000
    for p in payments_list:
        inst_num = p[2]
        if inst_num is None or inst_num <= 0:
            fallback_idx += 1
            key = fallback_idx
        else:
            key = int(inst_num)
        existing = by_inst.get(key)
        if existing is None:
            by_inst[key] = p
        else:
            # تفضيل القسط المسدد على المكرر غير المسدد
            if bool(p[6]) and not bool(existing[6]):
                by_inst[key] = p
            elif bool(p[6]) == bool(existing[6]):
                if p[5] and (not existing[5] or p[5] < existing[5]):
                    by_inst[key] = p
    return [by_inst[k] for k in sorted(by_inst.keys())]


def _natural_sub_sort_key(sub_num):
    """ترتيب أرقام المشتركين طبيعياً (مثل A-1, A-2, A-10 بدلاً من الترتيب النصي)."""
    s = str(sub_num or "").strip()
    if "-" in s:
        parts = s.split("-", 1)
        prefix = parts[0].strip()
        num_str = "".join(ch for ch in parts[1] if ch.isdigit())
        if num_str.isdigit():
            return (prefix, int(num_str), s)
    num_only = "".join(ch for ch in s if ch.isdigit())
    if num_only.isdigit():
        return ("", int(num_only), s)
    return (s, 0, s)


def compute_category_draw_analytics(db, selected_cycles=None, season_id=None):
    """
    حساب إحصائيات وأهلية السحب وتفاصيل تقارير ما قبل القرعة لجميع الفئات بسرعة فائقة (~15ms) وبدقة كاملة:
    - يحدد تلقائياً آخر دورة مكتملة الجدول (أو التي أتمها المشتركون) لكل فئة بدلاً من الدورات التي بدأت للتو بقسط أو قسطين،
      ويتجاهل القيم الشاذة الفردية عند حساب الدورة التلقائية للفئة.
    - عند اختيار دورة محددة يدوياً من القائمة، يقيّم المشتركين بناءً على سدادهم والتزامهم داخل تلك الدورة تحديداً.
    - يجهز لكل فئة قوائم تفصيلية بـ:
      1) أرقام المؤهلين في هذه الدورة
      2) أرقام الذين قد فازوا في الدورات السابقة (مع رقم الدورة التي فازوا فيها)
      3) أرقام الذين خرجوا من القرعة في هذه الدورة (مع سبب الخروج)
    """
    selected_cycles = dict(selected_cycles or {})
    today = datetime.datetime.now()
    today_date = today.date()

    q_cat = db.query(db_mod.Category)
    if season_id and season_id != -1:
        q_cat = q_cat.filter(db_mod.Category.season_id == season_id)
    categories = q_cat.order_by(db_mod.Category.id.asc()).all()

    q_subs_all = db.query(db_mod.Subscriber)
    if season_id and season_id != -1:
        q_subs_all = q_subs_all.filter(db_mod.Subscriber.season_id == season_id)
    all_subs_every_status = q_subs_all.all()
    all_accepted = [s for s in all_subs_every_status if s.status == "accepted"]
    fin_status_map = db_mod.calculate_financial_status_batch(all_accepted, db) if all_accepted else {}

    subs_by_cat = {}
    all_subs_by_cat = {}
    for s in all_subs_every_status:
        all_subs_by_cat.setdefault(s.category, []).append(s)
        if s.status == "accepted":
            subs_by_cat.setdefault(s.category, []).append(s)

    for c_key in all_subs_by_cat:
        all_subs_by_cat[c_key].sort(key=lambda x: _natural_sub_sort_key(x.subscriber_number))
    for c_key in subs_by_cat:
        subs_by_cat[c_key].sort(key=lambda x: _natural_sub_sort_key(x.subscriber_number))

    all_sub_ids = [s.id for s in all_subs_every_status]
    raw_payments = (
        db.query(
            db_mod.Payment.subscriber_id,
            db_mod.Payment.cycle_number,
            db_mod.Payment.installment_number,
            db_mod.Payment.amount,
            db_mod.Payment.due_date,
            db_mod.Payment.paid_date,
            db_mod.Payment.is_paid,
        )
        .filter(db_mod.Payment.subscriber_id.in_(all_sub_ids))
        .all()
        if all_sub_ids
        else []
    )

    # تجميع المدفوعات حسب (المشترك -> الدورة -> قائمة الأقساط المنظفة)
    sub_cycle_payments = {}
    for p in raw_payments:
        sid = p[0]
        c_num = p[1] or 1
        sub_cycle_payments.setdefault(sid, {}).setdefault(c_num, []).append(p)

    for sid, c_map in sub_cycle_payments.items():
        for c_num, plist in list(c_map.items()):
            c_map[c_num] = _dedupe_cycle_payments(plist)

    max_late_allowed = _read_incentive_max_late(db)

    q_win_rows = db.query(
        db_mod.Winner.subscriber_number,
        db_mod.Winner.draw_type,
        db_mod.Winner.cycle_number,
        db_mod.Winner.draw_date,
    )
    if season_id and season_id != -1:
        q_win_rows = q_win_rows.filter(db_mod.Winner.season_id == season_id)
    all_winners_rows = q_win_rows.order_by(db_mod.Winner.draw_date.asc()).all()

    weekly_won_subs = set()
    weekly_winners_info = {}     # sub_num -> list of cycle_number
    incentive_winners_info = {}  # sub_num -> list of cycle_number
    grand_winners_info = {}      # sub_num -> list of cycle_number

    for w_num, w_type, w_cycle, _ in all_winners_rows:
        if not w_num:
            continue
        w_t = str(w_type or "")
        if "الاسبوعية" in w_t or "الأسبوعية" in w_t:
            weekly_won_subs.add(w_num)
            weekly_winners_info.setdefault(w_num, []).append(w_cycle)
        elif "التحفيزية" in w_t or "تحفيزية" in w_t:
            incentive_winners_info.setdefault(w_num, []).append(w_cycle)
        elif "الكبرى" in w_t:
            grand_winners_info.setdefault(w_num, []).append(w_cycle)

    def _format_won_cycles(cycles_list):
        if not cycles_list:
            return "دورة سابقة"
        valid_c = [str(c) for c in cycles_list if c is not None]
        if valid_c:
            return "دورة " + "، ".join(valid_c)
        return "دورة سابقة"

    analytics = {}
    for cat in categories:
        cat_subs = subs_by_cat.get(cat.name, [])
        cat_all_subs = all_subs_by_cat.get(cat.name, [])
        max_inst = max(1, int(cat.max_installments or 1))
        expected_amount = float(cat.amount or 0.0) * max_inst

        total_subs_count = len(cat_subs)
        committed_now_count = 0
        late_now_count = 0
        for s in cat_subs:
            if fin_status_map.get(s.id) in ("late", "suspended"):
                late_now_count += 1
            else:
                committed_now_count += 1

        # تحديد أقصى دورة مولّدة وأفضل دورة مكتملة الأقساط تلقائياً للفئة
        sub_full_due_cycles = []
        sub_latest_due_cycles = []
        sub_last_paid_full_cycles = []
        max_cycle_seen = int(cat.max_cycles or 1)

        for s in cat_subs:
            c_map = sub_cycle_payments.get(s.id, {})
            if not c_map:
                continue
            s_max_c = max(c_map.keys())
            if s_max_c > max_cycle_seen:
                max_cycle_seen = s_max_c

            best_full_due = 0
            best_any_due = 0
            best_full_paid = 0
            for c_num, plist in c_map.items():
                due_le_today = [p for p in plist if p[4] and p[4].date() <= today_date]
                paid_in_c = [p for p in plist if p[6]]
                if due_le_today:
                    if c_num > best_any_due:
                        best_any_due = c_num
                    if len(due_le_today) >= max_inst and c_num > best_full_due:
                        best_full_due = c_num
                if len(paid_in_c) >= max_inst and c_num > best_full_paid:
                    best_full_paid = c_num

            if best_full_due > 0:
                sub_full_due_cycles.append(best_full_due)
            if best_any_due > 0:
                sub_latest_due_cycles.append(best_any_due)
            if best_full_paid > 0:
                sub_last_paid_full_cycles.append(best_full_paid)

        if sub_full_due_cycles:
            freq = {}
            for c_val in sub_full_due_cycles:
                freq[c_val] = freq.get(c_val, 0) + 1
            auto_completed_cycle = max(freq.keys(), key=lambda k: (freq[k], k))
        elif sub_latest_due_cycles:
            freq = {}
            for c_val in sub_latest_due_cycles:
                freq[c_val] = freq.get(c_val, 0) + 1
            auto_completed_cycle = max(freq.keys(), key=lambda k: (freq[k], k))
        else:
            auto_completed_cycle = 1

        if sub_latest_due_cycles:
            freq_cur = {}
            for c_val in sub_latest_due_cycles:
                freq_cur[c_val] = freq_cur.get(c_val, 0) + 1
            current_running_cycle = max(freq_cur.keys(), key=lambda k: (freq_cur[k], k))
        else:
            current_running_cycle = auto_completed_cycle

        if sub_last_paid_full_cycles:
            freq_paid = {}
            for c_val in sub_last_paid_full_cycles:
                freq_paid[c_val] = freq_paid.get(c_val, 0) + 1
            last_group_paid_cycle = max(freq_paid.keys(), key=lambda k: (freq_paid[k], k))
        else:
            last_group_paid_cycle = auto_completed_cycle

        sel_c = selected_cycles.get(cat.name, "auto")
        is_manual_cycle = (sel_c != "auto" and isinstance(sel_c, int))
        target_cycle = int(sel_c) if is_manual_cycle else auto_completed_cycle

        completed_total = 0
        weekly_eligible = 0
        incentive_count = 0
        weekly_qualified_ids = []
        incentive_qualified_ids = []

        weekly_qualified_entries = []
        weekly_previous_winners_entries = []
        weekly_excluded_entries = []

        incentive_qualified_entries = []
        incentive_previous_winners_entries = []
        incentive_excluded_entries = []

        running_due_inst_count = 0
        for s in cat_subs:
            r_plist = sub_cycle_payments.get(s.id, {}).get(current_running_cycle, [])
            if r_plist:
                running_due_inst_count = max(
                    running_due_inst_count,
                    sum(1 for p in r_plist if p[4] and p[4].date() <= today_date),
                )

        for s in cat_all_subs:
            s_num = s.subscriber_number or f"#{s.id}"
            s_name = s.name or "-"
            c_map = sub_cycle_payments.get(s.id, {})
            s_payments = c_map.get(target_cycle, [])
            if not s_payments and not is_manual_cycle and c_map:
                s_payments = c_map.get(max(c_map.keys(), default=1), [])

            paid_rows = [p for p in s_payments if p[6]]
            paid_count = len(paid_rows)
            total_paid = sum(float(p[3] or 0.0) for p in paid_rows)

            # إذا كان قد فاز سابقاً في القرعة الأسبوعية، يُسجّل في قائمة الفائزين بالدورات السابقة
            if s_num in weekly_won_subs:
                weekly_previous_winners_entries.append({
                    "id": s.id,
                    "number": s_num,
                    "name": s_name,
                    "won_cycle": _format_won_cycles(weekly_winners_info.get(s_num, [])),
                })

            if s_num in incentive_winners_info:
                incentive_previous_winners_entries.append({
                    "id": s.id,
                    "number": s_num,
                    "name": s_name,
                    "won_cycle": _format_won_cycles(incentive_winners_info.get(s_num, [])),
                })

            # التحقق من حالة المشترك الإدارية والمالية
            if s.status != "accepted":
                reason_admin = "مستبعد إدارياً" if s.status == "excluded" else "طلب اشتراك معلق"
                if s_num not in weekly_won_subs:
                    weekly_excluded_entries.append({
                        "id": s.id,
                        "number": s_num,
                        "name": s_name,
                        "reason": reason_admin,
                    })
                incentive_excluded_entries.append({
                    "id": s.id,
                    "number": s_num,
                    "name": s_name,
                    "reason": reason_admin,
                })
                continue

            fin_st = fin_status_map.get(s.id, "committed")
            if not is_manual_cycle and fin_st in ("late", "suspended"):
                st_label = "موقوف" if fin_st == "suspended" else "متأخر"
                reason_fin = f"{st_label} (سدد {paid_count}/{max_inst} في الدورة {target_cycle})"
                if s_num not in weekly_won_subs:
                    weekly_excluded_entries.append({
                        "id": s.id,
                        "number": s_num,
                        "name": s_name,
                        "reason": reason_fin,
                    })
                incentive_excluded_entries.append({
                    "id": s.id,
                    "number": s_num,
                    "name": s_name,
                    "reason": reason_fin,
                })
                continue

            if not s_payments:
                reason_no_p = f"لا توجد أقساط مسجلة في الدورة {target_cycle}"
                if s_num not in weekly_won_subs:
                    weekly_excluded_entries.append({
                        "id": s.id,
                        "number": s_num,
                        "name": s_name,
                        "reason": reason_no_p,
                    })
                incentive_excluded_entries.append({
                    "id": s.id,
                    "number": s_num,
                    "name": s_name,
                    "reason": reason_no_p,
                })
                continue

            is_finished = (total_paid >= expected_amount - 0.01) and (paid_count >= max_inst)
            last_due_dt = s_payments[-1][4] if s_payments else today
            is_date_reached = (today >= last_due_dt) if (last_due_dt and not is_manual_cycle) else True

            has_paid_something = paid_count > 0
            late_count = 0
            for p in s_payments:
                p_due = p[4].date() if p[4] else None
                p_paid = p[5].date() if p[5] else None
                is_p = bool(p[6])
                if p_due is None:
                    continue
                if p_due <= today_date or is_manual_cycle:
                    if not is_p:
                        late_count += 1
                    else:
                        if p_paid and p_paid > p_due:
                            late_count += 1
                else:
                    if is_p and p_paid and p_paid > p_due:
                        late_count += 1

            is_inc = has_paid_something and (late_count <= max_late_allowed)

            if is_finished and is_date_reached:
                completed_total += 1
                if s_num not in weekly_won_subs:
                    weekly_eligible += 1
                    weekly_qualified_ids.append(s.id)
                    weekly_qualified_entries.append({
                        "id": s.id,
                        "number": s_num,
                        "name": s_name,
                        "paid_count": paid_count,
                        "max_inst": max_inst,
                    })
            else:
                if s_num not in weekly_won_subs:
                    weekly_excluded_entries.append({
                        "id": s.id,
                        "number": s_num,
                        "name": s_name,
                        "reason": f"لم يُتم أقساط الدورة {target_cycle} (سدد {paid_count}/{max_inst})",
                    })

            if is_inc:
                incentive_count += 1
                incentive_qualified_ids.append(s.id)
                incentive_qualified_entries.append({
                    "id": s.id,
                    "number": s_num,
                    "name": s_name,
                    "paid_count": paid_count,
                    "max_inst": max_inst,
                })
            else:
                inc_reason = (
                    f"لم يسدد أي قسط في الدورة {target_cycle}"
                    if not has_paid_something
                    else f"تأخر في {late_count} أقساط بالدورة {target_cycle}"
                )
                incentive_excluded_entries.append({
                    "id": s.id,
                    "number": s_num,
                    "name": s_name,
                    "reason": inc_reason,
                })

        analytics[cat.name] = {
            "category_name": cat.name,
            "target_cycle": target_cycle,
            "auto_cycle": auto_completed_cycle,
            "current_running_cycle": current_running_cycle,
            "running_due_inst_count": running_due_inst_count,
            "max_installments": max_inst,
            "last_group_paid_cycle": last_group_paid_cycle,
            "total_cycles": max(max_cycle_seen, auto_completed_cycle, current_running_cycle),
            "total_subs": total_subs_count,
            "committed_now": committed_now_count,
            "late_now": late_now_count,
            "completed_total": completed_total,
            "weekly_eligible": weekly_eligible,
            "incentive_count": incentive_count,
            "weekly_qualified_ids": weekly_qualified_ids,
            "incentive_qualified_ids": incentive_qualified_ids,
            "weekly_qualified_entries": weekly_qualified_entries,
            "weekly_previous_winners_entries": weekly_previous_winners_entries,
            "weekly_excluded_entries": weekly_excluded_entries,
            "incentive_qualified_entries": incentive_qualified_entries,
            "incentive_previous_winners_entries": incentive_previous_winners_entries,
            "incentive_excluded_entries": incentive_excluded_entries,
            "is_manual_cycle": is_manual_cycle,
        }

    return analytics


class DrawStatsLoader(QThread):
    stats_loaded = pyqtSignal(dict)

    def __init__(self, selected_cycles, season_id=None):
        super().__init__()
        self.selected_cycles = dict(selected_cycles or {})
        self.season_id = season_id

    def run(self):
        bg_db = db_mod.SessionLocal()
        try:
            analytics = compute_category_draw_analytics(
                bg_db,
                selected_cycles=self.selected_cycles,
                season_id=self.season_id,
            )
            self.stats_loaded.emit(analytics)
        except Exception as e:
            print("Error in DrawStatsLoader:", e)
        finally:
            bg_db.close()


class DrawQualificationWorker(QThread):
    finished = pyqtSignal(dict, list, int)  # (qualified_by_category, qualified_ids, disqualified_count)
    error = pyqtSignal(str)

    def __init__(self, draw_name, category_selected_cycles, selected_period=1, periods_count=1, weeks_per_period=12, season_id=None):
        super().__init__()
        self.draw_name = draw_name
        self.category_selected_cycles = dict(category_selected_cycles or {})
        self.selected_period = selected_period
        self.periods_count = periods_count
        self.weeks_per_period = weeks_per_period
        self.season_id = season_id

    def run(self):
        bg_db = db_mod.SessionLocal()
        try:
            analytics = compute_category_draw_analytics(
                bg_db,
                selected_cycles=self.category_selected_cycles,
                season_id=self.season_id,
            )
            self.analytics = analytics

            disqualified_count = sum(info.get("late_now", 0) for info in analytics.values())
            qualified_by_category = {}
            qualified_ids = []

            if "الاسبوعية" in self.draw_name or "الأسبوعية" in self.draw_name:
                for cat_name, info in analytics.items():
                    q_ids = info.get("weekly_qualified_ids", [])
                    qualified_by_category[cat_name] = list(q_ids)
                    qualified_ids.extend(q_ids)
                self.finished.emit(qualified_by_category, qualified_ids, disqualified_count)
                return

            if self.draw_name == "الجائزة التحفيزية":
                for cat_name, info in analytics.items():
                    q_ids = info.get("incentive_qualified_ids", [])
                    qualified_by_category[cat_name] = list(q_ids)
                    qualified_ids.extend(q_ids)
                self.finished.emit(qualified_by_category, qualified_ids, disqualified_count)
                return

            # الجائزة الكبرى:
            # - يدخل الملتزمون بالتسديد في الوقت المحدد خلال الفترة المحددة (يُسمح بالتأخير حتى 3 أيام فقط)
            # - من يتأخر أكثر من 3 أيام يُستبعد طوال هذه الفترة فقط، ويبدأ فترة جديدة نظيفة بعد القرعة
            # - كل من فاز سابقاً بالجائزة الكبرى لا يدخل السحب مرة أخرى
            today = datetime.datetime.now()
            today_date = today.date()

            q_cats_g = bg_db.query(db_mod.Category)
            q_subs_g = bg_db.query(db_mod.Subscriber)
            q_win_g = bg_db.query(
                db_mod.Winner.subscriber_number,
                db_mod.Winner.draw_type,
                db_mod.Winner.cycle_number,
            ).filter(db_mod.Winner.draw_type.contains("الجائزة الكبرى"))

            if self.season_id and self.season_id != -1:
                q_cats_g = q_cats_g.filter(db_mod.Category.season_id == self.season_id)
                q_subs_g = q_subs_g.filter(db_mod.Subscriber.season_id == self.season_id)
                q_win_g = q_win_g.filter(db_mod.Winner.season_id == self.season_id)

            categories_g = q_cats_g.order_by(db_mod.Category.id.asc()).all()
            all_subs_g = q_subs_g.all()
            if not all_subs_g:
                self.finished.emit({}, [], 0)
                return

            # جميع الفائزين السابقين في الجائزة الكبرى (لا يدخلون السحب مرة أخرى نهائياً)
            grand_won_numbers = set()
            grand_won_info = {}
            for w_num, w_type, w_cycle in q_win_g.all():
                if not w_num:
                    continue
                grand_won_numbers.add(w_num)
                lbl = str(w_type or "الجائزة الكبرى")
                if w_cycle:
                    lbl = f"{lbl} (د{w_cycle})"
                grand_won_info.setdefault(w_num, []).append(lbl)

            # قراءة تواريخ بداية ونهاية الجائزة الكبرى من الإعدادات
            s_start_row = bg_db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_start_date").first()
            s_end_row = bg_db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_end_date").first()
            cfg_start_date = None
            cfg_end_date = None
            if s_start_row and s_start_row.value:
                try:
                    cfg_start_date = datetime.date.fromisoformat(s_start_row.value.strip())
                except Exception:
                    cfg_start_date = None
            if s_end_row and s_end_row.value:
                try:
                    cfg_end_date = datetime.date.fromisoformat(s_end_row.value.strip())
                except Exception:
                    cfg_end_date = None

            all_sub_ids_g = [s.id for s in all_subs_g]
            raw_p_g = (
                bg_db.query(
                    db_mod.Payment.subscriber_id,
                    db_mod.Payment.due_date,
                    db_mod.Payment.paid_date,
                    db_mod.Payment.is_paid,
                )
                .filter(db_mod.Payment.subscriber_id.in_(all_sub_ids_g))
                .all()
                if all_sub_ids_g
                else []
            )
            payments_by_sub_g = {}
            for row_p in raw_p_g:
                payments_by_sub_g.setdefault(row_p[0], []).append(row_p)

            subs_by_cat_g = {}
            for s in all_subs_g:
                subs_by_cat_g.setdefault(s.category, []).append(s)
            for ck in subs_by_cat_g:
                subs_by_cat_g[ck].sort(key=lambda x: _natural_sub_sort_key(x.subscriber_number))

            period_days = max(1, int(self.weeks_per_period or 12) * 7)
            sel_period = max(1, int(self.selected_period or 1))
            max_grace_days = 3
            grand_disqualified_total = 0

            for cat in categories_g:
                cat_subs = subs_by_cat_g.get(cat.name, [])

                # حساب النطاق الزمني للفترة الحالية لهذه الفئة
                base_start = cfg_start_date
                if base_start is None and cat.start_date:
                    base_start = cat.start_date.date() if isinstance(cat.start_date, datetime.datetime) else cat.start_date
                if base_start is None:
                    # أقدم تاريخ استحقاق في الفئة
                    due_dates = [
                        p[1].date()
                        for s in cat_subs
                        for p in payments_by_sub_g.get(s.id, [])
                        if p[1] is not None
                    ]
                    base_start = min(due_dates) if due_dates else today_date

                if self.periods_count > 1:
                    period_start = base_start + datetime.timedelta(days=(sel_period - 1) * period_days)
                    period_end = base_start + datetime.timedelta(days=sel_period * period_days - 1)
                else:
                    period_start = base_start
                    period_end = cfg_end_date if (cfg_end_date and cfg_end_date >= period_start) else today_date

                eval_end = min(period_end, today_date)

                g_qual_ids = []
                g_qual_entries = []
                g_prev_entries = []
                g_excl_entries = []

                for s in cat_subs:
                    s_num = s.subscriber_number or f"#{s.id}"
                    s_name = s.name or "-"

                    # 1. الفائزون سابقاً في الجائزة الكبرى لا يدخلون السحب مرة أخرى
                    if s_num in grand_won_numbers:
                        g_prev_entries.append({
                            "id": s.id,
                            "number": s_num,
                            "name": s_name,
                            "won_cycle": " ، ".join(grand_won_info.get(s_num, ["فائز سابق"])),
                        })
                        continue

                    # 2. التحقق من حالة القبول الإداري
                    if s.status != "accepted":
                        reason_adm = "مستبعد إدارياً" if s.status == "excluded" else "طلب اشتراك معلق"
                        g_excl_entries.append({
                            "id": s.id,
                            "number": s_num,
                            "name": s_name,
                            "reason": reason_adm,
                        })
                        grand_disqualified_total += 1
                        continue

                    # 3. فحص أقساط المشترك داخل الفترة الزمنية المحددة [period_start .. eval_end]
                    s_plist = payments_by_sub_g.get(s.id, [])
                    period_rows = [
                        p for p in s_plist
                        if p[1] is not None and period_start <= p[1].date() <= eval_end
                    ]
                    if not period_rows:
                        g_excl_entries.append({
                            "id": s.id,
                            "number": s_num,
                            "name": s_name,
                            "reason": f"لا توجد أقساط مستحقة في الفترة ({period_start} إلى {eval_end})",
                        })
                        grand_disqualified_total += 1
                        continue

                    unpaid_count = 0
                    late_paid_count = 0
                    for p in period_rows:
                        p_due = p[1].date()
                        p_paid = p[2].date() if p[2] else None
                        is_p = bool(p[3])
                        if not is_p:
                            unpaid_count += 1
                        elif p_paid and p_paid > p_due:
                            late_paid_count += 1

                    # شروط التأهل للجائزة الكبرى:
                    # 1) سداد جميع أقساط الفترة (لو بقي قسط واحد غير مسدد لا يدخل السحب)
                    # 2) عدد الأقساط التي سددها متأخراً عن موعدها لا يتجاوز 3 أقساط كحد أقصى
                    if unpaid_count == 0 and late_paid_count <= 3:
                        g_qual_ids.append(s.id)
                        g_qual_entries.append({
                            "id": s.id,
                            "number": s_num,
                            "name": s_name,
                        })
                    else:
                        if unpaid_count > 0:
                            r_txt = f"عليه ({unpaid_count}) قسط غير مسدد في الفترة {sel_period}"
                        else:
                            r_txt = f"سدد ({late_paid_count}) أقساط متأخراً عن موعدها (الحد الأقصى 3 أقساط) في الفترة {sel_period}"
                        g_excl_entries.append({
                            "id": s.id,
                            "number": s_num,
                            "name": s_name,
                            "reason": r_txt,
                        })
                        grand_disqualified_total += 1

                qualified_by_category[cat.name] = list(g_qual_ids)
                qualified_ids.extend(g_qual_ids)

                cat_analytics = analytics.setdefault(cat.name, {"cat_id": cat.id, "target_cycle": sel_period})
                cat_analytics["grand_qualified_ids"] = g_qual_ids
                cat_analytics["grand_qualified_entries"] = g_qual_entries
                cat_analytics["grand_previous_winners_entries"] = g_prev_entries
                cat_analytics["grand_excluded_entries"] = g_excl_entries
                cat_analytics["grand_period_range"] = f"{period_start} إلى {period_end}"

            self.finished.emit(qualified_by_category, qualified_ids, grand_disqualified_total)
        except Exception as e:
            self.error.emit(str(e))
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
            self.load_recent_winners()
        elif current_idx == 2:
            self.load_draw_excluded()

    def _on_draw_tab_changed(self, idx):
        if idx == 1:
            self.load_recent_winners()
        elif idx == 2:
            self.load_draw_excluded()
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
            ("الجائزة الكبرى", "سحب الملتزمين بسداد كامل أقساط الفترة (سماح حتى 3 أقساط مسددة متأخراً فقط، ولا يتكرر الفوز).", "#ef4444")
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
            "المشترك", "رقم الحساب", "الفئة", "الهاتف", "الدورة", "نوع الجائزة", "تاريخ السحب", "الاستلام"
        ])
        self.table_recent_winners.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_recent_winners.horizontalHeader().setMinimumSectionSize(45)
        self.table_recent_winners.setWordWrap(True)
        self.table_recent_winners.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table_recent_winners.setStyleSheet(
            "QTableWidget { font-size: 11px; } "
            "QHeaderView::section { font-size: 11px; padding: 4px 3px; }"
        )
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
        self.combo_draw_ex_cat_filter.currentIndexChanged.connect(self._on_draw_ex_cat_changed)
        ex_filter_layout.addWidget(self.combo_draw_ex_cat_filter)

        ex_filter_layout.addWidget(QLabel("الدورة:"))
        self.combo_draw_ex_cycle_filter = QComboBox()
        self.combo_draw_ex_cycle_filter.addItem("كل الدورات", None)
        self.combo_draw_ex_cycle_filter.currentIndexChanged.connect(self.load_draw_excluded)
        ex_filter_layout.addWidget(self.combo_draw_ex_cycle_filter)

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
            "المشترك", "رقم الحساب", "الفئة", "الهاتف", "سبب الاستبعاد", "الانضباط", "إجراء"
        ])
        self.table_draw_excluded.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_draw_excluded.horizontalHeader().setMinimumSectionSize(45)
        self.table_draw_excluded.setWordWrap(True)
        self.table_draw_excluded.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table_draw_excluded.setStyleSheet(
            "QTableWidget { font-size: 11px; } "
            "QHeaderView::section { font-size: 11px; padding: 4px 3px; }"
        )
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

        # --- Wheel Central Golden Hub Settings (إعدادات القرص المركزي الذهبي لعجلة القرعة) ---
        hub_frame = QFrame(); hub_frame.setObjectName("StatCard")
        hub_lay = QVBoxLayout(hub_frame); hub_lay.setContentsMargins(20, 20, 20, 20); hub_lay.setSpacing(15)

        hub_title_color = "color: #eab308;" if is_dark else "color: #a16207;"
        hub_title = QLabel("🎡  إعدادات القرص الذهبي المركزي لعجلة القرعة (الشعار والنصوص)")
        hub_title.setObjectName("SectionTitle")
        hub_title.setStyleSheet(f"font-size: 16px; font-weight: bold; {hub_title_color}")
        hub_lay.addWidget(hub_title)

        hub_desc = QLabel(
            "تحكم بمحتوى القرص الذهبي الموجود في منتصف عجلة القرعة: يمكنك عرض الشعار الذهبي النصي الافتراضي، "
            "أو وضع شعار الشركة مع نص أسفله، أو جعل شعار الشركة يملأ القرص الذهبي بالكامل."
        )
        hub_desc.setWordWrap(True)
        hub_desc.setStyleSheet(f"font-size: 12px; {lbl_muted}")
        hub_lay.addWidget(hub_desc)

        hub_content_row = QHBoxLayout()
        hub_content_row.setSpacing(20)

        # Left/Right: Form controls
        hub_form = QFormLayout()
        hub_form.setSpacing(12)

        self.combo_wheel_hub_mode = QComboBox()
        self.combo_wheel_hub_mode.setFixedHeight(38)
        self.combo_wheel_hub_mode.addItem("✨ شعار نصي ذهبي (الرمز M + العنوان + النص الفرعي)", "text")
        self.combo_wheel_hub_mode.addItem("🏢 شعار الشركة (صورة الشعار في الأعلى + نص أسفله)", "logo_with_text")
        self.combo_wheel_hub_mode.addItem("🌕 شعار الشركة ملء القرص الذهبي بالكامل", "logo_full")
        self.combo_wheel_hub_mode.currentIndexChanged.connect(self._on_wheel_hub_mode_changed)

        self.ent_wheel_hub_symbol = QLineEdit("M")
        self.ent_wheel_hub_symbol.setPlaceholderText("مثال: M")
        self.ent_wheel_hub_symbol.setMaxLength(6)

        self.ent_wheel_hub_title = QLineEdit("MILLION")
        self.ent_wheel_hub_title.setPlaceholderText("مثال: MILLION")

        self.ent_wheel_hub_subtitle = QLineEdit("هكبة المليون الأسبوعية")
        self.ent_wheel_hub_subtitle.setPlaceholderText("مثال: هكبة المليون الأسبوعية")

        hub_form.addRow("نمط عرض القرص المركزي:", self.combo_wheel_hub_mode)
        hub_form.addRow("الرمز الذهبي العلوي:", self.ent_wheel_hub_symbol)
        hub_form.addRow("العنوان الذهبي الرئيسي:", self.ent_wheel_hub_title)
        hub_form.addRow("النص الفرعي أسفل القرص:", self.ent_wheel_hub_subtitle)

        hub_content_row.addLayout(hub_form, 2)

        # Logo preview & picker buttons
        logo_side_lay = QVBoxLayout()
        logo_side_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_side_lay.setSpacing(8)

        self.lbl_wheel_hub_logo_preview = QLabel("الشعار النصي\nالافتراضي (M)")
        self.lbl_wheel_hub_logo_preview.setFixedSize(130, 130)
        self.lbl_wheel_hub_logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_wheel_hub_logo_preview.setStyleSheet(
            "border: 3px solid #eab308; border-radius: 65px; background: #1e293b; color: #fde047; font-size: 12px; font-weight: bold;"
        )
        logo_side_lay.addWidget(self.lbl_wheel_hub_logo_preview, 0, Qt.AlignmentFlag.AlignCenter)

        btn_pick_hub_logo = QPushButton("📁 اختيار صورة شعار للقرص...")
        btn_pick_hub_logo.setObjectName("PrimaryBtn")
        btn_pick_hub_logo.clicked.connect(self.select_wheel_hub_logo)
        logo_side_lay.addWidget(btn_pick_hub_logo)

        btn_use_comp_logo = QPushButton("🏢 استخدام شعار الشركة العام")
        btn_use_comp_logo.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        btn_use_comp_logo.clicked.connect(self.use_company_logo_for_wheel_hub)
        logo_side_lay.addWidget(btn_use_comp_logo)

        btn_clear_hub_logo = QPushButton("🔄 استعادة الشعار الذهبي الافتراضي")
        btn_clear_hub_logo.setStyleSheet("background-color: #475569; color: white; padding: 5px 10px; border-radius: 6px;")
        btn_clear_hub_logo.clicked.connect(self.reset_wheel_hub_defaults)
        logo_side_lay.addWidget(btn_clear_hub_logo)

        hub_content_row.addLayout(logo_side_lay, 1)
        hub_lay.addLayout(hub_content_row)

        hub_actions_row = QHBoxLayout()
        hub_actions_row.setSpacing(12)

        btn_save_hub = QPushButton("💾 حفظ إعدادات القرص المركزي")
        btn_save_hub.setObjectName("PrimaryBtn")
        btn_save_hub.setFixedHeight(42)
        btn_save_hub.clicked.connect(self.save_wheel_hub_settings)

        btn_preview_wheel = QPushButton("🎡 معاينة وتجربة العجلة الآن")
        btn_preview_wheel.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ca8a04, stop:1 #eab308); "
            "color: #052e16; font-weight: 900; font-size: 14px; border-radius: 8px; padding: 0 20px;"
        )
        btn_preview_wheel.setFixedHeight(42)
        btn_preview_wheel.clicked.connect(self.preview_luxury_wheel)

        hub_actions_row.addWidget(btn_save_hub, 2)
        hub_actions_row.addWidget(btn_preview_wheel, 1)
        hub_lay.addLayout(hub_actions_row)

        lay3.addWidget(hub_frame)
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

            # Load Wheel Central Golden Hub Settings
            hub_keys = ["wheel_hub_mode", "wheel_hub_logo_path", "wheel_hub_symbol", "wheel_hub_title", "wheel_hub_subtitle", "company_logo_path"]
            hub_rows = self.db.query(db_mod.Setting).filter(db_mod.Setting.key.in_(hub_keys)).all()
            hub_map = {r.key: (r.value or "") for r in hub_rows}

            mode_val = hub_map.get("wheel_hub_mode", "text") or "text"
            idx_mode = self.combo_wheel_hub_mode.findData(mode_val)
            self.combo_wheel_hub_mode.setCurrentIndex(idx_mode if idx_mode >= 0 else 0)

            self.ent_wheel_hub_symbol.setText(hub_map.get("wheel_hub_symbol") or "M")
            self.ent_wheel_hub_title.setText(hub_map["wheel_hub_title"] if "wheel_hub_title" in hub_map else "MILLION")
            self.ent_wheel_hub_subtitle.setText(hub_map["wheel_hub_subtitle"] if "wheel_hub_subtitle" in hub_map else "هكبة المليون الأسبوعية")

            raw_logo = hub_map.get("wheel_hub_logo_path", "").strip()
            self._wheel_hub_logo_setting_val = raw_logo
            effective_logo = hub_map.get("company_logo_path", "").strip() if raw_logo == "__company_logo__" else raw_logo
            self._update_wheel_hub_logo_preview(effective_logo)
            self._on_wheel_hub_mode_changed()
        except Exception as e:
            print(f"Error loading draw settings: {e}")

    def _on_wheel_hub_mode_changed(self):
        if not hasattr(self, "combo_wheel_hub_mode"):
            return
        mode = self.combo_wheel_hub_mode.currentData()
        is_text_mode = (mode == "text")
        is_logo_with_text = (mode == "logo_with_text")
        self.ent_wheel_hub_symbol.setEnabled(is_text_mode)
        self.ent_wheel_hub_title.setEnabled(is_text_mode)
        self.ent_wheel_hub_subtitle.setEnabled(is_text_mode or is_logo_with_text)

    def _update_wheel_hub_logo_preview(self, logo_path: str):
        if not hasattr(self, "lbl_wheel_hub_logo_preview"):
            return
        if logo_path and os.path.exists(logo_path):
            pm = QPixmap(logo_path)
            if not pm.isNull():
                size = 124
                rounded = QPixmap(size, size)
                rounded.fill(Qt.GlobalColor.transparent)
                p = QPainter(rounded)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                path = QPainterPath()
                path.addEllipse(0, 0, size, size)
                p.setClipPath(path)
                scaled = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
                p.end()
                self.lbl_wheel_hub_logo_preview.setPixmap(rounded)
                return
        self.lbl_wheel_hub_logo_preview.setPixmap(QPixmap())
        sym = self.ent_wheel_hub_symbol.text().strip() or "M"
        self.lbl_wheel_hub_logo_preview.setText(f"الشعار النصي\n({sym})")

    def select_wheel_hub_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "اختر صورة شعار القرص المركزي للعجلة", "", "ملفات الصور (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not file_path:
            return
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        uploads_dir = os.path.join(base_dir, "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        ext = os.path.splitext(file_path)[1] or ".png"
        dest = os.path.join(uploads_dir, f"wheel_hub_logo{ext}")
        try:
            shutil.copy(file_path, dest)
            self._wheel_hub_logo_setting_val = dest
            self._update_wheel_hub_logo_preview(dest)
            # إذا كان النمط نصياً، نحوله تلقائياً إلى شعار الشركة مع النص ليرى المستخدم الشعار مباشرة
            if self.combo_wheel_hub_mode.currentData() == "text":
                idx = self.combo_wheel_hub_mode.findData("logo_with_text")
                if idx >= 0:
                    self.combo_wheel_hub_mode.setCurrentIndex(idx)
        except Exception as e:
            ModernDialog(self, "خطأ", f"تعذر نسخ ملف الشعار: {e}").exec()

    def use_company_logo_for_wheel_hub(self):
        comp_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "company_logo_path").first()
        comp_path = (comp_setting.value or "").strip() if comp_setting else ""
        if not comp_path or not os.path.exists(comp_path):
            ModernDialog(
                self, "تنبيه",
                "لم يتم العثور على شعار عام مسجل للشركة في (إعدادات الشركة).\nيمكنك اختيار صورة الشعار مباشرة من زر 'اختيار صورة شعار للقرص'."
            ).exec()
            return
        self._wheel_hub_logo_setting_val = "__company_logo__"
        self._update_wheel_hub_logo_preview(comp_path)
        if self.combo_wheel_hub_mode.currentData() == "text":
            idx = self.combo_wheel_hub_mode.findData("logo_with_text")
            if idx >= 0:
                self.combo_wheel_hub_mode.setCurrentIndex(idx)
        ModernDialog(self, "تم التحديد", "تم ربط القرص المركزي بشعار الشركة العام بنجاح.\nاضغط 'حفظ إعدادات القرص المركزي' لاعتماد التغيير.").exec()

    def reset_wheel_hub_defaults(self):
        self._wheel_hub_logo_setting_val = ""
        idx = self.combo_wheel_hub_mode.findData("text")
        if idx >= 0:
            self.combo_wheel_hub_mode.setCurrentIndex(idx)
        self.ent_wheel_hub_symbol.setText("M")
        self.ent_wheel_hub_title.setText("MILLION")
        self.ent_wheel_hub_subtitle.setText("هكبة المليون الأسبوعية")
        self._update_wheel_hub_logo_preview("")

    def _get_current_ui_hub_config(self) -> dict:
        raw_logo = getattr(self, "_wheel_hub_logo_setting_val", "") or ""
        if raw_logo == "__company_logo__":
            comp_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "company_logo_path").first()
            effective_logo = (comp_setting.value or "").strip() if comp_setting else ""
        else:
            effective_logo = raw_logo
        return {
            "mode": self.combo_wheel_hub_mode.currentData() or "text",
            "logo_path": effective_logo,
            "symbol": self.ent_wheel_hub_symbol.text().strip() or "M",
            "title": self.ent_wheel_hub_title.text().strip(),
            "subtitle": self.ent_wheel_hub_subtitle.text().strip(),
        }

    def save_wheel_hub_settings(self):
        try:
            mode_val = self.combo_wheel_hub_mode.currentData() or "text"
            raw_logo = getattr(self, "_wheel_hub_logo_setting_val", "") or ""
            if mode_val in ("logo_with_text", "logo_full") and not raw_logo:
                # محاولة استخدام شعار الشركة تلقائياً إذا كان موجوداً
                comp_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "company_logo_path").first()
                if comp_setting and comp_setting.value and os.path.exists(comp_setting.value):
                    raw_logo = "__company_logo__"
                    self._wheel_hub_logo_setting_val = raw_logo
                else:
                    ModernDialog(self, "تنبيه", "يرجى اختيار صورة الشعار أولاً أو اختيار نمط 'شعار نصي ذهبي'.").exec()
                    return

            hub_settings = {
                "wheel_hub_mode": mode_val,
                "wheel_hub_logo_path": raw_logo,
                "wheel_hub_symbol": self.ent_wheel_hub_symbol.text().strip() or "M",
                "wheel_hub_title": self.ent_wheel_hub_title.text().strip(),
                "wheel_hub_subtitle": self.ent_wheel_hub_subtitle.text().strip(),
            }
            for key, val in hub_settings.items():
                setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
                if setting:
                    setting.value = val
                else:
                    self.db.add(db_mod.Setting(key=key, value=val))
            self.db.commit()
            ModernDialog(self, "نجاح", "تم حفظ إعدادات القرص المركزي الذهبي لعجلة القرعة بنجاح ✅").exec()
        except Exception as e:
            self.db.rollback()
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء حفظ إعدادات القرص المركزي: {e}").exec()

    def preview_luxury_wheel(self):
        cfg = self._get_current_ui_hub_config()
        dlg = WheelPreviewDialog(self, db=self.db, hub_config=cfg)
        dlg.exec()

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
            self.refresh_draw_stats()
            ModernDialog(self, "نجاح", "تم حفظ إعدادات الجائزة التحفيزية بنجاح وتحديث إحصائيات الفئات.").exec()
        except Exception as e:
            self.db.rollback()
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء الحفظ: {e}").exec()

    def _get_incentive_max_late(self):
        """إرجاع الحد الأقصى للأقساط المتأخرة المسموح بها للجائزة التحفيزية حسب الإعدادات."""
        return _read_incentive_max_late(self.db)

    def _get_category_stats(self, cat, target_cycle=None):
        sel_map = {cat.name: target_cycle if target_cycle is not None else "auto"}
        analytics = compute_category_draw_analytics(self.db, selected_cycles=sel_map)
        info = analytics.get(cat.name, {})
        return info.get("weekly_eligible", 0), info.get("incentive_count", 0)

    def _get_active_season_id_for_draw(self):
        try:
            if hasattr(self, 'combo_header_season'):
                sid = self.combo_header_season.currentData()
                if sid:
                    return sid
            curr_s = db_mod.get_current_season(self.db)
            return curr_s.id if curr_s else None
        except Exception:
            return None

    def refresh_draw_stats(self):
        """إعادة رسم إحصائيات السحب بشكل غير متزامن وسريع جداً (~15ms) من قاعدة البيانات المحلية."""
        if not hasattr(self, "category_selected_cycles"):
            self.category_selected_cycles = {}

        for i in reversed(range(self.draw_stats_layout.count())):
            item = self.draw_stats_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
            elif item and item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().setParent(None)

        loading_lbl = QLabel("⏳ جاري تحميل إحصائيات الفئات...")
        loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_lbl.setStyleSheet("color: #94a3b8; font-size: 14px; padding: 20px;")
        self.draw_stats_layout.addWidget(loading_lbl)

        self._stats_reload_pending = False
        if hasattr(self, '_draw_stats_loader') and self._draw_stats_loader.isRunning():
            self._draw_stats_loader.quit()
            self._draw_stats_loader.wait(100)

        season_id = self._get_active_season_id_for_draw()
        self._draw_stats_loader = DrawStatsLoader(self.category_selected_cycles, season_id=season_id)
        self._draw_stats_loader.stats_loaded.connect(self._on_draw_stats_loaded_full)
        self._draw_stats_loader.start()

    def _format_category_footer_text(self, info):
        total_subs = info.get("total_subs", 0)
        committed_now = info.get("committed_now", 0)
        late_now = info.get("late_now", 0)
        auto_c = info.get("auto_cycle", 1)
        run_c = info.get("current_running_cycle", auto_c)
        run_inst = info.get("running_due_inst_count", 0)
        max_inst = info.get("max_installments", 1)
        last_paid_c = info.get("last_group_paid_cycle", auto_c)

        parts = [
            f"👥 إجمالي الفئة: {total_subs}",
            f"🟢 ملتزمون حالياً: {committed_now}",
            f"🔴 متأخرون: {late_now}",
        ]
        if run_c > auto_c and 0 < run_inst < max_inst:
            parts.append(f"🔄 الدورة الجارية: {run_c} ({run_inst}/{max_inst} أقساط)")
        elif late_now > 0 and last_paid_c < auto_c:
            parts.append(f"📌 آخر دورة سددها المتأخرون: دورة {last_paid_c}")
        return "   |   ".join(parts)

    def _on_draw_stats_loaded_full(self, analytics_map):
        """يُستدعى بعد تحميل الإحصائيات لبناء بطاقات الفئات التفصيلية والدقيقة."""
        if not hasattr(self, '_draw_stats_cache'):
            self._draw_stats_cache = {}
        self._draw_stats_cache.update(analytics_map)

        for i in reversed(range(self.draw_stats_layout.count())):
            item = self.draw_stats_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
            elif item and item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().setParent(None)

        if not analytics_map:
            no_cat_lbl = QLabel("لا توجد فئات مسجلة حالياً.")
            no_cat_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.draw_stats_layout.addWidget(no_cat_lbl)
            return

        grid = QGridLayout()
        grid.setSpacing(15)
        self.draw_stats_layout.addLayout(grid)
        self._draw_stats_labels = {}
        cols = 2

        for idx, (cat_name, info) in enumerate(analytics_map.items()):
            auto_cycle = info.get("auto_cycle", 1)
            running_cycle = info.get("current_running_cycle", auto_cycle)
            total_cycles = info.get("total_cycles", 1)
            selected_cycle = self.category_selected_cycles.get(cat_name, "auto")

            completed_total = info.get("completed_total", 0)
            weekly_eligible = info.get("weekly_eligible", 0)
            incentive_count = info.get("incentive_count", 0)

            cat_card = QFrame()
            cat_card.setObjectName("StatCard")
            v_lay = QVBoxLayout(cat_card)
            v_lay.setSpacing(12)

            header_row = QHBoxLayout()
            header = QLabel(f"📊 {cat_name}")
            header.setObjectName("SectionTitle")
            header.setStyleSheet("font-size: 16px; font-weight: bold;")

            combo_cycle = QComboBox()
            combo_cycle.setMinimumWidth(210)
            combo_cycle.addItem(f"تلقائي — آخر دورة مكتملة (دورة {auto_cycle})", "auto")
            for c_i in range(1, total_cycles + 1):
                tag = ""
                if c_i == auto_cycle:
                    tag = " (مكتملة)"
                elif c_i == running_cycle and running_cycle > auto_cycle:
                    tag = " (جارية حالياً)"
                elif c_i == info.get("last_group_paid_cycle") and info.get("late_now", 0) > 0 and c_i < auto_cycle:
                    tag = " (آخر سداد للمتأخرين)"
                combo_cycle.addItem(f"الدورة {c_i}{tag}", c_i)

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

            # صف الأرقام الثلاثة: (أتموا الدورة) | (مؤهلون للأسبوعية) | (مؤهلون للتحفيزية)
            stats_row = QHBoxLayout()

            c_vbox = QVBoxLayout()
            c_val = QLabel(str(completed_total))
            c_val.setStyleSheet("font-size: 24px; font-weight: 800; color: #0284c7;")
            c_lbl = QLabel("أتموا الدورة")
            c_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
            c_vbox.addWidget(c_val)
            c_vbox.addWidget(c_lbl)

            w_vbox = QVBoxLayout()
            w_val = QLabel(str(weekly_eligible))
            w_val.setStyleSheet("font-size: 24px; font-weight: 800; color: #16a34a;")
            w_lbl = QLabel("مؤهلين الأسبوعية")
            w_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
            w_vbox.addWidget(w_val)
            w_vbox.addWidget(w_lbl)

            i_vbox = QVBoxLayout()
            i_val = QLabel(str(incentive_count))
            i_val.setStyleSheet("font-size: 24px; font-weight: 800; color: #eab308;")
            i_lbl = QLabel("مؤهلين التحفيزية")
            i_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
            i_vbox.addWidget(i_val)
            i_vbox.addWidget(i_lbl)

            stats_row.addLayout(c_vbox)
            stats_row.addStretch()
            stats_row.addLayout(w_vbox)
            stats_row.addStretch()
            stats_row.addLayout(i_vbox)
            v_lay.addLayout(stats_row)

            # شريط معلومات تفصيلي أسفل البطاقة يوضح إجمالي الفئة والملتزمين والمتأخرين
            footer_lbl = QLabel(self._format_category_footer_text(info))
            footer_lbl.setWordWrap(True)
            footer_lbl.setStyleSheet(
                "font-size: 11px; color: #64748b; background: rgba(148, 163, 184, 0.10); "
                "padding: 6px 10px; border-radius: 6px;"
            )
            v_lay.addWidget(footer_lbl)

            self._draw_stats_labels[cat_name] = (c_val, w_val, i_val, footer_lbl)

            def make_on_change(c_box, c_name, c_l, w_l, i_l):
                def on_change():
                    val = c_box.currentData()
                    self.category_selected_cycles[c_name] = val
                    c_l.setText("...")
                    w_l.setText("...")
                    i_l.setText("...")
                    self._trigger_fast_stats_update()
                return on_change

            combo_cycle.currentIndexChanged.connect(
                make_on_change(combo_cycle, cat_name, c_val, w_val, i_val)
            )

            cat_card.setMinimumWidth(340)
            grid.addWidget(cat_card, idx // cols, idx % cols)

    def _trigger_fast_stats_update(self):
        """تشغيل تحديث سريع للإحصائيات مع جدولة تلقائية إذا كان الخيط يعمل حالياً."""
        if hasattr(self, '_draw_stats_loader') and self._draw_stats_loader.isRunning():
            self._stats_reload_pending = True
            return
        self._stats_reload_pending = False
        season_id = self._get_active_season_id_for_draw()
        self._draw_stats_loader = DrawStatsLoader(self.category_selected_cycles, season_id=season_id)
        self._draw_stats_loader.stats_loaded.connect(self._on_draw_stats_loaded)
        self._draw_stats_loader.start()

    def _on_draw_stats_loaded(self, analytics_map):
        """تحديث الأرقام في البطاقات الموجودة فوراً عند تغيير الدورة."""
        if not hasattr(self, '_draw_stats_cache'):
            self._draw_stats_cache = {}
        self._draw_stats_cache.update(analytics_map)
        if hasattr(self, '_draw_stats_labels'):
            for cat_name, info in analytics_map.items():
                if cat_name in self._draw_stats_labels:
                    c_l, w_l, i_l, footer_l = self._draw_stats_labels[cat_name]
                    c_l.setText(str(info.get("completed_total", 0)))
                    w_l.setText(str(info.get("weekly_eligible", 0)))
                    i_l.setText(str(info.get("incentive_count", 0)))
                    footer_l.setText(self._format_category_footer_text(info))

        if getattr(self, '_stats_reload_pending', False):
            self._trigger_fast_stats_update()

    def refresh_draw_categories_filter(self):
        season_id = self._get_active_season_id_for_draw()
        q_cats = self.db.query(db_mod.Category)
        if season_id and season_id != -1:
            q_cats = q_cats.filter(db_mod.Category.season_id == season_id)
        cats = q_cats.all()
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
        self._refresh_draw_ex_cycles_filter()

    def _refresh_draw_ex_cycles_filter(self):
        if not hasattr(self, 'combo_draw_ex_cycle_filter'):
            return
        cat_filter = self.combo_draw_ex_cat_filter.currentData() if hasattr(self, 'combo_draw_ex_cat_filter') else None
        q_cat = self.db.query(db_mod.Category)
        if cat_filter:
            q_cat = q_cat.filter(db_mod.Category.name == cat_filter)
        cats = q_cat.all()
        max_cycles = max([int(getattr(c, 'max_cycles', 1) or 1) for c in cats], default=1)
        # التحقق أيضاً من أقصى رقم دورة مسجل فعلياً في جدول الأقساط
        try:
            max_p_cycle = self.db.query(func.max(db_mod.Payment.cycle_number)).scalar()
            if max_p_cycle and int(max_p_cycle) > max_cycles:
                max_cycles = int(max_p_cycle)
        except Exception:
            pass

        combo = self.combo_draw_ex_cycle_filter
        curr = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("كل الدورات", None)
        for c_num in range(1, max_cycles + 1):
            combo.addItem(f"الدورة {c_num}", c_num)
        if curr is not None:
            idx = combo.findData(curr)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _on_draw_ex_cat_changed(self):
        self._refresh_draw_ex_cycles_filter()
        self.load_draw_excluded()

    def load_recent_winners(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all()
        
        season_id = self._get_active_season_id_for_draw()
        query = self.db.query(db_mod.Winner)
        if season_id and season_id != -1:
            query = query.filter(db_mod.Winner.season_id == season_id)
        if hasattr(self, 'combo_draw_filter'):
            filter_val = self.combo_draw_filter.currentText()
            if filter_val != "الكل":
                query = query.filter(db_mod.Winner.draw_type.contains(filter_val))
                
        winners = query.order_by(db_mod.Winner.draw_date.desc()).all()
        
        # Prefetch subscribers for quick lookup
        q_subs = self.db.query(db_mod.Subscriber)
        if season_id and season_id != -1:
            q_subs = q_subs.filter(db_mod.Subscriber.season_id == season_id)
        subs = q_subs.all()
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

    def _get_draw_excluded_items(self):
        """جلب قائمة المستبعدين من السحب حسب الموسم النشط والفئة المالية ورقم الدورة والبحث السريع."""
        season_id = self._get_active_season_id_for_draw()
        cat_filter = self.combo_draw_ex_cat_filter.currentData() if hasattr(self, 'combo_draw_ex_cat_filter') else None
        cycle_filter = self.combo_draw_ex_cycle_filter.currentData() if hasattr(self, 'combo_draw_ex_cycle_filter') else None
        search_txt = self.draw_ex_search.text().strip().lower() if hasattr(self, 'draw_ex_search') else ""

        q_subs = self.db.query(db_mod.Subscriber)
        q_cats = self.db.query(db_mod.Category)
        if season_id and season_id != -1:
            q_subs = q_subs.filter(db_mod.Subscriber.season_id == season_id)
            q_cats = q_cats.filter(db_mod.Category.season_id == season_id)

        all_subs = q_subs.all()
        fin_status_map = db_mod.calculate_financial_status_batch(all_subs, self.db) if all_subs else {}

        cat_map = {c.name: c for c in q_cats.all()}
        cycle_payments_by_sub = {}
        if cycle_filter is not None:
            raw_p = (
                self.db.query(
                    db_mod.Payment.subscriber_id,
                    db_mod.Payment.cycle_number,
                    db_mod.Payment.installment_number,
                    db_mod.Payment.amount,
                    db_mod.Payment.due_date,
                    db_mod.Payment.paid_date,
                    db_mod.Payment.is_paid,
                )
                .filter(db_mod.Payment.cycle_number == int(cycle_filter))
                .all()
            )
            for p in raw_p:
                cycle_payments_by_sub.setdefault(p[0], []).append(p)
            for sid, plist in list(cycle_payments_by_sub.items()):
                cycle_payments_by_sub[sid] = _dedupe_cycle_payments(plist)

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
            status_plain = ""

            if sub.status == "excluded":
                is_excluded = True
                reason = sub.exclusion_reason or "استبعاد إداري مباشر"
                status_badge = "مستبعد 🚫"
                status_plain = "مستبعد"
            elif sub.status == "pending":
                is_excluded = True
                reason = "طلب اشتراك معلق لم يتم اعتماده بعد"
                status_badge = "معلق 🟡"
                status_plain = "معلق"
            elif cycle_filter is not None:
                cat_obj = cat_map.get(sub.category)
                max_inst = max(1, int(getattr(cat_obj, 'max_installments', 1) or 1)) if cat_obj else 1
                expected_amount = float(getattr(cat_obj, 'amount', 0.0) or 0.0) * max_inst if cat_obj else 0.0
                s_payments = cycle_payments_by_sub.get(sub.id, [])
                if not s_payments:
                    is_excluded = True
                    reason = f"لا توجد أقساط مسجلة في الدورة {cycle_filter}"
                    status_badge = "غير مؤهل ⚪"
                    status_plain = "غير مؤهل"
                else:
                    paid_rows = [p for p in s_payments if p[6]]
                    paid_count = len(paid_rows)
                    total_paid = sum(float(p[3] or 0.0) for p in paid_rows)
                    is_finished = (total_paid >= expected_amount - 0.01) and (paid_count >= max_inst)
                    if not is_finished:
                        is_excluded = True
                        reason = f"لم يُتم أقساط الدورة {cycle_filter} (سدد {paid_count}/{max_inst})"
                        if fin_status == "suspended":
                            status_badge = "موقوف ⚫"
                            status_plain = "موقوف"
                        else:
                            status_badge = "متأخر 🔴"
                            status_plain = "متأخر"
            else:
                if fin_status == "suspended":
                    is_excluded = True
                    reason = "إيقاف آلي بسبب تراكم الأقساط المتأخرة"
                    status_badge = "موقوف ⚫"
                    status_plain = "موقوف"
                elif fin_status == "late":
                    is_excluded = True
                    reason = "تأخر وتعثر عن سداد الأقساط المستحقة"
                    status_badge = "متأخر 🔴"
                    status_plain = "متأخر"

            if is_excluded:
                excluded_list.append({
                    "id": sub.id,
                    "name": sub_name,
                    "acc": sub_acc,
                    "cat": sub_cat,
                    "phone": sub_phone,
                    "reason": reason,
                    "status_badge": status_badge,
                    "status_plain": status_plain,
                    "status": sub.status,
                })
        return excluded_list

    def load_draw_excluded(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.expire_all()

        if not hasattr(self, 'table_draw_excluded'):
            return

        excluded_list = self._get_draw_excluded_items()

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
            excluded_list = self._get_draw_excluded_items()
            items = [{
                "اسم المشترك": it["name"],
                "رقم الحساب": it["acc"],
                "الفئة المالية": it["cat"],
                "رقم الهاتف": it["phone"],
                "سبب الاستبعاد": it["reason"],
                "حالة الانضباط": it["status_plain"],
            } for it in excluded_list]

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
                    self.refresh_draw_stats()
                    ModernDialog(self, "نجاح", "تم حذف السجل بنجاح وتحديث إحصائيات الفئات").exec()
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

        # إظهار نافذة التحميل فوراً لمنع أي تهنيج أو تأخير في استجابة الواجهة
        if hasattr(self, 'show_loading'):
            self.show_loading("جاري تجهيز السحب", "يرجى الانتظار، جاري فحص أهلية المشتركين وتجهيز القرعة...")

        if hasattr(self, '_draw_qual_worker') and self._draw_qual_worker.isRunning():
            self._draw_qual_worker.quit()
            self._draw_qual_worker.wait(100)

        season_id = self._get_active_season_id_for_draw()
        self._draw_qual_worker = DrawQualificationWorker(
            draw_name,
            self.category_selected_cycles,
            selected_period=selected_period,
            periods_count=periods_count,
            weeks_per_period=weeks_per_period,
            season_id=season_id,
        )

        def _on_finished(qualified_by_cat_ids, qualified_ids, disqualified_count):
            if hasattr(self, 'hide_loading'):
                self.hide_loading()
            self._execute_draw_flow(draw_name, qualified_by_cat_ids, qualified_ids, disqualified_count, selected_period, periods_count)

        def _on_error(err_msg):
            if hasattr(self, 'hide_loading'):
                self.hide_loading()
            ModernDialog(self, "خطأ", f"حدث خطأ أثناء فحص المشتركين: {err_msg}").exec()

        self._draw_qual_worker.finished.connect(_on_finished)
        self._draw_qual_worker.error.connect(_on_error)
        self._draw_qual_worker.start()

    def _execute_draw_flow(self, draw_name, qualified_by_cat_ids, qualified_ids, disqualified_count, selected_period, periods_count):
        # جلب كائنات المشتركين المؤهلين فقط
        subs_list = self.db.query(db_mod.Subscriber).filter(db_mod.Subscriber.id.in_(qualified_ids)).all() if qualified_ids else []
        sub_dict = {s.id: s for s in subs_list}

        qualified_subs = [sub_dict[sid] for sid in qualified_ids if sid in sub_dict]
        qualified_by_category = {}
        for cat, sids in qualified_by_cat_ids.items():
            cat_subs = [sub_dict[sid] for sid in sids if sid in sub_dict]
            qualified_by_category[cat] = cat_subs

        analytics_reports = getattr(self._draw_qual_worker, "analytics", None) or {}
        draw_title = f"{draw_name} (الفترة {selected_period})" if (draw_name == "الجائزة الكبرى" and periods_count > 1) else draw_name

        if draw_name in ["القرعة الاسبوعية", "الجائزة التحفيزية"]:
            if not analytics_reports and not qualified_subs:
                msg_alert = f"لا توجد فئات أو مشتركون مستوفون لشروط {draw_title} حالياً."
                ModernDialog(self, "تنبيه", msg_alert).exec()
                return

            # فتح نافذة السحب المتدرجة (تقرير الفئة الأولى -> قرعة الفئة الأولى -> تقرير الفئة الثانية -> قرعة الفئة الثانية -> ... -> التقرير النهائي للفائزين)
            anim_dlg = DrawAnimationDialog(
                self,
                qualified_by_category,
                draw_name,
                self.db,
                category_reports=analytics_reports,
            )
            anim_dlg.exec()
            self.load_recent_winners()
            self.refresh_draw_stats()
            return

        if not qualified_subs:
            msg_alert = f"لا يوجد مشتركون مستوفون لشروط {draw_title} حالياً."
            if disqualified_count > 0:
                msg_alert += f"\n\n(تنبيه: تم استبعاد {disqualified_count} مشتركين بسبب عدم الانضباط المالي: متأخر/موقوف)."
            ModernDialog(self, "تنبيه", msg_alert).exec()
            return

        if draw_name == "الجائزة الكبرى":
            count_setting = self.db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_winners_count").first()
            num_winners = int(count_setting.value) if count_setting and count_setting.value.isdigit() else 1
            num_winners = max(1, num_winners)
            draw_label = f"الجائزة الكبرى - الفترة {selected_period}" if periods_count > 1 else "الجائزة الكبرى"

            # كل فئة تُقرع على حدة ولها تقريرها المستقل، ويُختار من كل فئة عدد الفائزين المحدد في الإعدادات
            anim_dlg = DrawAnimationDialog(
                self,
                qualified_by_category,
                draw_label,
                self.db,
                category_reports=analytics_reports,
                winners_per_category=num_winners,
            )
            anim_dlg.exec()
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

        winner_season_id = getattr(winner, 'season_id', None)
        if not winner_season_id and hasattr(self, 'combo_header_season'):
            winner_season_id = self.combo_header_season.currentData()
        new_w = db_mod.Winner(
            subscriber_number=winner.subscriber_number, 
            draw_type=draw_name,
            draw_date=datetime.datetime.now(),
            cycle_number=cycle_num,
            season_id=winner_season_id
        )
        self.db.add(new_w)
        self.db.commit()
        
        # Show Result
        res_msg = f"مبروك للفائز في {draw_name}!\n\nالفئة المالية: {winner.category}\nرقم المشترك: {winner.subscriber_number}"
        ModernDialog(self, "تم السحب بنجاح", res_msg).exec()
        
        self.load_recent_winners()
        self.refresh_draw_stats()

