import pytest
from django.db import IntegrityError, transaction

from app.buyers.models import Buyer


@pytest.mark.django_db
def test_buyer_create_user_normalizes_email_and_hashes_password():
    buyer = Buyer.objects.create_user(
        email="BUYER@Example.COM",
        password="strong-password",
        first_name="Buyer",
    )

    assert buyer.email == "BUYER@example.com"
    assert buyer.check_password("strong-password")
    assert buyer.is_active is True
    assert buyer.deleted is False


@pytest.mark.django_db
def test_buyer_email_is_unique():
    Buyer.objects.create_user(
        email="buyer@example.com",
        password="strong-password",
        first_name="Buyer",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Buyer.objects.create_user(
            email="buyer@example.com",
            password="another-password",
            first_name="Other",
        )
