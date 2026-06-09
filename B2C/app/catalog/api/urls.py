from django.urls import path

from app.catalog.api.controller import (
    CatalogFacetsController,
    CategoryFiltersController,
    ProductsController,
)

urlpatterns = [
    path("products", ProductsController.as_view(), name="catalog-products"),
    path(
        "categories/<str:category_id>/filters",
        CategoryFiltersController.as_view(),
        name="category-filters",
    ),
    path("catalog/facets", CatalogFacetsController.as_view(), name="catalog-facets"),
]
