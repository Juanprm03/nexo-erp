from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import CompanyScopedModel


class Partner(CompanyScopedModel):
    """A third party that can be a customer, a supplier, or both.

    `tax_id` uses an empty string (never null) as the "not informed"
    sentinel, so the partial unique index below can express "unique per
    company only when informed" with a single, readable condition.
    """

    name = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=50, blank=True, default="")
    is_customer = models.BooleanField(default=False)
    is_supplier = models.BooleanField(default=False)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(is_customer=True) | Q(is_supplier=True),
                name="partner_is_customer_or_supplier",
            ),
            models.UniqueConstraint(
                fields=["company", "tax_id"],
                condition=~Q(tax_id=""),
                name="unique_partner_tax_id_per_company",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self.is_customer and not self.is_supplier:
            raise ValidationError("El tercero debe ser cliente, proveedor o ambos.")

        # Django's automatic validate_unique() skips UniqueConstraints that
        # have a `condition` (our partial index below), so the friendly
        # form/admin error has to be raised here explicitly — the DB
        # constraint remains the actual guard against race conditions.
        if self.tax_id and self.company_id is not None:
            duplicates = Partner.objects.filter(company_id=self.company_id, tax_id=self.tax_id)
            if self.pk is not None:
                duplicates = duplicates.exclude(pk=self.pk)
            if duplicates.exists():
                raise ValidationError(
                    {"tax_id": "Ya existe un tercero con este tax_id en la empresa activa."}
                )
