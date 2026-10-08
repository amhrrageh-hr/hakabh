import sys
import os
from reportlab.pdfbase import pdfmetrics
import subprocess
import re
from PyQt6.QtCore import QObject, pyqtSignal
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

def setup_excel_header(workbook, worksheet, df, title, subtitle, company_name, company_logo_path, start_row=8):
    import os
    worksheet.right_to_left()
    header_bg = '#052109'
    title_color = '#c9a84c'
    header_font_color = '#FFFFFF'
    
    header_format = workbook.add_format({'bold': True, 'bg_color': header_bg, 'color': title_color, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial', 'font_size': 12})
    title_format = workbook.add_format({'bold': True, 'font_size': 20, 'color': title_color, 'bg_color': header_bg, 'align': 'center', 'valign': 'vcenter'})
    subtitle_format = workbook.add_format({'font_size': 11, 'color': header_font_color, 'bg_color': header_bg, 'align': 'center', 'valign': 'vcenter'})
    
    num_cols = max(len(df.columns), 6)
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
    
    worksheet.set_row(start_row - 4, 30)
    for col_num, value in enumerate(df.columns.values): 
        worksheet.write(start_row, col_num, value, header_format)
        
    worksheet.freeze_panes(start_row + 1, 0)
    worksheet.hide_gridlines(2)
    
    for i, col in enumerate(df.columns):
        max_len = max(df[col].astype(str).map(len).max(), len(str(col))) + 2
        worksheet.set_column(i, i, max_len)

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
