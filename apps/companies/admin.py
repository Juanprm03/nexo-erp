from django.contrib import admin

from apps.companies.models import Company, CompanyMembership


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "tax_id", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "tax_id")


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "company")
    search_fields = ("user__email", "company__name")
    autocomplete_fields = ("user", "company")
