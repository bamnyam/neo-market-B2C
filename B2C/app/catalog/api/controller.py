from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.catalog.services import (
    ALLOWED_SORTS,
    B2BCatalogClient,
    B2BUnavailableError,
    B2BUpstreamError,
)


INVALID_SORT_MESSAGE = (
    "Invalid sort parameter. Allowed: "
    "rating, popularity, price_asc, price_desc, date_desc, discount_desc"
)


class CatalogProxyMixin:
    service_class = B2BCatalogClient

    def _proxy_response(self, method_name, *args):
        try:
            payload = getattr(self.service_class(), method_name)(*args)
        except B2BUnavailableError:
            return Response(
                {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Catalog temporarily unavailable",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except B2BUpstreamError as exc:
            return Response(exc.payload, status=exc.status_code)

        return Response(payload, status=status.HTTP_200_OK)

    def _invalid_request(self, message):
        return Response(
            {
                "code": "INVALID_REQUEST",
                "message": message,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class ProductsController(CatalogProxyMixin, APIView):
    def get(self, request):
        sort = request.query_params.get("sort", "rating")

        if sort not in ALLOWED_SORTS:
            return self._invalid_request(INVALID_SORT_MESSAGE)

        query_params = request.query_params.copy()
        query_params.setdefault("limit", "20")
        query_params.setdefault("offset", "0")
        query_params.setdefault("sort", sort)

        return self._proxy_response("get_products", query_params)


class CategoryFiltersController(CatalogProxyMixin, APIView):
    def get(self, request, category_id):
        return self._proxy_response("get_category_filters", category_id)


class CatalogFacetsController(CatalogProxyMixin, APIView):
    def get(self, request):
        if not request.query_params.get("category_id"):
            return self._invalid_request("category_id is required")

        return self._proxy_response("get_facets", request.query_params)
