from django.db import IntegrityError
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated

from apps.companies.permissions import (
    HasActiveCompany,
    IsCompanyAccountant,
    IsCompanyMember,
    IsSameCompanyObject,
)
from apps.companies.viewsets import CompanyScopedViewSetMixin
from apps.partners.api.serializers import PartnerSerializer
from apps.partners.models import Partner


class PartnerViewSet(CompanyScopedViewSetMixin, viewsets.ModelViewSet):
    """Partners are soft-deleted: no DELETE route, only PATCH is_active=False."""

    serializer_class = PartnerSerializer
    queryset = Partner.objects.all()
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    filterset_fields = ["is_customer", "is_supplier", "is_active"]
    search_fields = ["name", "tax_id"]
    ordering_fields = ["name", "created_at"]

    def get_permissions(self):
        # Read: owner/admin/accountant/sales/purchasing/readonly (any active
        # member). Write: owner/admin/accountant only (see MembershipRole).
        is_read_action = self.action in ("list", "retrieve")
        role_permission = IsCompanyMember if is_read_action else IsCompanyAccountant
        return [
            IsAuthenticated(),
            HasActiveCompany(),
            IsSameCompanyObject(),
            role_permission(),
        ]

    def _save_or_400(self, serializer, **kwargs):
        try:
            serializer.save(**kwargs)
        except IntegrityError as exc:
            raise DRFValidationError(
                "No se pudo guardar el tercero: revisa los datos únicos de la empresa."
            ) from exc

    def perform_create(self, serializer):
        self._save_or_400(serializer, company=self.request.active_company)

    def perform_update(self, serializer):
        self._save_or_400(serializer)
