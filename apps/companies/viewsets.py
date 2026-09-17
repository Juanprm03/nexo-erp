"""Generic DRF ViewSet infrastructure for future CompanyScopedModel resources.

No concrete resource (Partner, Product, ...) is implemented here — this is
the reusable base that a future `PartnerViewSet(CompanyScopedViewSetMixin,
ModelViewSet)` etc. will build on.
"""

from rest_framework.exceptions import PermissionDenied


class CompanyScopedViewSetMixin:
    """Scopes the queryset to `request.active_company` and stamps it on create.

    Requires the view's `queryset`/model manager to expose `.for_company()`
    (i.e. the model extends `apps.core.models.CompanyScopedModel`).
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        company = getattr(self.request, "active_company", None)
        if company is None:
            raise PermissionDenied("No hay una empresa activa seleccionada.")
        return queryset.for_company(company)

    def perform_create(self, serializer):
        serializer.save(company=self.request.active_company)
