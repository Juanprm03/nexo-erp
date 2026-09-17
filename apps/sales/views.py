from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.companies.mixins import CompanyRoleRequiredMixin, CompanyScopedQuerysetMixin
from apps.companies.models import MembershipRole
from apps.companies.services import user_has_role
from apps.sales import services
from apps.sales.forms import SalesInvoiceForm, SalesInvoiceLineAddForm, SalesInvoiceLineEditForm
from apps.sales.models import InvoiceStatus, SalesInvoice
from apps.sales.permissions import SALES_VOID_ROLES, SALES_WRITE_ROLES

VIEW_ROLES = tuple(MembershipRole.values)


class SalesInvoiceListView(CompanyRoleRequiredMixin, CompanyScopedQuerysetMixin, ListView):
    allowed_roles = VIEW_ROLES
    model = SalesInvoice
    paginate_by = 25
    template_name = "sales/invoice_list.html"
    context_object_name = "invoices"

    def get_queryset(self):
        return super().get_queryset().select_related("partner")


class SalesInvoiceDetailView(CompanyRoleRequiredMixin, CompanyScopedQuerysetMixin, DetailView):
    allowed_roles = VIEW_ROLES
    model = SalesInvoice
    template_name = "sales/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return super().get_queryset().select_related("partner").prefetch_related("lines__product")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.request.active_company
        context["line_form"] = SalesInvoiceLineAddForm(company=company)
        context["can_write"] = user_has_role(self.request.user, company, *SALES_WRITE_ROLES)
        context["can_void"] = user_has_role(self.request.user, company, *SALES_VOID_ROLES)
        return context


def _get_draft_or_403(request, pk):
    """Shared by every draft-mutation view below: fetch a company-scoped
    invoice and refuse (403, not a silently-broken form) if it isn't a
    draft — the *actual* enforcement is in apps/sales/services.py, this
    just avoids showing an edit UI that can only ever fail."""
    invoice = get_object_or_404(SalesInvoice.objects.for_company(request.active_company), pk=pk)
    if invoice.status != InvoiceStatus.DRAFT:
        raise PermissionDenied("Solo se pueden editar facturas en borrador.")
    return invoice


class SalesInvoiceCreateView(CompanyRoleRequiredMixin, View):
    allowed_roles = SALES_WRITE_ROLES

    def get(self, request):
        form = SalesInvoiceForm(company=request.active_company)
        return render(request, "sales/invoice_form.html", {"form": form})

    def post(self, request):
        form = SalesInvoiceForm(request.POST, company=request.active_company)
        if form.is_valid():
            try:
                invoice = services.create_draft_invoice(
                    company=request.active_company,
                    partner=form.cleaned_data["partner"],
                    created_by=request.user,
                    due_date=form.cleaned_data["due_date"],
                )
            except services.InvoiceError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Borrador de factura creado.")
                return redirect("sales:detail", pk=invoice.pk)
        return render(request, "sales/invoice_form.html", {"form": form})


class SalesInvoiceUpdateView(CompanyRoleRequiredMixin, View):
    allowed_roles = SALES_WRITE_ROLES

    def get(self, request, pk):
        invoice = _get_draft_or_403(request, pk)
        form = SalesInvoiceForm(instance=invoice, company=request.active_company)
        return render(request, "sales/invoice_form.html", {"form": form, "invoice": invoice})

    def post(self, request, pk):
        invoice = _get_draft_or_403(request, pk)
        form = SalesInvoiceForm(request.POST, instance=invoice, company=request.active_company)
        if form.is_valid():
            try:
                services.update_draft_invoice(
                    invoice,
                    partner=form.cleaned_data["partner"],
                    due_date=form.cleaned_data["due_date"],
                )
            except services.InvoiceError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Factura actualizada.")
                return redirect("sales:detail", pk=invoice.pk)
        return render(request, "sales/invoice_form.html", {"form": form, "invoice": invoice})


class SalesInvoiceLineAddView(CompanyRoleRequiredMixin, View):
    allowed_roles = SALES_WRITE_ROLES

    def post(self, request, pk):
        invoice = _get_draft_or_403(request, pk)
        form = SalesInvoiceLineAddForm(request.POST, company=request.active_company)
        if form.is_valid():
            try:
                services.add_line(
                    invoice,
                    product=form.cleaned_data["product"],
                    quantity=form.cleaned_data["quantity"],
                    unit_price=form.cleaned_data.get("unit_price"),
                )
            except services.InvoiceError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Línea agregada.")
        else:
            messages.error(request, "Datos de línea inválidos.")
        return redirect("sales:detail", pk=invoice.pk)


class SalesInvoiceLineEditView(CompanyRoleRequiredMixin, View):
    allowed_roles = SALES_WRITE_ROLES

    def _get_line(self, invoice, line_pk):
        return get_object_or_404(invoice.lines, pk=line_pk)

    def get(self, request, pk, line_pk):
        invoice = _get_draft_or_403(request, pk)
        line = self._get_line(invoice, line_pk)
        form = SalesInvoiceLineEditForm(
            initial={"quantity": line.quantity, "unit_price": line.unit_price}
        )
        context = {"form": form, "invoice": invoice, "line": line}
        return render(request, "sales/invoice_line_form.html", context)

    def post(self, request, pk, line_pk):
        invoice = _get_draft_or_403(request, pk)
        line = self._get_line(invoice, line_pk)
        form = SalesInvoiceLineEditForm(request.POST)
        if form.is_valid():
            try:
                services.update_line(
                    line,
                    quantity=form.cleaned_data["quantity"],
                    unit_price=form.cleaned_data["unit_price"],
                )
            except services.InvoiceError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Línea actualizada.")
                return redirect("sales:detail", pk=invoice.pk)
        context = {"form": form, "invoice": invoice, "line": line}
        return render(request, "sales/invoice_line_form.html", context)


class SalesInvoiceLineDeleteView(CompanyRoleRequiredMixin, View):
    allowed_roles = SALES_WRITE_ROLES

    def post(self, request, pk, line_pk):
        invoice = _get_draft_or_403(request, pk)
        line = get_object_or_404(invoice.lines, pk=line_pk)
        try:
            services.remove_line(line)
        except services.InvoiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Línea eliminada.")
        return redirect("sales:detail", pk=invoice.pk)


class SalesInvoiceIssueView(CompanyRoleRequiredMixin, View):
    allowed_roles = SALES_WRITE_ROLES

    def post(self, request, pk):
        invoice = get_object_or_404(SalesInvoice.objects.for_company(request.active_company), pk=pk)
        try:
            services.issue_invoice(invoice, actor=request.user)
        except services.InvoiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Factura {invoice.number} emitida.")
        return redirect("sales:detail", pk=invoice.pk)


class SalesInvoiceVoidView(CompanyRoleRequiredMixin, View):
    allowed_roles = SALES_VOID_ROLES

    def post(self, request, pk):
        invoice = get_object_or_404(SalesInvoice.objects.for_company(request.active_company), pk=pk)
        try:
            services.void_invoice(invoice, actor=request.user)
        except services.InvoiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Factura anulada.")
        return redirect("sales:detail", pk=invoice.pk)
