import os
import logging
from typing import Any, Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class APIClientError(Exception):
    """استثناء مخصص لأخطاء العميل والاتصال بالخادم"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class HakbahAPIClient:
    """
    عميل HTTP عالي الأداء ومؤمن للتواصل بين تطبيق سطح المكتب وخادم هكبة المليون.
    يعتمد على إعادة استخدام اتصالات HTTP (Connection Pooling) ومفتاح التوثيق الآمن.
    """
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 15):
        # 1. تحديد الرابط ومفتاح API من متغيرات البيئة أو القيم الافتراضية
        self.base_url = (base_url or os.getenv("API_SERVER_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.api_key = api_key or os.getenv("ADMIN_API_KEY") or "hakbah_api_sec_994a3bc1e8204d88e07a216f49b"
        self.timeout = timeout

        # 2. إعداد جلسة اتصالات سريعة مع استراتيجية إعادة المحاولة التلقائية
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "Hakbah-Admin-Desktop/2.0"
        })

        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        kwargs.setdefault("timeout", self.timeout)

        try:
            resp = self.session.request(method, url, **kwargs)
            if resp.status_code == 204:
                return None

            try:
                data = resp.json()
            except Exception:
                data = resp.text

            if not resp.ok:
                err_msg = data.get("detail", str(data)) if isinstance(data, dict) else str(data)
                raise APIClientError(
                    f"خطأ في الطلب ({resp.status_code}): {err_msg}",
                    status_code=resp.status_code,
                    response_data=data
                )
            return data
        except requests.exceptions.ConnectionError as e:
            raise APIClientError(f"تعذر الاتصال بخادم الـ API ({self.base_url}). يرجى التأكد من تشغيل الخادم والاتصال بالإنترنت.", response_data=str(e))
        except requests.exceptions.Timeout:
            raise APIClientError(f"انتهت مهلة انتظار استجابة الخادم ({self.timeout} ثانية).", status_code=408)
        except requests.exceptions.RequestException as e:
            raise APIClientError(f"خطأ أثناء الاتصال بالخادم: {e}", response_data=str(e))

    # --- Dashboard & System Stats ---
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """جلب إحصائيات الصفحة الرئيسية"""
        return self._request("GET", "stats/dashboard")

    def get_visitors_stats(self) -> Dict[str, Any]:
        """جلب إحصائيات الزيارات والمشتركين المتصلين حالياً"""
        return self._request("GET", "stats/visitors")

    def get_notifications(self, unread_only: bool = False, limit: int = 50) -> Dict[str, Any]:
        """جلب إشعارات المشرفين"""
        return self._request("GET", "stats/notifications", params={"unread_only": unread_only, "limit": limit})

    def mark_notification_read(self, notif_id: int) -> Dict[str, Any]:
        """تحديد إشعار كمقروء"""
        return self._request("POST", f"stats/notifications/{notif_id}/read")

    def mark_all_notifications_read(self) -> Dict[str, Any]:
        """تحديد جميع الإشعارات كمقروءة"""
        return self._request("POST", "stats/notifications/read-all")

    def get_categories(self) -> List[Dict[str, Any]]:
        """جلب جميع الفئات"""
        return self._request("GET", "stats/categories")

    def update_category(self, cat_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """تحديث بيانات فئة"""
        return self._request("PUT", f"stats/categories/{cat_id}", json=data)

    # --- Subscribers ---
    def list_subscribers(self, category: Optional[str] = None, status: Optional[str] = None, search: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """جلب قائمة المشتركين مع حساب حالتهم المالية"""
        params = {"skip": skip, "limit": limit}
        if category and category != "الكل":
            params["category"] = category
        if status and status != "الكل":
            params["status"] = status
        if search:
            params["search"] = search
        return self._request("GET", "subscribers", params=params)

    def get_subscriber(self, sub_id: int) -> Dict[str, Any]:
        """جلب تفاصيل مشترك محدد"""
        return self._request("GET", f"subscribers/{sub_id}")

    def get_account_statement(self, sub_id: int) -> Dict[str, Any]:
        """جلب كشف حساب المشترك المالي كاملاً ومفصلاً في طلب واحد"""
        return self._request("GET", f"subscribers/{sub_id}/statement")

    def create_subscriber(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """إضافة مشترك جديد"""
        return self._request("POST", "subscribers", json=data)

    def update_subscriber(self, sub_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """تحديث بيانات مشترك"""
        return self._request("PUT", f"subscribers/{sub_id}", json=data)

    def delete_subscriber(self, sub_id: int) -> None:
        """حذف مشترك وسجلاته"""
        return self._request("DELETE", f"subscribers/{sub_id}")

    # --- Payments ---
    def quick_pay(self, payment_id: int, staff_id: Optional[int] = None, note: Optional[str] = None) -> Dict[str, Any]:
        """سداد سريع لقسط"""
        return self._request("POST", "payments/quick-pay", json={
            "payment_id": payment_id,
            "staff_id": staff_id,
            "note": note
        })

    def batch_pay(self, payment_ids: Optional[List[int]] = None, subscriber_id: Optional[int] = None, 
                  cycle_number: Optional[int] = None, pay_all_overdue: bool = False, 
                  category: Optional[str] = None, staff_id: Optional[int] = None, note: Optional[str] = None) -> Dict[str, Any]:
        """سداد دفعة من الأقساط في طلب واحد"""
        payload = {
            "payment_ids": payment_ids,
            "subscriber_id": subscriber_id,
            "cycle_number": cycle_number,
            "pay_all_overdue": pay_all_overdue,
            "category": category,
            "staff_id": staff_id,
            "note": note
        }
        return self._request("POST", "payments/batch-pay", json=payload)

    def list_defaulters(self, category: Optional[str] = None, search: Optional[str] = None, skip: int = 0, limit: int = 200) -> List[Dict[str, Any]]:
        """جلب كشف المتأخرات"""
        params = {"skip": skip, "limit": limit}
        if category and category != "الكل":
            params["category"] = category
        if search:
            params["search"] = search
        return self._request("GET", "payments/defaulters", params=params)

    # --- Capital & Liquidity ---
    def get_capital_stats(self, category: Optional[str] = None) -> Dict[str, Any]:
        """جلب إحصائيات رأس المال والسيولة وتحليل الفئات المحسوبة على الخادم"""
        params = {}
        if category and category != "الكل":
            params["category"] = category
        return self._request("GET", "capital/stats", params=params)

    def get_subscribers_standing(self, category: Optional[str] = None, search: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """جلب الموقف المالي للمشتركين"""
        params = {"skip": skip, "limit": limit}
        if category and category != "الكل":
            params["category"] = category
        if search:
            params["search"] = search
        return self._request("GET", "capital/standing", params=params)

    # --- Draw & Winners ---
    def get_draw_stats(self) -> Dict[str, Any]:
        """جلب إحصائيات تأهل الفئات للقرعات"""
        return self._request("GET", "draw/stats")

    def get_draw_candidates(self, draw_type: str = "القرعة الاسبوعية", category: Optional[str] = None, cycle: str = "auto") -> List[Dict[str, Any]]:
        """جلب المشتركين المؤهلين للقرعة"""
        params = {"draw_type": draw_type, "cycle": cycle}
        if category and category != "الكل":
            params["category"] = category
        return self._request("GET", "draw/candidates", params=params)

    def get_draw_excluded(self, category: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """جلب المستبعدين من القرعة مع الأسباب"""
        params = {}
        if category and category != "الكل":
            params["category"] = category
        if search:
            params["search"] = search
        return self._request("GET", "draw/excluded", params=params)

    def list_winners(self, draw_type: Optional[str] = None, category: Optional[str] = None, search: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """جلب سجل الفائزين"""
        params = {"skip": skip, "limit": limit}
        if draw_type and draw_type != "الكل":
            params["draw_type"] = draw_type
        if category and category != "الكل":
            params["category"] = category
        if search:
            params["search"] = search
        return self._request("GET", "draw/winners", params=params)

    def update_winner_receipt(self, winner_id: int, is_received: bool, payout_amount: float = 0.0) -> Dict[str, Any]:
        """تحديث حالة استلام مستحقات الفائز"""
        return self._request("PUT", f"draw/winners/{winner_id}/receipt", json={
            "is_received": is_received,
            "payout_amount": payout_amount
        })

# --- Generic PyQt6 Non-Blocking Worker Thread ---
class APIWorker(QThread):
    """
    خيط معالجة خلفي غير حاجب لواجهة المستخدم (Non-blocking QThread).
    يقوم بتنفيذ أي طلب إلى خادم الـ API في الخلفية ثم يرسل النتيجة
    أو الخطأ عبر Qt Signals بأمان تام ودون أي تجميد للواجهة.
    """
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            res = self.func(*self.args, **self.kwargs)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))

# Singleton instance
_client_instance: Optional[HakbahAPIClient] = None

def get_api_client() -> HakbahAPIClient:
    """الحصول على النسخة الموحدة من عميل الـ API"""
    global _client_instance
    if _client_instance is None:
        _client_instance = HakbahAPIClient()
    return _client_instance
