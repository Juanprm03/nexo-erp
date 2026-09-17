from django.contrib import admin

from apps.partners.models import Partner


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "tax_id",
        "is_customer",
        "is_supplier",
        "is_active",
        "created_at",
    )
    list_filter = ("company", "is_customer", "is_supplier", "is_active")
    search_fields = ("name", "tax_id", "email")
    autocomplete_fields = ("company",)
