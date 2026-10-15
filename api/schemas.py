import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

# --- Subscriber Schemas ---
class SubscriberBase(BaseModel):
    name: str
    phone: str
    category: Optional[str] = None
    national_id: Optional[str] = None
    address: Optional[str] = None

class SubscriberCreate(SubscriberBase):
    pass

class SubscriberUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    category: Optional[str] = None
    national_id: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    exclusion_reason: Optional[str] = None

class SubscriberOut(SubscriberBase):
    id: int
    status: Optional[str] = "pending"
    subscriber_number: Optional[str] = None
    created_at: Optional[datetime.datetime] = None
    fin_status: Optional[str] = None
    paid_count: Optional[int] = 0
    total_paid: Optional[float] = 0.0

    model_config = ConfigDict(from_attributes=True)

class AccountStatementPayment(BaseModel):
    id: int
    cycle_number: int
    installment_number: int
    amount: float
    due_date: Optional[str] = None
    paid_date: Optional[str] = None
    is_paid: bool
    note: Optional[str] = None

class AccountStatementOut(BaseModel):
    subscriber: SubscriberOut
    total_paid: float
    total_remaining: float
    paid_count: int
    total_count: int
    payments: List[AccountStatementPayment]

# --- Payment Schemas ---
class PaymentOut(BaseModel):
    id: int
    subscriber_id: int
    cycle_number: int
    installment_number: int
    amount: float
    due_date: Optional[datetime.datetime] = None
    paid_date: Optional[datetime.datetime] = None
    is_paid: bool
    note: Optional[str] = None
    staff_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class QuickPayRequest(BaseModel):
    payment_id: int
    staff_id: Optional[int] = None
    note: Optional[str] = None

# --- Category Schemas ---
class CategoryOut(BaseModel):
    id: int
    name: str
    amount: float
    max_cycles: Optional[int] = 1
    max_installments: Optional[int] = 12
    start_date: Optional[datetime.datetime] = None
    end_date: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CategoryUpdate(BaseModel):
    amount: Optional[float] = None
    max_cycles: Optional[int] = None
    max_installments: Optional[int] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None

# --- Stats Schemas ---
class DashboardStatsOut(BaseModel):
    total_subscribers: int
    category_counts: Dict[str, int]
    registration_open: bool

class CapitalCategoryItem(BaseModel):
    name: str
    amount: float
    sub_count: int
    expected: float
    collected: float
    remaining: float
    ratio: float

class CapitalStatsOut(BaseModel):
    total_expected: float
    total_collected: float
    total_winner_payouts: float
    total_expenses: float
    total_arrears: float
    net_cash: float
    categories_breakdown: List[CapitalCategoryItem]

# --- Draw Schemas ---
class DrawCategoryStatItem(BaseModel):
    category_name: str
    active_cycle: int
    total_cycles: int
    selected_cycle: Any
    completed_cycle_count: int
    incentive_count: int

class DrawStatsSummaryOut(BaseModel):
    categories: List[DrawCategoryStatItem]

class QualifiedDrawSubscriber(BaseModel):
    sub_id: int
    name: str
    phone: str
    category: str
    number: str
    draw_type: str
    cycle: Any
    pay_ratio: float
    total_paid: float
    total_expected: float
    fin_status: str
    is_qualified: bool

class PerformDrawRequest(BaseModel):
    draw_type: str
    category: Optional[str] = None
    cycle: Optional[Any] = "auto"
    period: Optional[int] = 1

class WinnerOut(BaseModel):
    id: int
    draw_name: str
    subscriber_number: str
    subscriber_name: str
    phone: str
    category: str
    draw_date: datetime.datetime
    payout_amount: Optional[float] = 0.0
    is_received: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)

# --- Admin Notification Schemas ---
class NotificationOut(BaseModel):
    id: int
    message: str
    type: Optional[str] = "info"
    is_read: bool
    created_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)
