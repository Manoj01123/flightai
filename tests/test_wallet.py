"""Unit tests for wallet debit / topup logic (Week 2)."""
import pytest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_wallet(user_id: str, balance: Decimal = Decimal("100.00")):
    from services.wallet.models import Wallet
    w = Wallet()
    w.id = str(uuid.uuid4())
    w.user_id = user_id
    w.balance = balance
    w.currency = "USD"
    return w


def _async_result(value):
    m = MagicMock()
    m.scalar_one_or_none = MagicMock(return_value=value)
    m.scalar_one = MagicMock(return_value=value)
    return m


# ── get_or_create_wallet ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_or_create_wallet_creates_when_missing():
    from services.wallet.service import get_or_create_wallet

    user_id = str(uuid.uuid4())
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_async_result(None))

    wallet = await get_or_create_wallet(user_id, db)

    assert wallet.user_id == user_id
    assert wallet.balance == Decimal("0.00")
    db.add.assert_called_once()
    db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_wallet_returns_existing():
    from services.wallet.service import get_or_create_wallet

    user_id = str(uuid.uuid4())
    existing = _make_wallet(user_id, Decimal("50.00"))
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_async_result(existing))

    wallet = await get_or_create_wallet(user_id, db)

    assert wallet is existing
    db.add.assert_not_called()


# ── topup_wallet ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_topup_wallet_credits_balance():
    from services.wallet.service import topup_wallet

    user_id = str(uuid.uuid4())
    wallet = _make_wallet(user_id, Decimal("100.00"))
    idempotency_key = str(uuid.uuid4())

    db = AsyncMock()
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _async_result(None)       # idempotency check — no existing txn
        return _async_result(wallet)         # get_or_create_wallet + lock

    db.execute = AsyncMock(side_effect=side_effect)

    result_wallet, txn = await topup_wallet(
        user_id=user_id,
        amount=Decimal("50.00"),
        idempotency_key=idempotency_key,
        stripe_payment_intent_id="pi_test_123",
        db=db,
    )

    assert result_wallet.balance == Decimal("150.00")
    db.add.assert_called()


@pytest.mark.asyncio
async def test_topup_wallet_raises_on_duplicate_idempotency_key():
    from services.wallet.service import topup_wallet
    from services.shared.exceptions import ConflictError

    user_id = str(uuid.uuid4())
    idempotency_key = str(uuid.uuid4())

    existing_txn = MagicMock()
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_async_result(existing_txn))

    with pytest.raises(ConflictError):
        await topup_wallet(
            user_id=user_id,
            amount=Decimal("50.00"),
            idempotency_key=idempotency_key,
            stripe_payment_intent_id="pi_test_456",
            db=db,
        )


# ── debit_wallet ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_debit_wallet_deducts_amount_plus_fee():
    from services.wallet.service import debit_wallet, AGENT_FEE

    user_id = str(uuid.uuid4())
    wallet = _make_wallet(user_id, Decimal("200.00"))
    idempotency_key = str(uuid.uuid4())

    db = AsyncMock()
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _async_result(None)    # idempotency check — no existing txn
        if call_count["n"] == 2:
            return _async_result(wallet)  # get_or_create_wallet
        return _async_result(wallet)      # SELECT FOR UPDATE lock

    db.execute = AsyncMock(side_effect=side_effect)

    result_wallet, txn = await debit_wallet(
        user_id=user_id,
        amount=Decimal("100.00"),
        idempotency_key=idempotency_key,
        description="Test booking debit",
        related_booking_id=None,
        db=db,
    )

    expected_balance = Decimal("200.00") - Decimal("100.00") - AGENT_FEE
    assert result_wallet.balance == expected_balance
    assert db.add.call_count == 2   # one debit txn + one fee txn


@pytest.mark.asyncio
async def test_debit_wallet_raises_insufficient_funds():
    from services.wallet.service import debit_wallet
    from services.shared.exceptions import InsufficientFundsError

    user_id = str(uuid.uuid4())
    wallet = _make_wallet(user_id, Decimal("10.00"))
    idempotency_key = str(uuid.uuid4())

    db = AsyncMock()
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _async_result(None)
        if call_count["n"] == 2:
            return _async_result(wallet)
        return _async_result(wallet)

    db.execute = AsyncMock(side_effect=side_effect)

    with pytest.raises(InsufficientFundsError):
        await debit_wallet(
            user_id=user_id,
            amount=Decimal("100.00"),
            idempotency_key=idempotency_key,
            description="Should fail",
            related_booking_id=None,
            db=db,
        )


@pytest.mark.asyncio
async def test_debit_wallet_raises_on_duplicate_idempotency_key():
    from services.wallet.service import debit_wallet
    from services.shared.exceptions import ConflictError

    user_id = str(uuid.uuid4())
    idempotency_key = str(uuid.uuid4())
    existing_txn = MagicMock()

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_async_result(existing_txn))

    with pytest.raises(ConflictError):
        await debit_wallet(
            user_id=user_id,
            amount=Decimal("50.00"),
            idempotency_key=idempotency_key,
            description="Duplicate",
            related_booking_id=None,
            db=db,
        )


@pytest.mark.asyncio
async def test_debit_wallet_exact_balance_minus_fee_passes():
    """Balance exactly equal to amount + fee should succeed."""
    from services.wallet.service import debit_wallet, AGENT_FEE

    user_id = str(uuid.uuid4())
    amount = Decimal("95.00")
    exact_balance = amount + AGENT_FEE   # = 100.00
    wallet = _make_wallet(user_id, exact_balance)
    idempotency_key = str(uuid.uuid4())

    db = AsyncMock()
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _async_result(None)
        if call_count["n"] == 2:
            return _async_result(wallet)
        return _async_result(wallet)

    db.execute = AsyncMock(side_effect=side_effect)

    result_wallet, _ = await debit_wallet(
        user_id=user_id,
        amount=amount,
        idempotency_key=idempotency_key,
        description="Exact balance test",
        related_booking_id=None,
        db=db,
    )

    assert result_wallet.balance == Decimal("0.00")


@pytest.mark.asyncio
async def test_agent_fee_recorded_separately():
    """Two wallet_transaction rows should be created: debit + fee."""
    from services.wallet.service import debit_wallet
    from services.wallet.models import WalletTransaction, TransactionType

    user_id = str(uuid.uuid4())
    wallet = _make_wallet(user_id, Decimal("500.00"))
    idempotency_key = str(uuid.uuid4())

    db = AsyncMock()
    added = []
    db.add.side_effect = lambda obj: added.append(obj)

    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _async_result(None)
        if call_count["n"] == 2:
            return _async_result(wallet)
        return _async_result(wallet)

    db.execute = AsyncMock(side_effect=side_effect)

    await debit_wallet(
        user_id=user_id,
        amount=Decimal("100.00"),
        idempotency_key=idempotency_key,
        description="booking",
        related_booking_id="booking-123",
        db=db,
    )

    txn_types = [t.transaction_type for t in added]
    assert TransactionType.DEBIT in txn_types
    assert TransactionType.FEE in txn_types

    fee_txns = [t for t in added if t.transaction_type == TransactionType.FEE]
    assert fee_txns[0].idempotency_key == f"{idempotency_key}:fee"
