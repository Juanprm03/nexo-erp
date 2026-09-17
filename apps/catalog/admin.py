from django.contrib import admin

from apps.catalog.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "company",
        "type",
        "unit_price",
        "tax_rate",
        "is_active",
    )
    list_filter = ("company", "type", "is_active")
    search_fields = ("sku", "name")
    autocomplete_fields = ("company",)
