import sys
import os
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


class ServerWorker(QObject):
    link_found = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.process = None
        self._running = True # استخدام _running لتجنب تضارب الأسماء
        self._uvicorn_error = None # لتخزين الاستثناءات من ثريد uvicorn
        self._uvicorn_thread = None

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

            # دالة داخلية لتشغيل uvicorn والتقاط الاستثناءات
            def _start_uvicorn_target(worker_instance):
                try:
                    uvicorn.run(app, host="0.0.0.0", port=8765) # إزالة log_level="error" لرؤية جميع السجلات
                except Exception as e:
                    worker_instance._uvicorn_error = e # تخزين الاستثناء
                    worker_instance.error_occurred.emit(f"خطأ في تشغيل خادم FastAPI: {e}")

            # تشغيل الخادم فقط إذا لم يكن يعمل مسبقاً
            if not is_port_in_use(8765):
                self._uvicorn_thread = threading.Thread(target=_start_uvicorn_target, args=(self,), daemon=True)
                self._uvicorn_thread.start()
            else:
                self.error_occurred.emit("المنفذ 8765 مشغول بالفعل. يرجى إغلاق أي تطبيق آخر يستخدم هذا المنفذ.")
                return
            
            # انتظر حتى يصبح الخادم جاهزاً للاستجابة (حد أقصى 10 ثوانٍ)
            server_ready = False
            for _ in range(10):
                if is_port_in_use(8765):
                    server_ready = True
                    break
                time.sleep(1)
            
            if not server_ready:
                if self._uvicorn_error:
                    self.error_occurred.emit(f"خادم FastAPI لم يبدأ أو حدث به خطأ: {self._uvicorn_error}")
                else:
                    self.error_occurred.emit("خادم FastAPI لم يبدأ في الوقت المحدد (10 ثوانٍ).")
                return

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
            while self._running:
                line = self.process.stdout.readline()
                if not line:
                    # التحقق مما إذا كان ثريد uvicorn قد تعطل
                    if self._uvicorn_thread and not self._uvicorn_thread.is_alive() and self._uvicorn_error:
                        self.error_occurred.emit(f"خادم FastAPI توقف بشكل غير متوقع: {self._uvicorn_error}")
                    break
                
                match = re.search(r'https://[a-zA-Z0-9.-]+\.trycloudflare\.com', line)
                if match and not found_link:
                    self.link_found.emit(match.group(0))
                    found_link = True
                # استمرار قراءة الأسطر ضروري لمنع تعليق عملية cloudflared في ويندوز
                # التحقق أيضاً من أخطاء uvicorn أثناء التشغيل
                if self._uvicorn_error:
                    self.error_occurred.emit(f"خطأ في خادم FastAPI أثناء التشغيل: {self._uvicorn_error}")
                    break
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self._running = False
        if self.process:
            self.process.terminate()
        # لا يوجد إيقاف صريح لثريد uvicorn daemon، سيتم إغلاقه مع العملية الرئيسية.
        # إذا كانت هناك حاجة لإيقاف أكثر سلاسة، فسيتطلب ذلك كائن uvicorn.Server.
        # في الوقت الحالي، نضمن فقط إنهاء عملية cloudflared.
