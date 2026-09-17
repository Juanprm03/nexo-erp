"""Reusable mixins for server-rendered (Django template) views.

Mirrors apps/companies/permissions.py and viewsets.py for the template
side of the product, which is the priority per current architecture
decisions (session + CSRF first, JWT for external API consumers later).
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.companies.services import user_has_role


class ActiveCompanyRequiredMixin(LoginRequiredMixin):
    """Requires a logged-in user with an active company resolved by
    ActiveCompanyMiddleware."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request, "active_company", None) is None:
            raise PermissionDenied("Selecciona una empresa activa antes de continuar.")
        return super().dispatch(request, *args, **kwargs)


class CompanyRoleRequiredMixin(ActiveCompanyRequiredMixin):
    """Requires the user's role in the active company to be one of `allowed_roles`."""

    allowed_roles: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        company = getattr(request, "active_company", None)
        if (
            request.user.is_authenticated
            and company is not None
            and not user_has_role(request.user, company, *self.allowed_roles)
        ):
            raise PermissionDenied("No tienes el rol requerido para esta acción.")
        return super().dispatch(request, *args, **kwargs)


class CompanyScopedQuerysetMixin:
    """Scopes a ListView/DetailView queryset to `request.active_company`."""

    def get_queryset(self):
        queryset = super().get_queryset()
        company = getattr(self.request, "active_company", None)
        if company is None:
            return queryset.none()
        return queryset.for_company(company)
