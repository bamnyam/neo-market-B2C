import json
import urllib.request

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from app.catalog.services.b2b_client import B2BCatalogClient


@pytest.fixture
def api_client():
    return APIClient()


def test_catalog_returns_filtered_sorted_products(api_client, monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["service_key"] = request.headers["X-service-key"]
        return JsonResponse(
            {
                "items": [
                    {
                        "id": "770e8400-e29b-41d4-a716-446655440002",
                        "title": "iPhone 15 Pro Max",
                        "image": "https://cdn.neomarket.ru/images/iphone15.jpg",
                        "price": 12999000,
                        "in_stock": True,
                        "is_in_cart": False,
                    }
                ],
                "total_count": 1,
                "limit": 20,
                "offset": 0,
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    response = api_client.get(
        "/api/v1/products",
        {
            "category_id": "123e4567-e89b-12d3-a456-426614174001",
            "filters[brand]": "Apple",
            "sort": "price_asc",
            "limit": "20",
            "offset": "0",
        },
    )

    assert response.status_code == 200
    assert response.data["items"][0]["title"] == "iPhone 15 Pro Max"
    assert response.data["total_count"] == 1
    assert "category_id=123e4567-e89b-12d3-a456-426614174001" in seen["url"]
    assert "filters%5Bbrand%5D=Apple" in seen["url"]
    assert "sort=price_asc" in seen["url"]
    assert "limit=20" in seen["url"]
    assert "offset=0" in seen["url"]
    assert seen["service_key"] == settings.B2C_TO_B2B_KEY


def test_facets_return_counts_per_filter_value(api_client, monkeypatch):
    def fake_urlopen(request, timeout):
        assert "/api/v1/catalog/facets?" in request.full_url
        assert "filters%5Bbrand%5D=Apple" in request.full_url
        return JsonResponse(
            {
                "category_id": "123e4567-e89b-12d3-a456-426614174001",
                "facets": [
                    {
                        "name": "brand",
                        "values": [
                            {"value": "Apple", "count": 124},
                            {"value": "Samsung", "count": 98},
                        ],
                    },
                    {
                        "name": "color",
                        "values": [{"value": "черный", "count": 60}],
                    },
                ],
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    response = api_client.get(
        "/api/v1/catalog/facets",
        {
            "category_id": "123e4567-e89b-12d3-a456-426614174001",
            "filters[brand]": "Apple",
        },
    )

    assert response.status_code == 200
    assert response.data["facets"][0]["name"] == "brand"
    assert response.data["facets"][0]["values"] == [
        {"value": "Apple", "count": 124},
        {"value": "Samsung", "count": 98},
    ]


def test_invalid_sort_returns_400(api_client, monkeypatch):
    def fail_if_called(request, timeout):
        raise AssertionError("B2B must not be called for invalid sort")

    monkeypatch.setattr(urllib.request, "urlopen", fail_if_called)

    response = api_client.get("/api/v1/products", {"sort": "price_up"})

    assert response.status_code == 400
    assert response.data == {
        "code": "INVALID_REQUEST",
        "message": (
            "Invalid sort parameter. Allowed: "
            "rating, popularity, price_asc, price_desc, date_desc, discount_desc"
        ),
    }


def test_b2b_unavailable_returns_502(api_client, monkeypatch):
    def fake_urlopen(request, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    response = api_client.get("/api/v1/products")

    assert response.status_code == 502
    assert response.data == {
        "code": "SERVICE_UNAVAILABLE",
        "message": "Catalog temporarily unavailable",
    }


def test_empty_category_returns_empty_page(api_client, monkeypatch):
    monkeypatch.setattr(
        B2BCatalogClient,
        "get_products",
        lambda self, query_params: {
            "items": [],
            "total_count": 0,
            "limit": 20,
            "offset": 0,
        },
    )

    response = api_client.get(
        "/api/v1/products",
        {"category_id": "123e4567-e89b-12d3-a456-426614174001"},
    )

    assert response.status_code == 200
    assert response.data["items"] == []
    assert response.data["total_count"] == 0


def test_missing_facets_category_id_returns_400(api_client):
    response = api_client.get("/api/v1/catalog/facets")

    assert response.status_code == 400
    assert response.data == {
        "code": "INVALID_REQUEST",
        "message": "category_id is required",
    }


class JsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode()
