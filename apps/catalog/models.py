from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import CompanyScopedModel

ZERO = Decimal("0")


class ProductType(models.TextChoices):
    GOOD = "good", "Bien"
    SERVICE = "service", "Servicio"


class Product(CompanyScopedModel):
    """A good or service a company sells or buys. No inventory/stock yet."""

    sku = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=ProductType.choices)
    unit_price = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(ZERO)]
    )
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "sku"], name="unique_product_sku_per_company"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0), name="product_unit_price_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(tax_rate__gte=0), name="product_tax_rate_non_negative"
            ),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"
