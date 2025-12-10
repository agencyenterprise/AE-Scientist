'"""Pydantic schemas for billing endpoints."""'

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class CreditTransactionModel(BaseModel):
    id: int
    amount: int
    transaction_type: str
    status: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    stripe_session_id: Optional[str] = None
    created_at: str


class BillingWalletResponse(BaseModel):
    balance: int
    transactions: List[CreditTransactionModel]


class CreditPackModel(BaseModel):
    price_id: str
    credits: int
    currency: str
    unit_amount: int
    nickname: str


class CreditPackListResponse(BaseModel):
    packs: List[CreditPackModel]


class CheckoutSessionCreateRequest(BaseModel):
    price_id: str
    success_url: HttpUrl
    cancel_url: HttpUrl


class CheckoutSessionCreateResponse(BaseModel):
    checkout_url: HttpUrl
