import uuid

import pytest
from rest_framework.test import APIClient

from app.buyers.models import Address, Buyer, PaymentMethod, PaymentMethodType
from app.carts.models import CartItem
from app.carts.services.b2b_client import normalize_skus
from app.orders.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.orders.services.b2b_client import B2BUnavailableError, ReserveFailedError


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def buyer():
    return Buyer.objects.create_user(
        email=f"{uuid.uuid4()}@example.com",
        password="strong-password",
        first_name="Buyer",
    )


@pytest.fixture
def address(buyer):
    return Address.objects.create(
        buyer=buyer,
        country="Россия",
        region="Свердловская область",
        city="Екатеринбург",
        street="Мира",
        building="19",
        apartment="42",
        postal_code="620000",
        recipient_name="Buyer",
        recipient_phone="+79990000000",
    )


@pytest.fixture
def payment_method(buyer):
    return PaymentMethod.objects.create(
        buyer=buyer,
        type=PaymentMethodType.CARD,
        card_last4="1234",
        card_brand=PaymentMethod.CardBrand.MIR,
    )


def sku_payload(
    sku_id,
    product_id=None,
    price=1000,
    discount=0,
    available_quantity=10,
):
    return {
        str(sku_id): {
            "sku_id": str(sku_id),
            "product_id": str(product_id or uuid.uuid4()),
            "product_title": "Phone",
            "sku_name": "Black",
            "sku_code": "SKU-1",
            "price": price,
            "discount": discount,
            "available_quantity": available_quantity,
            "product_status": "MODERATED",
            "product_deleted": False,
            "image": {"url": "https://cdn.example.test/phone.jpg", "ordering": 0},
        }
    }


def add_cart_item(buyer, sku_id, quantity=1):
    return CartItem.objects.create(user=buyer, sku_id=sku_id, quantity=quantity)


@pytest.mark.django_db
def test_checkout_creates_paid_order_with_fixed_prices(
    api_client,
    buyer,
    address,
    payment_method,
    monkeypatch,
):
    sku_id = uuid.uuid4()
    product_id = uuid.uuid4()
    idempotency_key = uuid.uuid4()
    reserves = []
    add_cart_item(buyer, sku_id, quantity=2)

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.get_skus",
        lambda self, sku_ids: sku_payload(
            sku_id,
            product_id=product_id,
            price=1500,
            discount=200,
        ),
    )
    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.reserve",
        lambda self, idem_key, order_id, items: reserves.append(
            (idem_key, order_id, items)
        )
        or {"reserved": True},
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "address_id": str(address.uuid),
            "payment_method_id": str(payment_method.uuid),
            "comment": "Позвонить за час",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(idempotency_key),
    )

    assert response.status_code == 201
    assert response.data["buyer_id"] == str(buyer.uuid)
    assert response.data["status"] == OrderStatus.PAID
    assert response.data["subtotal"] == 2600
    assert response.data["delivery_cost"] == 0
    assert response.data["total"] == 2600
    assert response.data["address"]["id"] == str(address.uuid)
    assert response.data["address"]["city"] == "Екатеринбург"
    assert response.data["payment_method"]["id"] == str(payment_method.uuid)
    assert response.data["payment_method"]["type"] == PaymentMethodType.CARD
    assert response.data["comment"] == "Позвонить за час"
    assert response.data["cancel_reason"] is None
    assert response.data["paid_at"] is not None
    assert response.data["delivered_at"] is None
    assert response.data["items"][0]["name"] == "Phone Black"
    assert response.data["items"][0]["unit_price"] == 1300
    assert response.data["items"][0]["line_total"] == 2600
    assert reserves[0][0] == idempotency_key
    assert uuid.UUID(str(reserves[0][1])) == uuid.UUID(response.data["id"])

    order = Order.objects.get(idempotency_key=idempotency_key)
    item = OrderItem.objects.get(order=order)
    assert order.status == OrderStatus.PAID
    assert order.paid_at is not None
    assert order.total_amount == 2600
    assert order.address == address
    assert order.payment_method == payment_method
    assert order.comment == "Позвонить за час"
    assert item.name == "Phone Black"
    assert item.product_id == product_id
    assert item.unit_price == 1300
    assert item.line_total == 2600
    assert list(
        OrderStatusHistory.objects.filter(order=order).order_by("id").values_list(
            "status_from",
            "status_to",
        )
    ) == [
        (None, OrderStatus.CREATED),
        (OrderStatus.CREATED, OrderStatus.PAID),
    ]


@pytest.mark.django_db
def test_partial_reserve_failure_returns_409(
    api_client,
    buyer,
    address,
    payment_method,
    monkeypatch,
):
    ok_sku_id = uuid.uuid4()
    failed_sku_id = uuid.uuid4()
    add_cart_item(buyer, ok_sku_id)
    add_cart_item(buyer, failed_sku_id, quantity=2)
    failed_items = [
        {
            "sku_id": str(failed_sku_id),
            "requested": 2,
            "available": 0,
            "reason": "INSUFFICIENT_STOCK",
        }
    ]

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.get_skus",
        lambda self, sku_ids: {
            **sku_payload(ok_sku_id),
            **sku_payload(failed_sku_id, available_quantity=3),
        },
    )

    def reserve_failed(self, idempotency_key, order_id, items):
        raise ReserveFailedError(failed_items)

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.reserve",
        reserve_failed,
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "address_id": str(address.uuid),
            "payment_method_id": str(payment_method.uuid),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )

    assert response.status_code == 409
    assert response.data["code"] == "RESERVE_FAILED"
    assert response.data["failed_items"] == failed_items
    assert Order.objects.count() == 0
    assert OrderItem.objects.count() == 0


@pytest.mark.django_db
def test_idempotency_returns_existing_order(
    api_client,
    buyer,
    address,
    payment_method,
    monkeypatch,
):
    sku_id = uuid.uuid4()
    idempotency_key = uuid.uuid4()
    reserve_calls = []
    add_cart_item(buyer, sku_id)

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.get_skus",
        lambda self, sku_ids: sku_payload(sku_id, price=1000),
    )
    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.reserve",
        lambda self, idem_key, order_id, items: reserve_calls.append(items)
        or {"reserved": True},
    )
    api_client.force_authenticate(user=buyer)
    payload = {
        "address_id": str(address.uuid),
        "payment_method_id": str(payment_method.uuid),
    }

    first_response = api_client.post(
        "/api/v1/orders",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(idempotency_key),
    )
    second_response = api_client.post(
        "/api/v1/orders",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(idempotency_key),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.data["id"] == first_response.data["id"]
    assert Order.objects.count() == 1
    assert OrderItem.objects.count() == 1
    assert len(reserve_calls) == 1


@pytest.mark.django_db
def test_b2b_unavailable_returns_503(
    api_client,
    buyer,
    address,
    payment_method,
    monkeypatch,
):
    add_cart_item(buyer, uuid.uuid4())

    def b2b_unavailable(self, sku_ids):
        raise B2BUnavailableError("B2B service is unavailable")

    monkeypatch.setattr(
        "app.orders.services.b2b_client.B2BOrdersClient.get_skus",
        b2b_unavailable,
    )
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "address_id": str(address.uuid),
            "payment_method_id": str(payment_method.uuid),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )

    assert response.status_code == 503
    assert response.data["code"] == "B2B_UNAVAILABLE"
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_rejects_cart_id(api_client, buyer, address, payment_method):
    add_cart_item(buyer, uuid.uuid4())
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "cart_id": str(uuid.uuid4()),
            "address_id": str(address.uuid),
            "payment_method_id": str(payment_method.uuid),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_REQUEST"
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_requires_idempotency_key_header(
    api_client,
    buyer,
    address,
    payment_method,
):
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "address_id": str(address.uuid),
            "payment_method_id": str(payment_method.uuid),
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_REQUEST"
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_rejects_items_in_body(api_client, buyer, address, payment_method):
    add_cart_item(buyer, uuid.uuid4())
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "items": [{"sku_id": str(uuid.uuid4()), "quantity": 1}],
            "address_id": str(address.uuid),
            "payment_method_id": str(payment_method.uuid),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_REQUEST"
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_rejects_empty_cart(api_client, buyer, address, payment_method):
    api_client.force_authenticate(user=buyer)

    response = api_client.post(
        "/api/v1/orders",
        {
            "address_id": str(address.uuid),
            "payment_method_id": str(payment_method.uuid),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_REQUEST"
    assert Order.objects.count() == 0


def test_b2b_product_contract_active_quantity_is_supported():
    sku_id = uuid.uuid4()

    sku_map = normalize_skus(
        [
            {
                "id": str(uuid.uuid4()),
                "title": "Phone",
                "status": "MODERATED",
                "skus": [
                    {
                        "id": str(sku_id),
                        "name": "Black",
                        "price": 1000,
                        "activeQuantity": 7,
                    }
                ],
            }
        ]
    )

    assert sku_map[str(sku_id)]["available_quantity"] == 7
