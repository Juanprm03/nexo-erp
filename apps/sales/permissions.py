"""Sales-specific authorization: who can write/issue vs void invoices.

- owner/admin: full access (drafts, issue, void).
- sales: create/edit drafts and issue, but NOT void — voiding a live
  invoice is treated as a financial-control action, not a day-to-day
  sales one.
- accountant: read-only over sales data, but CAN void an issued invoice
  — that's the financial-control action they own.
- purchasing/readonly: read-only, no exceptions.

This is a fixed, hardcoded split (no dynamic permission matrix), matching
the project-wide convention in apps/companies/permissions.py.
"""

from apps.companies.models import MANAGEMENT_ROLES, MembershipRole
from apps.companies.permissions import BaseCompanyRolePermission

SALES_WRITE_ROLES = (*MANAGEMENT_ROLES, MembershipRole.SALES)
SALES_VOID_ROLES = (*MANAGEMENT_ROLES, MembershipRole.ACCOUNTANT)


class CanWriteSalesInvoice(BaseCompanyRolePermission):
    """Create/edit drafts and issue."""

    allowed_roles = SALES_WRITE_ROLES


class CanVoidSalesInvoice(BaseCompanyRolePermission):
    allowed_roles = SALES_VOID_ROLES
