import ast

mixins_methods = [
    'init_dashboard_page', 'start_web_server', '_on_server_link_found', '_on_server_error', 'copy_link', 'toggle_reg', 'refresh_stats',
    'init_subscribers_page', 'load_subscribers', 'create_sub_cards_view', 'create_subscriber_card', 'show_subscriber_card_context_menu', 'edit_subscriber', 'delete_subscriber', 'add_new_subscriber', 'open_account_details', 'open_batch_payment', 'show_sub_context_menu', 'export_subscribers_excel', 'export_subscribers_pdf',
    'init_settings_page', 'refresh_cat_list', 'refresh_cat_table', 'refresh_numbers_list', 'add_category', 'edit_category', 'delete_category', 'add_numbers', 'delete_number',
    'init_capital_page', 'show_capital_management', 'sync_unpaid_installments', 'refresh_capital_stats', 'refresh_capital_categories', 'refresh_capital_defaulters', 'quick_pay_payment', 'refresh_capital_standing', 'export_categories_financial_excel', 'export_defaulters_excel', 'refresh_capital_expenses', 'add_new_expense', 'delete_expense', 'export_expenses_excel',
    'init_reports_page', 'refresh_reports_sub_list', 'generate_subscriber_report', 'generate_winners_report', 'generate_categories_report', 'generate_custom_report', 'generate_overall_financial_summary_report', 'generate_subscriber_contact_list_report', 'generate_expense_summary_report', 'upload_new_report', 'refresh_uploaded_reports', 'open_uploaded_file', 'show_upload_context_menu', 'delete_uploaded_file',
    'show_draw_management', 'init_draw_page', 'refresh_draw_stats', 'load_recent_winners', 'show_winner_context_menu', 'delete_winner', 'perform_draw',
    'init_cycles_page', 'refresh_cycles_cat_list', 'load_category_cycle_settings', 'update_auto_end_date', 'save_cycle_settings', 'generate_cycle_schedule',
    'init_messaging_page', 'load_messaging_settings', 'save_messaging_settings', 'send_broadcast'
]

with open('admin_app_backup_full.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    source = ''.join(lines)

tree = ast.parse(source)
app_class = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AdminApp'][0]

remain_methods_code = []
for n in app_class.body:
    if isinstance(n, ast.FunctionDef) and n.name not in mixins_methods:
        start, end = n.lineno, n.end_lineno
        remain_methods_code.append(''.join(lines[start-1:end]))

new_header = ''.join(lines[:29]) + '''
# --- Imported GUI Modules ---
from gui.styles import HAKBAH_LIGHT, HAKBAH_DARK
from gui.utils import reshape_text, ServerWorker
from gui.dialogs import (
    ModernDialog, DrawAnimationDialog, SubscriberEditDialog, CategoryEditDialog,
    PaymentDialog, AddSubscriberDialog, BatchPaymentDialog, AccountDetailsDialog
)
from gui.pages.dashboard import DashboardMixin
from gui.pages.subscribers import SubscribersMixin
from gui.pages.settings import SettingsMixin
from gui.pages.capital import CapitalMixin
from gui.pages.reports import ReportsMixin
from gui.pages.draw import DrawMixin
from gui.pages.cycles import CyclesMixin
from gui.pages.messaging import MessagingMixin

class AdminApp(QMainWindow, DashboardMixin, SubscribersMixin, SettingsMixin, CapitalMixin, ReportsMixin, DrawMixin, CyclesMixin, MessagingMixin):
'''

new_content = new_header + ''.join(remain_methods_code) + '\nif __name__ == "__main__":\n    app = QApplication(sys.argv)\n    app.setStyle("Fusion")\n    window = AdminApp()\n    window.show()\n    sys.exit(app.exec_())\n'

with open('admin_app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
