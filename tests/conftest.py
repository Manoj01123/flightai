import pytest
import pytest_asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


@pytest.fixture
def user_id():
    return str(uuid.uuid4())


@pytest.fixture
def wallet_id():
    return str(uuid.uuid4())


def make_wallet(user_id: str, wallet_id: str, balance: Decimal = Decimal("100.00")):
    from services.wallet.models import Wallet
    w = Wallet()
    w.id = wallet_id
    w.user_id = user_id
    w.balance = balance
    w.currency = "USD"
    return w
