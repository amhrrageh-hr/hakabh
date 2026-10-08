import sys
import os
import datetime
from sqlalchemy.orm import Session
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database as db_mod
from gui.utils import reshape_text, draw_pdf_header, register_arabic_font

def test_pdf():
    db = next(db_mod.get_db())
    # create a dummy subscriber if needed, or get first
    sub = db.query(db_mod.Subscriber).first()
    if not sub:
        print("No subscriber found")
        return
    
    payments = db.query(db_mod.Payment).filter(db_mod.Payment.subscriber_id == sub.id).all()
    
    total_paid = sum(p.amount for p in payments if p.is_paid)
    total_due = sum(p.amount for p in payments if not p.is_paid)
    
    file_path = "scratch/test_statement.pdf"
    
    try:
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

        def get_setting(key, default=""):
            s = db.query(db_mod.Setting).filter(db_mod.Setting.key == key).first()
            return s.value if s else default

        company_name       = get_setting("company_name",             "هكبة المليون")
        company_legal_name = get_setting("company_legal_name",       "الاسبوعية")
        company_record     = get_setting("company_commercial_record", "")
        company_logo_path  = get_setting("company_logo_path",        "")

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
        HDRS  = ["الدورة/القسط", "المبلغ", "الاستحقاق", "تاريخ الاستحقاق", "تاريخ السداد", "الحالة", "ملاحظة"]
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
        print("Success")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf()
