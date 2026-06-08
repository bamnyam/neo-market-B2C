import uuid

import pytest
from django.db import IntegrityError, transaction

from app.buyers.models import Buyer
from app.carts.models import CartItem


@pytest.fixture
def buyer():
    return Buyer.objects.create_user(
        email=f"{uuid.uuid4()}@example.com",
        password="strong-password",
        first_name="Buyer",
    )


@pytest.mark.django_db
def test_cart_item_requires_exactly_one_identity(buyer):
    sku_id = uuid.uuid4()

    with pytest.raises(IntegrityError), transaction.atomic():
        CartItem.objects.create(sku_id=sku_id, quantity=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        CartItem.objects.create(
            user=buyer,
            session_id=uuid.uuid4(),
            sku_id=sku_id,
            quantity=1,
        )


@pytest.mark.django_db
def test_cart_item_is_unique_per_user_and_sku(buyer):
    sku_id = uuid.uuid4()
    CartItem.objects.create(user=buyer, sku_id=sku_id, quantity=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        CartItem.objects.create(user=buyer, sku_id=sku_id, quantity=2)


@pytest.mark.django_db
def test_cart_item_is_unique_per_session_and_sku():
    session_id = uuid.uuid4()
    sku_id = uuid.uuid4()
    CartItem.objects.create(session_id=session_id, sku_id=sku_id, quantity=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        CartItem.objects.create(session_id=session_id, sku_id=sku_id, quantity=2)
