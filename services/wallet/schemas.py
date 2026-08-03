from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, field_validator


class WalletResponse(BaseModel):
    id: str
    user_id: str
    balance: Decimal
    currency: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class TopUpRequest(BaseModel):
    amount: Decimal
    stripe_payment_intent_id: str  # Stripe PaymentIntent ID already confirmed by Stripe.js
    idempotency_key: str

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Top-up amount must be positive")
        if v > Decimal("10000"):
            raise ValueError("Top-up amount cannot exceed $10,000")
        return v


class CreatePaymentIntentRequest(BaseModel):
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive")
        if v > Decimal("10000"):
            raise ValueError("Amount cannot exceed $10,000")
        return v


class DebitRequest(BaseModel):
    amount: Decimal
    idempotency_key: str
    description: str | None = None
    related_booking_id: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Debit amount must be positive")
        return v


class TransactionResponse(BaseModel):
    id: str
    wallet_id: str
    amount: Decimal
    transaction_type: str
    idempotency_key: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    next_cursor: str | None
    total: int
