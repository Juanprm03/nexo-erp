from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base with creation/update timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CompanyScopedQuerySet(models.QuerySet):
    """Explicit scoping only. Never filters automatically."""

    def for_company(self, company):
        return self.filter(company=company)


class CompanyScopedModel(TimeStampedModel):
    """Abstract base for tenant data belonging to exactly one Company.

    `on_delete=PROTECT`: a Company must be deactivated (`is_active=False`),
    never hard-deleted while it still owns business records — deleting it
    should not be able to silently wipe out a tenant's data.
    """

    company = models.ForeignKey("companies.Company", on_delete=models.PROTECT)

    objects = CompanyScopedQuerySet.as_manager()

    class Meta:
        abstract = True
