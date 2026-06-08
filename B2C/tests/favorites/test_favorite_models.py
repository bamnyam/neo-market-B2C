import uuid

import pytest
from django.db import IntegrityError, transaction

from app.buyers.models import Buyer
from app.favorites.models import Favorite, ProductSubscription


@pytest.fixture
def buyer():
    return Buyer.objects.create_user(
        email=f"{uuid.uuid4()}@example.com",
        password="strong-password",
        first_name="Buyer",
    )


@pytest.mark.django_db
def test_favorite_is_unique_per_buyer_and_product(buyer):
    product_id = uuid.uuid4()
    Favorite.objects.create(buyer=buyer, product_id=product_id)

    with pytest.raises(IntegrityError), transaction.atomic():
        Favorite.objects.create(buyer=buyer, product_id=product_id)


@pytest.mark.django_db
def test_product_subscription_is_unique_per_buyer_and_product(buyer):
    product_id = uuid.uuid4()
    ProductSubscription.objects.create(
        buyer=buyer,
        product_id=product_id,
        notify_on=["IN_STOCK"],
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProductSubscription.objects.create(
            buyer=buyer,
            product_id=product_id,
            notify_on=["PRICE_DOWN"],
        )
