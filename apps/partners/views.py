from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.companies.mixins import (
    CompanyRoleRequiredMixin,
    CompanyScopedFormMixin,
    CompanyScopedQuerysetMixin,
)
from apps.companies.models import MANAGEMENT_ROLES, MembershipRole
from apps.partners.forms import PartnerForm
from apps.partners.models import Partner

VIEW_ROLES = tuple(MembershipRole.values)
WRITE_ROLES = (*MANAGEMENT_ROLES, MembershipRole.ACCOUNTANT)


class PartnerListView(CompanyRoleRequiredMixin, CompanyScopedQuerysetMixin, ListView):
    allowed_roles = VIEW_ROLES
    model = Partner
    paginate_by = 25
    template_name = "partners/partner_list.html"
    context_object_name = "partners"


class PartnerDetailView(CompanyRoleRequiredMixin, CompanyScopedQuerysetMixin, DetailView):
    allowed_roles = VIEW_ROLES
    model = Partner
    template_name = "partners/partner_detail.html"
    context_object_name = "partner"


class PartnerCreateView(CompanyRoleRequiredMixin, CompanyScopedFormMixin, CreateView):
    allowed_roles = WRITE_ROLES
    model = Partner
    form_class = PartnerForm
    template_name = "partners/partner_form.html"
    success_url = reverse_lazy("partners:list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Tercero creado correctamente.")
        return response


class PartnerUpdateView(CompanyRoleRequiredMixin, CompanyScopedFormMixin, UpdateView):
    allowed_roles = WRITE_ROLES
    model = Partner
    form_class = PartnerForm
    template_name = "partners/partner_form.html"
    success_url = reverse_lazy("partners:list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Tercero actualizado correctamente.")
        return response


class PartnerDeactivateView(CompanyRoleRequiredMixin, View):
    """POST-only soft delete. Not built on CompanyScopedQuerysetMixin: a
    bare View has no get_queryset() for that mixin to extend via super(),
    so scoping is applied directly with .for_company() instead."""

    allowed_roles = WRITE_ROLES

    def post(self, request, pk):
        partner = get_object_or_404(
            Partner.objects.for_company(request.active_company), pk=pk
        )
        partner.is_active = False
        partner.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f"{partner.name} desactivado.")
        return redirect("partners:list")
