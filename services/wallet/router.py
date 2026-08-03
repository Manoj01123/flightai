from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..shared.database import get_db
from ..user.dependencies import get_current_user
from ..user.models import User
from .schemas import WalletResponse, TopUpRequest, CreatePaymentIntentRequest, TransactionListResponse, TransactionResponse
from .service import get_or_create_wallet, topup_wallet
from .models import WalletTransaction
from sqlalchemy import select, func

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletResponse)
async def get_wallet(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wallet = await get_or_create_wallet(current_user.id, db)
    return WalletResponse.model_validate(wallet)


@router.post("/topup", response_model=WalletResponse, status_code=201)
async def topup(
    body: TopUpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Credit the wallet after Stripe.js has already confirmed the PaymentIntent.
    The frontend calls /create-payment-intent, confirms with stripe.js, then
    calls this endpoint with the resulting PaymentIntent ID.
    """
    from ..shared.settings import settings
    import stripe
    from fastapi import HTTPException

    stripe.api_key = settings.stripe_secret_key

    try:
        intent = stripe.PaymentIntent.retrieve(body.stripe_payment_intent_id)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message}")

    if intent.status != "succeeded":
        raise HTTPException(status_code=402, detail=f"Payment not completed: {intent.status}")

    # Security: verify amount matches and belongs to this user
    expected_cents = int(body.amount * 100)
    if intent.amount != expected_cents:
        raise HTTPException(status_code=400, detail="Amount mismatch between request and Stripe payment")

    if intent.metadata.get("user_id") and intent.metadata["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="PaymentIntent does not belong to this user")

    wallet, _ = await topup_wallet(
        user_id=current_user.id,
        amount=body.amount,
        idempotency_key=body.idempotency_key,
        stripe_payment_intent_id=intent.id,
        db=db,
    )
    return WalletResponse.model_validate(wallet)


@router.post("/create-payment-intent")
async def create_payment_intent(
    body: CreatePaymentIntentRequest,
    current_user: User = Depends(get_current_user),
):
    from ..shared.settings import settings
    import stripe
    from fastapi import HTTPException

    stripe.api_key = settings.stripe_secret_key
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(body.amount * 100),
            currency="usd",
            metadata={"user_id": current_user.id},
        )
        return {"client_secret": intent.client_secret}
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e.user_message))


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    limit: int = 20,
    cursor: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from .service import get_or_create_wallet
    wallet = await get_or_create_wallet(current_user.id, db)

    query = (
        select(WalletTransaction)
        .where(WalletTransaction.wallet_id == wallet.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(limit + 1)
    )
    if cursor:
        query = query.where(WalletTransaction.created_at < cursor)

    result = await db.execute(query)
    txns = result.scalars().all()

    next_cursor = None
    if len(txns) > limit:
        txns = txns[:limit]
        next_cursor = str(txns[-1].created_at)

    count_result = await db.execute(
        select(func.count()).where(WalletTransaction.wallet_id == wallet.id)
    )
    total = count_result.scalar_one()

    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in txns],
        next_cursor=next_cursor,
        total=total,
    )
