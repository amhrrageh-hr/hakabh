# Global Styling - Hakbah Premium Light Theme
HAKBAH_LIGHT = """
QMainWindow { background-color: #f7f9fc; }
QWidget { color: #1e293b; font-family: 'Tajawal', sans-serif; }

/* Sidebar */
#Sidebar { background-color: #0a3d0e; border-left: none; min-width: 250px; }
#Sidebar QLabel { color: #ffffff; }
#Sidebar QPushButton { 
    background-color: transparent; 
    border: none; 
    border-radius: 8px; 
    padding: 12px; 
    text-align: right; 
    font-size: 14px; 
    font-weight: 500; 
    color: #e0e0e0; 
}
#Sidebar QPushButton:hover { background-color: #1b5e20; color: white; }
#Sidebar QPushButton#NavBtnActive { background-color: #2e7d32; color: white; font-weight: bold; }

/* Content Area */
#ContentFrame { background-color: #f7f9fc; }
QLabel#PageTitle { color: #1b5e20; font-size: 28px; font-weight: bold; }
QLabel#SectionTitle { color: #1b5e20; font-size: 20px; font-weight: bold; }

/* Cards */
QFrame#StatCard { background-color: #ffffff; border-radius: 15px; border: 1px solid #e2e8f0; }
QLabel#StatTitle { color: #64748b; font-size: 14px; }
QLabel#StatValue { font-size: 28px; font-weight: bold; }

/* Tables */
QTableWidget { 
    background-color: #ffffff; 
    border: 1px solid #e2e8f0; 
    border-radius: 10px; 
    gridline-color: #f1f5f9; 
    font-size: 13px; 
    selection-background-color: #f0fdf4; 
    selection-color: #1b5e20; 
    color: #1e293b; 
}
QTableWidget QTableCornerButton::section { background-color: #f8fafc; }
QHeaderView::section { 
    background-color: #f8fafc; 
    color: #1b5e20; 
    padding: 10px; 
    border: none; 
    font-weight: bold; 
    border-bottom: 2px solid #f1f5f9; 
}

/* Inputs */
QLineEdit, QComboBox { 
    background-color: #ffffff; 
    border: 1px solid #e2e8f0; 
    border-radius: 8px; 
    padding: 10px; 
    color: #1e293b; 
}
QLineEdit:focus { border: 1px solid #2e7d32; }

QPushButton { 
    background-color: #d1fae5;
    color: #065f46;
    border: none;
    border-radius: 8px;
    padding: 10px;
}
QPushButton:hover { background-color: #a7f3d0; }

/* Buttons */
QPushButton#PrimaryBtn { background-color: #2e7d32; color: white; border-radius: 8px; padding: 10px; font-weight: bold; }
QPushButton#PrimaryBtn:hover { background-color: #1b5e20; }

QPushButton#DangerBtn { background-color: #ef4444; color: white; border-radius: 8px; padding: 10px; }
QPushButton#DangerBtn:hover { background-color: #dc2626; }

QMenu { background-color: #ffffff; border: 1px solid #e2e8f0; color: #1e293b; }
QMenu::item:selected { background-color: #f1f5f9; color: #1b5e20; }
QDialog { background-color: #ffffff; }
QScrollArea { background-color: transparent; border: none; }
QScrollArea > QWidget > QWidget { background-color: transparent; }
QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 10px; background-color: white; margin-top: -1px; }
QTabBar::tab { background-color: #f1f5f9; padding: 12px 25px; border-top-left-radius: 10px; border-top-right-radius: 10px; margin-right: 4px; color: #64748b; font-weight: 500; }
QTabBar::tab:selected { background-color: white; color: #1b5e20; font-weight: bold; border: 1px solid #e2e8f0; border-bottom: 2px solid white; }
QScrollBar:vertical { border: none; background: #f1f5f9; width: 10px; margin: 0px; }
QScrollBar::handle:vertical { background: #cbd5e1; min-height: 20px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { border: none; background: #f1f5f9; height: 10px; margin: 0px; }
QScrollBar::handle:horizontal { background: #cbd5e1; min-width: 20px; border-radius: 5px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
"""

# Global Styling - Hakbah Premium Dark Theme
HAKBAH_DARK = """
QMainWindow { background-color: #0f172a; }
QWidget { color: #f1f5f9; font-family: 'Tajawal', sans-serif; }

/* Sidebar */
#Sidebar { background-color: #052109; border-left: none; min-width: 250px; }
#Sidebar QLabel { color: #ffffff; }
#Sidebar QPushButton { 
    background-color: transparent; 
    border: none; 
    border-radius: 8px; 
    padding: 12px; 
    text-align: right; 
    font-size: 14px; 
    font-weight: 500; 
    color: #94a3b8; 
}
#Sidebar QPushButton:hover { background-color: #1b5e20; color: white; }
#Sidebar QPushButton#NavBtnActive { background-color: #2e7d32; color: white; font-weight: bold; }

/* Content Area */
#ContentFrame { background-color: #0f172a; }
QLabel#PageTitle { color: #4ade80; font-size: 28px; font-weight: bold; }
QLabel#SectionTitle { color: #4ade80; font-size: 20px; font-weight: bold; }

/* Cards */
QFrame#StatCard { background-color: #1e293b; border-radius: 15px; border: 1px solid #334155; }
QLabel#StatTitle { color: #94a3b8; font-size: 14px; }
QLabel#StatValue { color: #ffffff; font-size: 28px; font-weight: bold; }

/* Tables */
QTableWidget { 
    background-color: #1e293b; 
    border: 1px solid #334155; 
    border-radius: 10px; 
    gridline-color: #334155; 
    font-size: 13px; 
    selection-background-color: #1b5e20; 
    selection-color: white; 
    color: #f1f5f9; 
}
QTableWidget QTableCornerButton::section { background-color: #1e293b; }
QHeaderView::section { 
    background-color: #0f172a; 
    color: #4ade80; 
    padding: 10px; 
    border: none; 
    font-weight: bold; 
    border-bottom: 2px solid #334155; 
}

/* Inputs */
QLineEdit, QComboBox { 
    background-color: #1e293b; 
    border: 1px solid #334155; 
    border-radius: 8px; 
    padding: 10px; 
    color: #ffffff; 
}
QLineEdit:focus { border: 1px solid #4ade80; }

QPushButton { 
    background-color: #1e293b;
    color: #f1f5f9;
    border: none;
    border-radius: 8px;
    padding: 10px;
}
QPushButton:hover { background-color: #334155; }

/* Buttons */
QPushButton#PrimaryBtn { background-color: #2e7d32; color: white; border-radius: 8px; padding: 10px; font-weight: bold; }
QPushButton#PrimaryBtn:hover { background-color: #1b5e20; }

QPushButton#DangerBtn { background-color: #ef4444; color: white; border-radius: 8px; padding: 10px; }
QPushButton#DangerBtn:hover { background-color: #dc2626; }

QMenu { background-color: #1e293b; border: 1px solid #334155; color: #ffffff; }
QMenu::item:selected { background-color: #2e7d32; color: white; }
QDialog { background-color: #111827; }
QScrollArea { background-color: transparent; border: none; }
QScrollArea > QWidget > QWidget { background-color: transparent; }
QTabWidget::pane { border: 1px solid #334155; border-radius: 10px; background-color: #1e293b; margin-top: -1px; }
QTabBar::tab { background-color: #0f172a; padding: 12px 25px; border-top-left-radius: 10px; border-top-right-radius: 10px; margin-right: 4px; color: #94a3b8; font-weight: 500; }
QTabBar::tab:selected { background-color: #1e293b; color: #4ade80; font-weight: bold; border: 1px solid #334155; border-bottom: 2px solid #1e293b; }
QScrollBar:vertical { border: none; background: #0f172a; width: 10px; margin: 0px; }
QScrollBar::handle:vertical { background: #334155; min-height: 20px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #475569; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { border: none; background: #0f172a; height: 10px; margin: 0px; }
QScrollBar::handle:horizontal { background: #334155; min-width: 20px; border-radius: 5px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
"""

