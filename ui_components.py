import customtkinter as ctk
import arabic_reshaper
from bidi.algorithm import get_display

def fix_text(text):
    if not text: return ""
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)
    except:
        return text

class ModernAlert(ctk.CTkToplevel):
    def __init__(self, parent, title, message, icon="info"):
        super().__init__(parent)
        self.title(fix_text(title))
        self.geometry("400x200")
        self.attributes("-topmost", True)
        self.grid_columnconfigure(0, weight=1)
        
        self.label = ctk.CTkLabel(self, text=fix_text(message), font=ctk.CTkFont(family="Tajawal", size=14), wraplength=350)
        self.label.pack(pady=40, padx=20)
        
        btn_color = "#10b981" if icon == "info" else "#ef4444"
        self.btn = ctk.CTkButton(self, text=fix_text("موافق"), command=self.destroy, fg_color=btn_color, width=100)
        self.btn.pack(pady=10)
        
        # Center the window
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        self.grab_set()

class ModernConfirm(ctk.CTkToplevel):
    def __init__(self, parent, title, message, callback):
        super().__init__(parent)
        self.title(fix_text(title))
        self.geometry("400x200")
        self.attributes("-topmost", True)
        self.result = False
        self.callback = callback
        
        self.label = ctk.CTkLabel(self, text=fix_text(message), font=ctk.CTkFont(family="Tajawal", size=14), wraplength=350)
        self.label.pack(pady=40, padx=20)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        self.btn_yes = ctk.CTkButton(btn_frame, text=fix_text("نعم"), command=self.confirm, fg_color="#ef4444", width=80)
        self.btn_yes.pack(side="left", padx=10)
        
        self.btn_no = ctk.CTkButton(btn_frame, text=fix_text("إلغاء"), command=self.destroy, fg_color="gray", width=80)
        self.btn_no.pack(side="left", padx=10)
        
        # Center the window
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    def confirm(self):
        self.destroy()
        self.callback()

class ModernInput(ctk.CTkToplevel):
    def __init__(self, parent, title, message, callback, initial_value=""):
        super().__init__(parent)
        self.title(fix_text(title))
        self.geometry("400x250")
        self.attributes("-topmost", True)
        self.callback = callback
        
        self.label = ctk.CTkLabel(self, text=fix_text(message), font=ctk.CTkFont(family="Tajawal", size=14))
        self.label.pack(pady=(20, 10), padx=20)
        
        self.entry = ctk.CTkEntry(self, width=300)
        self.entry.insert(0, initial_value)
        self.entry.pack(pady=10, padx=20)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        self.btn_save = ctk.CTkButton(btn_frame, text=fix_text("حفظ"), command=self.save, fg_color="#6366f1", width=100)
        self.btn_save.pack(side="left", padx=10)
        
        self.btn_cancel = ctk.CTkButton(btn_frame, text=fix_text("إلغاء"), command=self.destroy, fg_color="gray", width=100)
        self.btn_cancel.pack(side="left", padx=10)
        
        # Center the window
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        self.focus_set()
        self.grab_set()

    def save(self):
        val = self.entry.get()
        self.destroy()
        self.callback(val)
