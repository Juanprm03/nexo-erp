from django.conf import settings
from django.db import models

from apps.core.models import CompanyScopedModel, TimeStampedModel


class Company(TimeStampedModel):
    """A tenant. Every scoped record belongs to exactly one Company."""

    name = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=50, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MembershipRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    ACCOUNTANT = "accountant", "Contador"
    SALES = "sales", "Ventas"
    PURCHASING = "purchasing", "Compras"
    READONLY = "readonly", "Solo lectura"


# Roles with access to every operational area (accountant/sales/purchasing),
# on top of general company administration. Any permission class gating an
# operational action should include these explicitly, e.g.
# `allowed_roles = (*MANAGEMENT_ROLES, MembershipRole.SALES)`, so owner/admin
# are never accidentally locked out of an area-specific permission.
# `owner` vs `admin` are equal here — actions exclusive to `owner` (none yet)
# should use `(MembershipRole.OWNER,)` directly instead of this tuple.
MANAGEMENT_ROLES = (MembershipRole.OWNER, MembershipRole.ADMIN)


class CompanyMembership(CompanyScopedModel):
    """Grants a User a fixed role within a Company.

    Inherits `company` (FK, PROTECT) and timestamps from CompanyScopedModel:
    a membership is itself tenant data scoped to the company it grants
    access to, so it reuses the same abstraction instead of redeclaring
    the same field.
    """

    company = models.ForeignKey(
        "companies.Company", on_delete=models.PROTECT, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_memberships"
    )
    role = models.CharField(max_length=20, choices=MembershipRole.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"], name="unique_user_company_membership"
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.company} ({self.role})"
