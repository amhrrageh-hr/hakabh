import sys
import os
from reportlab.pdfbase import pdfmetrics
import subprocess
import re
from PyQt6.QtCore import QObject, QEvent, pyqtSignal
import arabic_reshaper
from bidi.algorithm import get_display

def reshape_text(text):
    if not text: return ""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

def draw_pdf_header(c, title, subtitle, page_num, W, H, M, font_name, company_name, company_legal_name, company_record, company_logo_path):
    from reportlab.lib import colors
    import datetime
    import os
    GOLD        = colors.HexColor("#c9a84c")
    DARK_GREEN  = colors.HexColor("#052109")
    c.setFillColor(DARK_GREEN)
    c.roundRect(M, H - 132, W - 2*M, 120, 8, fill=1, stroke=0)
    if company_logo_path and os.path.exists(company_logo_path):
        try: c.drawImage(company_logo_path, M + 12, H - 122, width=68, height=68, preserveAspectRatio=True, mask='auto')
        except Exception: pass
    cx = W / 2
    c.setFillColor(GOLD)
    c.setFont(font_name, 22)
    c.drawCentredString(cx, H - 68, reshape_text(company_name))
    c.setFont(font_name, 11)
    c.setFillColor(colors.white)
    c.drawCentredString(cx, H - 84, reshape_text(company_legal_name))
    if company_record:
        c.setFont(font_name, 8)
        c.setFillColor(colors.HexColor("#a5d6a7"))
        c.drawCentredString(cx, H - 97, reshape_text(f"السجل التجاري: {company_record}"))
    c.setFont(font_name, 9)
    c.setFillColor(colors.HexColor("#a5d6a7"))
    c.drawRightString(W - M - 12, H - 62, reshape_text(f"تاريخ الإصدار: {datetime.date.today().strftime('%Y-%m-%d')}"))
    c.setFont(font_name, 8)
    c.setFillColor(colors.HexColor("#69f0ae"))
    c.drawRightString(W - M - 12, H - 76, reshape_text(title))
    c.setFont(font_name, 8)
    c.setFillColor(colors.white)
    c.drawRightString(W - M - 12, H - 90, reshape_text(f"صفحة {page_num}"))
    if subtitle:
        c.setFont(font_name, 8)
        c.setFillColor(colors.white)
        c.drawRightString(W - M - 12, H - 104, reshape_text(subtitle))
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(M, H - 137, W - M, H - 137)
    # إعادة تعيين اللون الافتراضي للأسود حتى لا تُرسم النصوص اللاحقة باللون الأبيض على خلفية بيضاء
    c.setFillColor(colors.black)
    c.setStrokeColor(colors.black)
    c.setFont(font_name, 10)

def get_safe_db_url(db_session):
    """إرجاع رابط قاعدة البيانات الفعلي دون إخفاء كلمة المرور للـ Threads المنفصلة"""
    try:
        bind = db_session.get_bind()
        return bind.url.render_as_string(hide_password=False)
    except Exception:
        import database as db_mod
        return db_mod.get_database_url()

def setup_excel_header(workbook, worksheet, df, title, subtitle, company_name, company_logo_path, start_row=8):
    import os
    worksheet.right_to_left()
    header_bg = '#052109'
    title_color = '#c9a84c'
    header_font_color = '#FFFFFF'
    
    header_format = workbook.add_format({'bold': True, 'bg_color': header_bg, 'color': title_color, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial', 'font_size': 12})
    title_format = workbook.add_format({'bold': True, 'font_size': 20, 'color': title_color, 'bg_color': header_bg, 'align': 'center', 'valign': 'vcenter'})
    subtitle_format = workbook.add_format({'font_size': 11, 'color': header_font_color, 'bg_color': header_bg, 'align': 'center', 'valign': 'vcenter'})
    
    num_cols = max(len(df.columns) if hasattr(df, 'columns') else 0, 6)
    def get_col_letter(n):
        result = ""
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            result = chr(65 + remainder) + result
        return result
    last_col_letter = get_col_letter(num_cols)
    
    worksheet.merge_range(f'A1:{last_col_letter}2', company_name, title_format)
    if company_logo_path and os.path.exists(company_logo_path):
        try:
            from PyQt6.QtGui import QImage
            img = QImage(company_logo_path)
            scale = 60.0 / img.height() if img.height() > 0 else 0.5
            scale = min(scale, 1.0)
        except Exception:
            scale = 0.5
        worksheet.insert_image('A1', company_logo_path, {'x_offset': 5, 'y_offset': 5, 'x_scale': scale, 'y_scale': scale})
    worksheet.merge_range(f'A3:{last_col_letter}3', title, subtitle_format)
    if subtitle:
        worksheet.merge_range(f'A4:{last_col_letter}4', subtitle, subtitle_format)
    
    if start_row >= 4:
        worksheet.set_row(start_row - 4, 30)
    for col_num, value in enumerate(df.columns.values): 
        worksheet.write(start_row, col_num, value, header_format)
        
    worksheet.freeze_panes(start_row + 1, 0)
    worksheet.hide_gridlines(2)
    
    if not df.empty:
        for i, col in enumerate(df.columns):
            try:
                lens = df[col].dropna().astype(str).map(len)
                max_val_len = lens.max() if not lens.empty else 0
                max_len = max(max_val_len, len(str(col))) + 3
            except Exception:
                max_len = len(str(col)) + 4
            worksheet.set_column(i, i, max(max_len, 12))

def register_arabic_font():
    """
    يبحث عن خط عربي شائع ويسجله في ReportLab.
    يعيد اسم الخط المسجل أو 'Helvetica' كبديل.
    """
    font_name = "ArabicFont"
    if font_name in pdfmetrics.getRegisteredFontNames():
        return font_name

    possible_fonts = [
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "static/tahoma.ttf", # مسار نسبي داخل المشروع
        "static/arial.ttf"
    ]
    font_path = next((p for p in possible_fonts if os.path.exists(p)), None)
    if font_path:
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        return font_name
    return "Helvetica"


class ServerWorker(QObject):
    link_found = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.process = None
        self.running = True

    def run(self):
        try:
            # Creation flags for Windows to hide the console window
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            # 1. Start main.py (Web Server) in the background
            import threading
            import time
            import socket
            import uvicorn
            from main import app

            def is_port_in_use(port: int) -> bool:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    return s.connect_ex(("127.0.0.1", port)) == 0

            def start_uvicorn():
                try:
                    import sys
                    import os
                    if sys.stdout is None:
                        sys.stdout = open(os.devnull, "w")
                    if sys.stderr is None:
                        sys.stderr = open(os.devnull, "w")
                    
                    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="error")
                except Exception as e:
                    try:
                        with open("server_error.log", "w", encoding="utf-8") as f:
                            f.write(str(e))
                    except:
                        pass

            # تشغيل الخادم فقط إذا لم يكن يعمل مسبقاً
            if not is_port_in_use(8765):
                threading.Thread(target=start_uvicorn, daemon=True).start()
            
            # انتظر حتى يصبح الخادم جاهزاً للاستجابة (حد أقصى 10 ثوانٍ)
            for _ in range(10):
                if is_port_in_use(8765):
                    break
                time.sleep(1)

            # 2. Start cloudflared (Tunnel)
            if getattr(sys, 'frozen', False):
                base_dir = sys._MEIPASS
            else:
                # الانتقال للمجلد الرئيسي للمشروع (المجلد الأب لمجلد gui)
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            cloudflared_path = os.path.join(base_dir, "cloudflared.exe")
            
            if not os.path.exists(cloudflared_path):
                self.error_occurred.emit("ملف cloudflared.exe غير موجود!")
                return

            self.process = subprocess.Popen(
                [cloudflared_path, "tunnel", "--url", "http://localhost:8765"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                creationflags=creation_flags
            )

            found_link = False
            while self.running:
                line = self.process.stdout.readline()
                if not line: break
                
                match = re.search(r'https://[a-zA-Z0-9.-]+\.trycloudflare\.com', line)
                if match and not found_link:
                    self.link_found.emit(match.group(0))
                    found_link = True
                # استمرار قراءة الأسطر ضروري لمنع تعليق عملية cloudflared في ويندوز
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()


def get_available_screen_geometry(widget=None):
    """إرجاع أبعاد الشاشة المتاحة (بدون شريط المهام) لأي جهاز أو شاشة."""
    from PyQt6.QtWidgets import QApplication
    screen = None
    if widget is not None:
        try:
            screen = widget.screen()
        except Exception:
            screen = None
        if screen is None and widget.parent() is not None:
            try:
                screen = widget.parent().screen()
            except Exception:
                screen = None
    if screen is None:
        screen = QApplication.primaryScreen()
    return screen.availableGeometry() if screen else None


class _DialogScreenFitFilter(QObject):
    """فلتر أحداث خفيف لضبط أبعاد أي نافذة حوار وتوسيطها بدقة عند العرض."""
    def __init__(self, dialog, preferred_w=None, preferred_h=None, fixed_width=False, fixed_size=False):
        super().__init__(dialog)
        self._dialog = dialog
        self._preferred_w = preferred_w
        self._preferred_h = preferred_h
        self._fixed_width = fixed_width
        self._fixed_size = fixed_size
        self._applied = False

    def eventFilter(self, obj, event):
        if obj is self._dialog and event.type() == QEvent.Type.Show and not self._applied:
            self._applied = True
            _apply_dialog_screen_fit(
                self._dialog,
                preferred_w=self._preferred_w,
                preferred_h=self._preferred_h,
                fixed_width=self._fixed_width,
                fixed_size=self._fixed_size,
            )
        return super().eventFilter(obj, event)


def _apply_dialog_screen_fit(dialog, preferred_w=None, preferred_h=None, fixed_width=False, fixed_size=False):
    avail = get_available_screen_geometry(dialog)
    if not avail:
        if preferred_w and preferred_h:
            dialog.resize(int(preferred_w), int(preferred_h))
        elif preferred_w:
            dialog.resize(int(preferred_w), max(160, dialog.sizeHint().height()))
        return

    max_w = max(320, int(avail.width() * 0.94))
    max_h = max(280, int(avail.height() * 0.92))
    dialog.setMaximumSize(max_w, max_h)

    hint = dialog.sizeHint()
    target_w = min(int(preferred_w), max_w) if preferred_w else min(max(360, hint.width()), max_w)
    if preferred_h:
        target_h = min(int(preferred_h), max_h)
    else:
        target_h = min(max(160, hint.height()), max_h)

    if fixed_size:
        dialog.setFixedSize(target_w, target_h)
    elif fixed_width:
        dialog.setFixedWidth(target_w)
        dialog.resize(target_w, target_h)
    else:
        dialog.resize(target_w, target_h)

    pos_x = avail.x() + max(0, (avail.width() - target_w) // 2)
    pos_y = avail.y() + max(0, (avail.height() - target_h) // 2)
    dialog.move(pos_x, pos_y)


def fit_dialog_to_screen(dialog, preferred_w=None, preferred_h=None, fixed_width=False, fixed_size=False):
    """ضبط حجم أي نافذة حوار وتوسيطها تلقائياً لتتلاءم مع الشاشات الصغيرة والكبيرة دون تجاوز حدود الشاشة."""
    _apply_dialog_screen_fit(
        dialog,
        preferred_w=preferred_w,
        preferred_h=preferred_h,
        fixed_width=fixed_width,
        fixed_size=fixed_size,
    )
    if not getattr(dialog, "_screen_fit_filter", None):
        flt = _DialogScreenFitFilter(
            dialog,
            preferred_w=preferred_w,
            preferred_h=preferred_h,
            fixed_width=fixed_width,
            fixed_size=fixed_size,
        )
        dialog._screen_fit_filter = flt
        dialog.installEventFilter(flt)
