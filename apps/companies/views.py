from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from apps.companies.models import Company
from apps.companies.services import CompanyAccessDenied, activate_company


class CompanySwitchView(LoginRequiredMixin, View):
    """Lets the user pick which of their own companies is active this
    session. Deliberately minimal: no company CRUD here, just the switch
    UI needed to exercise the rest of the product end to end."""

    template_name = "companies/switch.html"

    def get(self, request):
        memberships = request.user.company_memberships.filter(is_active=True).select_related(
            "company"
        )
        return render(request, self.template_name, {"memberships": memberships})

    def post(self, request):
        # Validate the id shape ourselves: a non-numeric company_id would
        # otherwise raise an unhandled ValueError when Django tries to
        # cast it for the pk lookup, surfacing as a raw 500.
        company_id = request.POST.get("company_id", "")
        company = Company.objects.filter(pk=company_id).first() if company_id.isdigit() else None

        if company is None:
            messages.error(request, "Empresa inválida.")
            return redirect("companies:switch")

        try:
            activate_company(request, request.user, company)
        except CompanyAccessDenied:
            messages.error(request, "No tienes acceso a esa empresa.")
            return redirect("companies:switch")

        messages.success(request, f"Empresa activa: {company.name}")
        return redirect(self._safe_next(request) or "partners:list")

    def _safe_next(self, request):
        """Only follow `next` if it points back into this site — the
        current template never sends it, but the endpoint must not become
        an open redirect just because a future form (or a direct POST)
        does."""
        next_url = request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return next_url
        return None
