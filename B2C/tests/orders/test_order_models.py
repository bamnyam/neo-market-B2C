import uuid

import pytest
from django.db import IntegrityError, transaction

from app.buyers.models import Buyer
from app.orders.models import Order, OrderStatus


@pytest.fixture
def buyer():
    return Buyer.objects.create_user(
        email=f"{uuid.uuid4()}@example.com",
        password="strong-password",
        first_name="Buyer",
    )


@pytest.mark.django_db
def test_order_idempotency_key_is_unique(buyer):
    idempotency_key = uuid.uuid4()
    Order.objects.create(
        buyer=buyer,
        status=OrderStatus.PAID,
        idempotency_key=idempotency_key,
        total_amount=1000,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.create(
            buyer=buyer,
            status=OrderStatus.PAID,
            idempotency_key=idempotency_key,
            total_amount=1000,
        )
