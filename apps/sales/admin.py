from django.contrib import admin

from apps.sales.models import SalesInvoice, SalesInvoiceLine

INVOICE_FIELDS = (
    "company",
    "partner",
    "number",
    "status",
    "issue_date",
    "due_date",
    "subtotal",
    "tax_total",
    "total",
    "created_by",
    "created_at",
    "updated_at",
)


class SalesInvoiceLineInline(admin.TabularInline):
    model = SalesInvoiceLine
    extra = 0
    fields = ("product", "quantity", "unit_price", "tax_rate", "subtotal", "tax_amount", "total")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    """Read-only in admin by design: all mutations (draft edits, line
    management, issue, void) carry invariants that only
    apps/sales/services.py enforces (draft-only edits, recalculated
    totals, atomic numbering). Django admin's default save path would
    bypass every one of those, so rather than re-implement them here
    (or risk someone editing a field admin shouldn't touch), the admin
    is inspection-only — matches the project-wide principle that admin
    is an internal tool, never the primary UI."""

    list_display = ("number", "company", "partner", "status", "total", "issue_date", "created_at")
    list_filter = ("status", "company")
    search_fields = ("number", "partner__name")
    autocomplete_fields = ("company", "partner", "created_by")
    readonly_fields = INVOICE_FIELDS
    inlines = [SalesInvoiceLineInline]

    def has_add_permission(self, request):
        return False
