import uuid

import pytest
from django.db import IntegrityError, transaction

from app.content.models import Collection, CollectionProduct


@pytest.mark.django_db
def test_collection_product_ordering_and_uniqueness():
    collection = Collection.objects.create(title="Hits", priority=1)
    first_product_id = uuid.uuid4()

    first = CollectionProduct.objects.create(
        collection=collection,
        product_id=first_product_id,
        ordering=10,
    )
    second = CollectionProduct.objects.create(
        collection=collection,
        product_id=uuid.uuid4(),
        ordering=20,
    )

    assert list(collection.products.order_by("ordering")) == [first, second]

    with pytest.raises(IntegrityError), transaction.atomic():
        CollectionProduct.objects.create(
            collection=collection,
            product_id=first_product_id,
            ordering=30,
        )
