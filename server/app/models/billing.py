"""Pydantic schemas for billing endpoints."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class CreditTransactionModel(BaseModel):
    """A billing transaction record.

    All amounts are in cents (e.g., 100 = $1.00).
    """

    id: int
    amount_cents: int  # Positive for purchases, negative for debits
    transaction_type: str  # 'purchase', 'debit', 'refund', 'adjustment', 'hold', 'hold_reversal'
    status: str  # 'pending', 'completed', 'refunded', 'failed'
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    stripe_session_id: Optional[str] = None
    created_at: str


class BillingWalletResponse(BaseModel):
    """User's wallet balance and transaction history.

    Balance is in cents (e.g., 1000 = $10.00).
    """

    balance_cents: int
    transactions: List[CreditTransactionModel]
    total_count: int = 0


class FundingOptionModel(BaseModel):
    """A funding option (Stripe price) that users can purchase.

    With the new 1:1 model, paying $X adds $X to the wallet.
    """

    price_id: str
    amount_cents: int  # Amount that will be added to wallet (equals Stripe amount)
    currency: str
    unit_amount: int  # Stripe unit amount in cents
    nickname: str


class FundingOptionListResponse(BaseModel):
    """List of available funding options."""

    options: List[FundingOptionModel]


class CheckoutSessionCreateRequest(BaseModel):
    price_id: str
    success_url: HttpUrl
    cancel_url: HttpUrl


class CheckoutSessionCreateResponse(BaseModel):
    checkout_url: HttpUrl


class InsufficientBalanceErrorDetail(BaseModel):
    """Details of an insufficient balance error.

    All amounts are in cents (e.g., 500 = $5.00).
    """

    message: str = Field(..., description="Human-readable error message")
    required_cents: int = Field(..., description="Minimum balance required for the action")
    available_cents: int = Field(..., description="User's current balance")
    action: str = Field(..., description="The action that was attempted")


class InsufficientBalanceError(BaseModel):
    """Error response when user has insufficient balance.

    Returned with HTTP 402 Payment Required.
    Matches FastAPI's HTTPException format with a 'detail' field.
    """

    detail: InsufficientBalanceErrorDetail
