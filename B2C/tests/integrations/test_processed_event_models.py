import uuid

import pytest
from django.db import IntegrityError, transaction

from app.integrations.models import ProcessedEvent, SenderService


@pytest.mark.django_db
def test_processed_event_is_unique_per_sender_and_idempotency_key():
    idempotency_key = uuid.uuid4()
    ProcessedEvent.objects.create(
        sender_service=SenderService.B2B,
        idempotency_key=idempotency_key,
        response_cached={"accepted": True},
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProcessedEvent.objects.create(
            sender_service=SenderService.B2B,
            idempotency_key=idempotency_key,
            response_cached={"accepted": True},
        )

    ProcessedEvent.objects.create(
        sender_service=SenderService.MODERATION,
        idempotency_key=idempotency_key,
        response_cached={"accepted": True},
    )
