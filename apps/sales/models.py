from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import CompanyScopedModel
from apps.core.money import ZERO

MIN_QUANTITY = Decimal("0.01")


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    ISSUED = "issued", "Emitida"
    PAID = "paid", "Pagada"
    VOID = "void", "Anulada"


class SalesInvoice(CompanyScopedModel):
    """A sales invoice. `paid` exists in the domain but nothing in this
    app ever assigns it — that transition belongs to the future
    `treasury` app, once payments exist.

    `number` is blank for drafts and only assigned by `services.issue_invoice()`
    (see apps/sales/services.py for the numbering strategy) — the partial
    unique index below mirrors the same "unique only when informed"
    pattern already used for Partner.tax_id.
    """

    partner = models.ForeignKey(
        "partners.Partner", on_delete=models.PROTECT, related_name="sales_invoices"
    )
    number = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(
        max_length=10, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT
    )
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    # PROTECT: never lose who created a financial document just because
    # their user account gets deleted later.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "number"],
                condition=~Q(number=""),
                name="unique_sales_invoice_number_per_company",
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0), name="sales_invoice_subtotal_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(tax_total__gte=0), name="sales_invoice_tax_total_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(total__gte=0), name="sales_invoice_total_non_negative"
            ),
        ]

    def __str__(self):
        return self.number or f"Draft #{self.pk}"

    def clean(self):
        super().clean()
        if self.partner_id and self.company_id and self.partner.company_id != self.company_id:
            raise ValidationError({"partner": "El tercero debe pertenecer a la misma empresa."})
        if self.partner_id and not self.partner.is_customer:
            raise ValidationError({"partner": "El tercero debe ser cliente."})


class SalesInvoiceLine(CompanyScopedModel):
    """A line's `unit_price`/`tax_rate` are a snapshot taken at the moment
    the line is added (see apps/sales/services.add_line) — they never
    re-read from Product afterward, so a later price/tax change on the
    Product does not alter historical invoices.

    `tax_rate` convention: a percentage, e.g. 19.00 means 19% (matching
    `catalog.Product.tax_rate`, which this snapshots from) — never a
    fraction like 0.19. `tax_amount = subtotal * tax_rate / 100`.

    `company` duplicates `invoice.company` (kept in sync by the service
    layer, never independently settable) rather than only being reachable
    via a join — every tenant-scoped row in this project carries its own
    `company` FK directly, which is what makes `.for_company()` and the
    permission/queryset scoping infra uniform across all resources.
    """

    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="sales_invoice_lines"
    )
    quantity = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(MIN_QUANTITY)]
    )
    unit_price = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(ZERO)]
    )
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)]
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="sales_invoice_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="sales_invoice_line_unit_price_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(tax_rate__gte=0), name="sales_invoice_line_tax_rate_non_negative"
            ),
        ]

    def __str__(self):
        return f"{self.invoice} / {self.product}"

    def clean(self):
        super().clean()
        if self.product_id and self.company_id and self.product.company_id != self.company_id:
            raise ValidationError({"product": "El producto debe pertenecer a la misma empresa."})


class SalesInvoiceSequence(models.Model):
    """One counter row per Company, holding the last assigned invoice
    number. Not a CompanyScopedModel: it's a singleton per company (a
    OneToOne), not a scoped collection, so `.for_company()`/timestamps
    don't apply the way they do for business records.

    Locked with `select_for_update()` inside `services.issue_invoice()`'s
    transaction to serialize numbering per company — see that module for
    why this is used instead of `MAX(number) + 1`.
    """

    company = models.OneToOneField(
        "companies.Company", on_delete=models.PROTECT, related_name="sales_invoice_sequence"
    )
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.company} -> {self.last_number}"
