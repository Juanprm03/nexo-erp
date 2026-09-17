from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.companies.permissions import HasActiveCompany, IsCompanyMember, IsSameCompanyObject
from apps.companies.viewsets import CompanyScopedViewSetMixin
from apps.sales import services
from apps.sales.api.serializers import SalesInvoiceLineSerializer, SalesInvoiceSerializer
from apps.sales.models import SalesInvoice, SalesInvoiceLine
from apps.sales.permissions import CanVoidSalesInvoice, CanWriteSalesInvoice


class SalesInvoiceViewSet(CompanyScopedViewSetMixin, viewsets.ModelViewSet):
    """No DELETE: a draft has no "physical delete" flow in this MVP (only
    its lines do), and issued/paid/void invoices must never disappear —
    `void` is the only terminal transition, and it's an action, not a
    DELETE request.

    Line management is a **separate ViewSet** (SalesInvoiceLineViewSet),
    not a nested writable serializer here — nested writable serializers
    need hand-rolled create/update/delete-diffing logic for the list of
    lines, which duplicates exactly what apps/sales/services.py already
    does per-line (recalculate totals, enforce draft-only). A flat,
    separately-permissioned endpoint filtered by `invoice` is simpler and
    reuses that service layer directly. `lines` is still readable as a
    nested list on the invoice (read-only) for a convenient GET.
    """

    serializer_class = SalesInvoiceSerializer
    queryset = SalesInvoice.objects.select_related("partner").prefetch_related("lines")
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    filterset_fields = ["status", "partner"]
    search_fields = ["number"]
    ordering_fields = ["issue_date", "created_at", "total"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            role_permission = IsCompanyMember
        elif self.action == "void":
            role_permission = CanVoidSalesInvoice
        else:
            role_permission = CanWriteSalesInvoice
        return [
            IsAuthenticated(),
            HasActiveCompany(),
            IsSameCompanyObject(),
            role_permission(),
        ]

    def perform_create(self, serializer):
        try:
            invoice = services.create_draft_invoice(
                company=self.request.active_company,
                partner=serializer.validated_data["partner"],
                created_by=self.request.user,
                due_date=serializer.validated_data.get("due_date"),
            )
        except services.InvoiceError as exc:
            raise DRFValidationError(str(exc)) from exc
        serializer.instance = invoice

    def perform_update(self, serializer):
        try:
            services.update_draft_invoice(
                serializer.instance,
                partner=serializer.validated_data.get("partner"),
                due_date=serializer.validated_data.get("due_date"),
            )
        except services.InvoiceError as exc:
            raise DRFValidationError(str(exc)) from exc

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        invoice = self.get_object()
        try:
            services.issue_invoice(invoice, actor=request.user)
        except services.InvoiceError as exc:
            raise DRFValidationError(str(exc)) from exc
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        invoice = self.get_object()
        try:
            services.void_invoice(invoice, actor=request.user)
        except services.InvoiceError as exc:
            raise DRFValidationError(str(exc)) from exc
        return Response(self.get_serializer(invoice).data)


class SalesInvoiceLineViewSet(CompanyScopedViewSetMixin, viewsets.ModelViewSet):
    """Lines ARE hard-deletable (unlike invoices) while their invoice is
    still a draft — services.remove_line() enforces the draft-only rule,
    so this never touches an issued invoice's lines."""

    serializer_class = SalesInvoiceLineSerializer
    queryset = SalesInvoiceLine.objects.select_related("invoice", "product")
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]
    filterset_fields = ["invoice"]

    def get_permissions(self):
        is_read_action = self.action in ("list", "retrieve")
        role_permission = IsCompanyMember if is_read_action else CanWriteSalesInvoice
        return [
            IsAuthenticated(),
            HasActiveCompany(),
            IsSameCompanyObject(),
            role_permission(),
        ]

    def perform_create(self, serializer):
        try:
            line = services.add_line(
                serializer.validated_data["invoice"],
                product=serializer.validated_data["product"],
                quantity=serializer.validated_data["quantity"],
                unit_price=serializer.validated_data.get("unit_price"),
            )
        except services.InvoiceError as exc:
            raise DRFValidationError(str(exc)) from exc
        serializer.instance = line

    def perform_update(self, serializer):
        try:
            services.update_line(
                serializer.instance,
                quantity=serializer.validated_data.get("quantity"),
                unit_price=serializer.validated_data.get("unit_price"),
            )
        except services.InvoiceError as exc:
            raise DRFValidationError(str(exc)) from exc

    def perform_destroy(self, instance):
        try:
            services.remove_line(instance)
        except services.InvoiceError as exc:
            raise DRFValidationError(str(exc)) from exc
