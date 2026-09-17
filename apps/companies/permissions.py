"""Reusable DRF permission classes for the fixed company roles.

No dynamic permission matrix: roles are fixed (see MembershipRole) and
each class below just declares which roles it accepts. Combine with
`IsSameCompanyObject` for object-level checks and with
`CompanyScopedViewSetMixin` (apps/companies/viewsets.py) for queryset
scoping — none of these implement a concrete resource yet.

Role hierarchy used here:
- `owner` / `admin` (MANAGEMENT_ROLES): access to every operational area
  plus general company administration. Every operational permission
  class below includes MANAGEMENT_ROLES so owner/admin are never
  accidentally excluded from a lower role's actions.
- `owner`-exclusive actions (none defined yet) should use
  `IsCompanyOwner`, not MANAGEMENT_ROLES.
- `accountant` / `sales` / `purchasing`: parallel operational roles, no
  hierarchy between them.
- `readonly`: baseline, any active membership (see `IsCompanyMember`).
"""

from rest_framework.permissions import BasePermission

from apps.companies.models import MANAGEMENT_ROLES, MembershipRole
from apps.companies.services import user_has_role


class HasActiveCompany(BasePermission):
    message = "No hay una empresa activa seleccionada."

    def has_permission(self, request, view):
        return getattr(request, "active_company", None) is not None


class IsSameCompanyObject(BasePermission):
    """Object-level check: the object must belong to the active company.

    Defensive by design — meant to be used even when the queryset is
    already scoped, as a second, independent guard against future bugs.
    """

    message = "El recurso no pertenece a la empresa activa."

    def has_object_permission(self, request, view, obj):
        company = getattr(request, "active_company", None)
        return company is not None and obj.company_id == company.id


class BaseCompanyRolePermission(BasePermission):
    """Base for a fixed-role permission check. Public (not `_`-prefixed)
    so other apps' module-specific role combos (e.g. apps/sales/permissions.py
    for "who can void an invoice") can extend it instead of re-implementing
    the same has_permission() logic."""

    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        company = getattr(request, "active_company", None)
        return user_has_role(request.user, company, *self.allowed_roles)


class IsCompanyMember(BaseCompanyRolePermission):
    """Any active role in the active company (baseline: at least readonly)."""

    allowed_roles = tuple(MembershipRole.values)


class IsCompanyOwner(BaseCompanyRolePermission):
    """Reserved for actions exclusive to the owner role (none defined yet)."""

    allowed_roles = (MembershipRole.OWNER,)


class IsCompanyAdmin(BaseCompanyRolePermission):
    """General company administration: owner and admin."""

    allowed_roles = MANAGEMENT_ROLES


class IsCompanyAccountant(BaseCompanyRolePermission):
    allowed_roles = (*MANAGEMENT_ROLES, MembershipRole.ACCOUNTANT)


class IsCompanySales(BaseCompanyRolePermission):
    allowed_roles = (*MANAGEMENT_ROLES, MembershipRole.SALES)


class IsCompanyPurchasing(BaseCompanyRolePermission):
    allowed_roles = (*MANAGEMENT_ROLES, MembershipRole.PURCHASING)
