from django.db import IntegrityError
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated

from apps.catalog.api.serializers import ProductSerializer
from apps.catalog.models import Product
from apps.companies.permissions import (
    HasActiveCompany,
    IsCompanyAdmin,
    IsCompanyMember,
    IsSameCompanyObject,
)
from apps.companies.viewsets import CompanyScopedViewSetMixin


class ProductViewSet(CompanyScopedViewSetMixin, viewsets.ModelViewSet):
    """Products are soft-deleted: no DELETE route, only PATCH is_active=False."""

    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    filterset_fields = ["type", "is_active"]
    search_fields = ["sku", "name"]
    ordering_fields = ["name", "sku", "unit_price", "created_at"]

    def get_permissions(self):
        # Read: any active member. Write: owner/admin only.
        is_read_action = self.action in ("list", "retrieve")
        role_permission = IsCompanyMember if is_read_action else IsCompanyAdmin
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
                "No se pudo guardar el producto: revisa los datos únicos de la empresa."
            ) from exc

    def perform_create(self, serializer):
        self._save_or_400(serializer, company=self.request.active_company)

    def perform_update(self, serializer):
        self._save_or_400(serializer)
