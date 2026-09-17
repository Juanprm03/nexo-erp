"""Business logic for company membership and active-company selection.

Kept as plain functions (no class-based "service objects") since none of
this needs shared state across calls — a thin, testable layer between
views/viewsets and the models.
"""

from django.core.exceptions import PermissionDenied

from apps.companies.models import CompanyMembership

ACTIVE_COMPANY_SESSION_KEY = "active_company_id"


class CompanyAccessDenied(PermissionDenied):
    """Raised when a user has no active membership in the given company."""


def get_active_membership(user, company):
    """Return the user's active membership in `company`, or None."""
    if company is None or not getattr(user, "is_authenticated", False):
        return None
    return (
        CompanyMembership.objects.filter(user=user, company=company, is_active=True)
        .select_related("company")
        .first()
    )


def user_has_role(user, company, *roles):
    """Whether `user` has an active membership in `company` with one of `roles`."""
    if company is None or not roles or not getattr(user, "is_authenticated", False):
        return False
    return CompanyMembership.objects.filter(
        user=user, company=company, is_active=True, role__in=roles
    ).exists()


def activate_company(request, user, company):
    """Set `company` as the active company for `user`'s session.

    Never trusts a bare company id: always re-derives access from a real,
    active CompanyMembership row before touching the session.
    """
    membership = get_active_membership(user, company)
    if membership is None:
        raise CompanyAccessDenied(
            "El usuario no tiene una membresía activa en esta empresa."
        )
    request.session[ACTIVE_COMPANY_SESSION_KEY] = company.id
    return membership
