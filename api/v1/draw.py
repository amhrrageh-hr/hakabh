import datetime
import random
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import database as db_mod
from api.auth import get_db, verify_admin_api_key
from api.schemas import (
    DrawCategoryStatItem, DrawStatsSummaryOut, 
    QualifiedDrawSubscriber, PerformDrawRequest, WinnerOut
)

router = APIRouter(prefix="/draw", tags=["Draw"], dependencies=[Depends(verify_admin_api_key)])

class DrawExcludedItem(BaseModel):
    id: int
    name: str
    subscriber_number: str
    category: str
    phone: str
    reason: str
    status_badge: str
    status: str

class WinnerReceiptUpdate(BaseModel):
    is_received: bool
    payout_amount: Optional[float] = 0.0

def _get_incentive_max_late(db: Session) -> int:
    try:
        late3 = db.query(db_mod.Setting).filter(db_mod.Setting.key == "incentive_allow_late_3").first()
        late2 = db.query(db_mod.Setting).filter(db_mod.Setting.key == "incentive_allow_late_2").first()
        late1 = db.query(db_mod.Setting).filter(db_mod.Setting.key == "incentive_allow_late_1").first()
        if late3 and late3.value == "1":
            return 3
        if late2 and late2.value == "1":
            return 2
        if late1 and late1.value == "1":
            return 1
    except Exception:
        pass
    return 0

@router.get("/stats", response_model=DrawStatsSummaryOut)
def get_draw_stats(db: Session = Depends(get_db)):
    """حساب إحصائيات التأهل للسحب لجميع الفئات دفعة واحدة على الخادم"""
    today = datetime.datetime.now()
    today_date = today.date()
    categories = db.query(db_mod.Category).all()

    all_accepted_subs = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted").all()
    fin_status_map = db_mod.calculate_financial_status_batch(all_accepted_subs, db)

    disciplined_subs = [s for s in all_accepted_subs if fin_status_map.get(s.id) not in ["late", "suspended"]]
    sub_ids = [s.id for s in disciplined_subs]

    active_cycles = dict(
        db.query(db_mod.Payment.subscriber_id, func.max(db_mod.Payment.cycle_number))
        .filter(db_mod.Payment.subscriber_id.in_(sub_ids), db_mod.Payment.due_date <= today)
        .group_by(db_mod.Payment.subscriber_id).all()
    ) if sub_ids else {}

    needed_cycles = set(active_cycles.values()) if active_cycles else {1}
    payments_data = db.query(
        db_mod.Payment.subscriber_id,
        db_mod.Payment.cycle_number,
        db_mod.Payment.amount,
        db_mod.Payment.due_date,
        db_mod.Payment.paid_date,
        db_mod.Payment.is_paid
    ).filter(
        db_mod.Payment.subscriber_id.in_(sub_ids),
        db_mod.Payment.cycle_number.in_(needed_cycles)
    ).all() if sub_ids else []

    payments_by_sub = {}
    for p in payments_data:
        payments_by_sub.setdefault(p[0], []).append(p)

    subs_by_cat = {}
    for s in disciplined_subs:
        subs_by_cat.setdefault(s.category, []).append(s)

    max_late_allowed = _get_incentive_max_late(db)
    results = []

    for cat in categories:
        subs_in_cat = subs_by_cat.get(cat.name, [])
        completed_cycle_count = 0
        incentive_count = 0
        max_inst = cat.max_installments or 12
        total_expected_for_cycle = (cat.amount or 0.0) * max_inst

        for sub in subs_in_cat:
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

        results.append(
            DrawCategoryStatItem(
                category_name=cat.name,
                active_cycle=1,
                total_cycles=cat.max_cycles or 1,
                selected_cycle="auto",
                completed_cycle_count=completed_cycle_count,
                incentive_count=incentive_count
            )
        )

    return DrawStatsSummaryOut(categories=results)

@router.get("/candidates", response_model=List[QualifiedDrawSubscriber])
def get_draw_candidates(
    draw_type: str = Query("القرعة الاسبوعية"),
    category: Optional[str] = None,
    cycle: Optional[str] = "auto",
    db: Session = Depends(get_db)
):
    """جلب قائمة المشتركين المؤهلين للقرعة المحددة"""
    today = datetime.datetime.now()
    query = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.status == "accepted")
    if category and category != "الكل":
        query = query.filter(db_mod.Subscriber.category == category)
    
    subs = query.all()
    if not subs:
        return []

    fin_status_map = db_mod.calculate_financial_status_batch(subs, db)
    disciplined_subs = [s for s in subs if fin_status_map.get(s.id) not in ["late", "suspended"]]
    sub_ids = [s.id for s in disciplined_subs]

    active_cycles = dict(
        db.query(db_mod.Payment.subscriber_id, func.max(db_mod.Payment.cycle_number))
        .filter(db_mod.Payment.subscriber_id.in_(sub_ids), db_mod.Payment.due_date <= today)
        .group_by(db_mod.Payment.subscriber_id).all()
    ) if sub_ids else {}

    cats_map = {c.name: c for c in db.query(db_mod.Category).all()}
    max_late_allowed = _get_incentive_max_late(db)

    # جلب دفعات هؤلاء المشتركين
    needed_cycles = set(active_cycles.values()) if active_cycles else {1}
    payments_data = db.query(
        db_mod.Payment.subscriber_id,
        db_mod.Payment.cycle_number,
        db_mod.Payment.amount,
        db_mod.Payment.due_date,
        db_mod.Payment.paid_date,
        db_mod.Payment.is_paid
    ).filter(
        db_mod.Payment.subscriber_id.in_(sub_ids),
        db_mod.Payment.cycle_number.in_(needed_cycles)
    ).all() if sub_ids else []

    payments_by_sub = {}
    for p in payments_data:
        payments_by_sub.setdefault(p[0], []).append(p)

    candidates = []
    for sub in disciplined_subs:
        sub_cycle = active_cycles.get(sub.id, 1)
        sub_payments = [p for p in payments_by_sub.get(sub.id, []) if p[1] == sub_cycle]
        if not sub_payments:
            continue

        cat = cats_map.get(sub.category)
        max_inst = cat.max_installments if cat else 12
        total_expected = (cat.amount * max_inst) if cat else 0.0
        total_paid = sum(p[2] for p in sub_payments if p[5])
        is_cycle_finished = (total_paid >= total_expected - 0.01) and all(p[5] for p in sub_payments)

        is_incentive = True
        has_paid_something = False
        late_count = 0
        for p in sub_payments:
            if not p[3]:
                continue
            p_due = p[3].date()
            is_p = p[5]
            p_paid = p[4].date() if p[4] else None

            if p_due <= today.date():
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

        is_qualified = False
        if draw_type == "القرعة الاسبوعية":
            already_won = db.query(db_mod.Winner).filter(
                db_mod.Winner.subscriber_number == sub.subscriber_number,
                db_mod.Winner.draw_type.contains("القرعة الاسبوعية"),
                (db_mod.Winner.cycle_number == sub_cycle) | (db_mod.Winner.cycle_number == None)
            ).first()
            if already_won:
                continue
            if is_cycle_finished:
                is_qualified = True
        elif draw_type == "الجائزة التحفيزية" and is_incentive and has_paid_something:
            is_qualified = True
        elif draw_type == "الجائزة الكبرى" and is_cycle_finished:
            is_qualified = True

        if is_qualified:
            ratio = (total_paid / total_expected * 100) if total_expected > 0 else 0.0
            candidates.append(
                QualifiedDrawSubscriber(
                    sub_id=sub.id,
                    name=sub.name,
                    phone=sub.phone,
                    category=sub.category or "-",
                    number=sub.subscriber_number or "",
                    draw_type=draw_type,
                    cycle=sub_cycle,
                    pay_ratio=round(ratio, 2),
                    total_paid=total_paid,
                    total_expected=total_expected,
                    fin_status=fin_status_map.get(sub.id, "active"),
                    is_qualified=True
                )
            )

    return candidates

@router.post("/perform")
def perform_draw_api(
    req: PerformDrawRequest,
    db: Session = Depends(get_db)
):
    """إجراء السحب الآلي للقرعة وحفظ الفائزين وإرجاع النتائج للمدير فقط"""
    draw_type = req.draw_type
    category = req.category if req.category and req.category != "الكل" else None

    # 1. جلب المرشحين المؤهلين
    candidates = get_draw_candidates(draw_type=draw_type, category=category, cycle=req.cycle or "auto", db=db)
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"لا يوجد مشتركون مؤهلون ومستوفون لشروط '{draw_type}' حالياً في الفئة المحددة."
        )

    # تجميع المرشحين حسب الفئة
    cand_by_cat = {}
    for c in candidates:
        cand_by_cat.setdefault(c.category, []).append(c)

    winners_created = []
    now = datetime.datetime.now()

    if draw_type in ["القرعة الاسبوعية", "الجائزة التحفيزية"]:
        # اختيار فائز واحد لكل فئة مؤهلة
        for cat_name, cat_candidates in cand_by_cat.items():
            chosen = random.choice(cat_candidates)
            draw_label = f"{draw_type} - {cat_name}"
            new_w = db_mod.Winner(
                subscriber_number=chosen.number,
                draw_type=draw_label,
                draw_date=now,
                cycle_number=chosen.cycle,
                payout_amount=0.0,
                is_received=False
            )
            db.add(new_w)
            winners_created.append({
                "subscriber_number": chosen.number,
                "subscriber_name": chosen.name,
                "phone": chosen.phone,
                "category": cat_name,
                "draw_name": draw_label,
                "draw_date": now.strftime("%Y-%m-%d %H:%M"),
                "cycle_number": chosen.cycle,
                "instance": new_w
            })
    else:
        # الجائزة الكبرى
        count_setting = db.query(db_mod.Setting).filter(db_mod.Setting.key == "grand_prize_winners_count").first()
        num_winners = int(count_setting.value) if count_setting and count_setting.value.isdigit() else 1
        num_winners = max(1, min(num_winners, len(candidates)))

        chosen_list = random.sample(candidates, num_winners)
        period = req.period or 1
        draw_label = f"الجائزة الكبرى - الفترة {period}" if period > 1 else "الجائزة الكبرى"

        for chosen in chosen_list:
            new_w = db_mod.Winner(
                subscriber_number=chosen.number,
                draw_type=draw_label,
                draw_date=now,
                cycle_number=chosen.cycle,
                payout_amount=0.0,
                is_received=False
            )
            db.add(new_w)
            winners_created.append({
                "subscriber_number": chosen.number,
                "subscriber_name": chosen.name,
                "phone": chosen.phone,
                "category": chosen.category,
                "draw_name": draw_label,
                "draw_date": now.strftime("%Y-%m-%d %H:%M"),
                "cycle_number": chosen.cycle,
                "instance": new_w
            })

    db.commit()

    # تحديث المعرفات بعد الحفظ
    result = []
    for w in winners_created:
        result.append({
            "id": w["instance"].id,
            "subscriber_number": w["subscriber_number"],
            "subscriber_name": w["subscriber_name"],
            "phone": w["phone"],
            "category": w["category"],
            "draw_name": w["draw_name"],
            "draw_date": w["draw_date"],
            "cycle_number": w["cycle_number"]
        })

    # إشعار عبر الـ WebSocket إذا كان المشترك متصلاً
    try:
        from main import manager
        import asyncio
        for res_w in result:
            sub_obj = db.query(db_mod.Subscriber).filter(db_mod.Subscriber.subscriber_number == res_w['subscriber_number']).first()
            if sub_obj:
                asyncio.create_task(manager.send_personal_message(f"🎉 ألف مبروك! لقد فزت بـ {res_w['draw_name']}", sub_obj.id))
    except Exception:
        pass

    return {
        "success": True,
        "message": f"تم إجراء السحب بنجاح واختيار {len(result)} فائز(ين)",
        "winners": result
    }

@router.get("/excluded", response_model=List[DrawExcludedItem])
def get_draw_excluded(
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """جلب قائمة المستبعدين من السحب مع توضيح سبب الاستبعاد بدقة"""
    all_subs = db.query(db_mod.Subscriber).all()
    fin_status_map = db_mod.calculate_financial_status_batch(all_subs, db)

    excluded_list = []
    for sub in all_subs:
        sub_cat = sub.category or "-"
        if category and category != "الكل" and sub_cat != category:
            continue

        if search:
            st = search.strip().lower()
            name_m = st in (sub.name or "").lower()
            acc_m = st in (sub.subscriber_number or "").lower()
            ph_m = st in (sub.phone or "").lower()
            if not (name_m or acc_m or ph_m):
                continue

        fin_status = fin_status_map.get(sub.id, "pending")
        is_excluded = False
        reason = ""
        badge = ""

        if sub.status == "excluded":
            is_excluded = True
            reason = sub.exclusion_reason or "استبعاد إداري مباشر"
            badge = "مستبعد 🚫"
        elif fin_status == "suspended":
            is_excluded = True
            reason = "إيقاف آلي بسبب تراكم الأقساط المتأخرة"
            badge = "موقوف ⚫"
        elif fin_status == "late":
            is_excluded = True
            reason = "تأخر وتعثر عن سداد الأقساط المستحقة"
            badge = "متأخر 🔴"
        elif sub.status == "pending":
            is_excluded = True
            reason = "طلب اشتراك معلق لم يتم اعتماده بعد"
            badge = "معلق ⏳"

        if is_excluded:
            excluded_list.append(
                DrawExcludedItem(
                    id=sub.id,
                    name=sub.name,
                    subscriber_number=sub.subscriber_number or "-",
                    category=sub_cat,
                    phone=sub.phone,
                    reason=reason,
                    status_badge=badge,
                    status=sub.status
                )
            )

    return excluded_list

@router.get("/winners")
def list_winners(
    draw_type: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """جلب سجل الفائزين مع تفاصيل المشتركين والتصفية السريعة"""
    query = db.query(db_mod.Winner)
    if draw_type and draw_type != "الكل":
        query = query.filter(db_mod.Winner.draw_type.contains(draw_type))

    winners = query.order_by(db_mod.Winner.draw_date.desc()).offset(skip).limit(limit).all()
    if not winners:
        return []

    subs = db.query(db_mod.Subscriber).all()
    sub_map = {s.subscriber_number: s for s in subs}

    items = []
    for w in winners:
        sub = sub_map.get(w.subscriber_number)
        sub_name = sub.name if sub else "غير مسجل"
        sub_cat = sub.category if sub else "-"
        sub_phone = sub.phone if sub else "-"

        if category and category != "الكل" and sub_cat != category:
            continue

        if search:
            st = search.strip().lower()
            name_m = st in sub_name.lower()
            acc_m = st in (w.subscriber_number or "").lower()
            ph_m = st in sub_phone.lower()
            if not (name_m or acc_m or ph_m):
                continue

        items.append({
            "id": w.id,
            "draw_name": w.draw_type or "-",
            "subscriber_number": w.subscriber_number or "-",
            "subscriber_name": sub_name,
            "phone": sub_phone,
            "category": sub_cat,
            "cycle_number": w.cycle_number,
            "draw_date": w.draw_date.strftime("%Y-%m-%d %H:%M") if w.draw_date else "-",
            "payout_amount": getattr(w, "payout_amount", 0.0) or 0.0,
            "is_received": getattr(w, "is_received", False)
        })

    return items

@router.put("/winners/{winner_id}/receipt")
def update_winner_receipt(winner_id: int, req: WinnerReceiptUpdate, db: Session = Depends(get_db)):
    """تحديث حالة استلام مستحقات الفائز والمبلغ المستلم"""
    w = db.get(db_mod.Winner, winner_id)
    if not w:
        raise HTTPException(status_code=404, detail="سجل الفائز غير موجود")

    w.is_received = req.is_received
    w.payout_amount = req.payout_amount
    db.commit()
    return {"success": True, "winner_id": winner_id, "is_received": w.is_received, "payout_amount": w.payout_amount}
