from decimal import Decimal
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..shared.exceptions import NotFoundError, InsufficientFundsError, ConflictError
from ..shared.settings import settings
from .models import Wallet, WalletTransaction, TransactionType


AGENT_FEE = Decimal("5.00")
LOW_BALANCE_THRESHOLD = Decimal("50.00")


async def get_or_create_wallet(user_id: str, db: AsyncSession) -> Wallet:
    result = await db.execute(select(Wallet).where(Wallet.user_id == user_id))
    wallet = result.scalar_one_or_none()
    if wallet is None:
        wallet = Wallet(id=str(uuid.uuid4()), user_id=user_id)
        db.add(wallet)
        await db.flush()
    return wallet


async def topup_wallet(
    user_id: str,
    amount: Decimal,
    idempotency_key: str,
    stripe_payment_intent_id: str,
    db: AsyncSession,
) -> tuple[Wallet, WalletTransaction]:
    # Idempotency check
    existing = await db.execute(
        select(WalletTransaction).where(WalletTransaction.idempotency_key == idempotency_key)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Transaction with idempotency key {idempotency_key} already exists")

    wallet = await get_or_create_wallet(user_id, db)

    # Row-level lock
    await db.execute(
        select(Wallet).where(Wallet.id == wallet.id).with_for_update()
    )

    wallet.balance += amount
    txn = WalletTransaction(
        wallet_id=wallet.id,
        amount=amount,
        transaction_type=TransactionType.TOPUP,
        idempotency_key=idempotency_key,
        stripe_payment_intent_id=stripe_payment_intent_id,
        description=f"Wallet top-up ${amount}",
    )
    db.add(txn)
    await db.flush()
    return wallet, txn


async def debit_wallet(
    user_id: str,
    amount: Decimal,
    idempotency_key: str,
    description: str,
    related_booking_id: str | None,
    db: AsyncSession,
) -> tuple[Wallet, WalletTransaction]:
    existing = await db.execute(
        select(WalletTransaction).where(WalletTransaction.idempotency_key == idempotency_key)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Transaction with idempotency key {idempotency_key} already exists")

    wallet = await get_or_create_wallet(user_id, db)

    # Row-level lock
    locked = await db.execute(
        select(Wallet).where(Wallet.id == wallet.id).with_for_update()
    )
    wallet = locked.scalar_one()

    total_debit = amount + AGENT_FEE
    if wallet.balance < total_debit:
        raise InsufficientFundsError(
            f"Insufficient balance. Required: ${total_debit}, Available: ${wallet.balance}"
        )

    wallet.balance -= total_debit

    txn = WalletTransaction(
        wallet_id=wallet.id,
        amount=amount,
        transaction_type=TransactionType.DEBIT,
        idempotency_key=idempotency_key,
        description=description,
        related_booking_id=related_booking_id,
    )
    fee_txn = WalletTransaction(
        wallet_id=wallet.id,
        amount=AGENT_FEE,
        transaction_type=TransactionType.FEE,
        idempotency_key=f"{idempotency_key}:fee",
        description="FlightAI agent fee",
        related_booking_id=related_booking_id,
    )
    db.add(txn)
    db.add(fee_txn)
    await db.flush()

    if wallet.balance < LOW_BALANCE_THRESHOLD:
        from ..user.models import User as UserModel
        user_result = await db.execute(select(UserModel).where(UserModel.id == user_id))
        user_obj = user_result.scalar_one_or_none()
        _publish_wallet_low(
            user_id=user_id,
            balance=str(wallet.balance),
            phone=user_obj.phone if user_obj and user_obj.sms_notifications else None,
            email=user_obj.email if user_obj and user_obj.email_notifications else None,
        )

    from ..shared.monitoring import emit_wallet_balance_metric
    emit_wallet_balance_metric(user_id=user_id, balance=float(wallet.balance))

    return wallet, txn


def _publish_wallet_low(user_id: str, balance: str, phone: str | None, email: str | None):
    import json
    from google.cloud import pubsub_v1
    from ..shared.settings import settings

    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(settings.gcp_project_id, settings.pubsub_topic_wallet_low)
        publisher.publish(topic_path, data=json.dumps({
            "user_id": user_id,
            "balance": balance,
            "phone": phone,
            "email": email,
        }).encode())
    except Exception:
        pass  # non-critical — don't fail a booking over a notification
