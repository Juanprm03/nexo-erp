import pytest
from django.test import RequestFactory

from apps.companies.models import MembershipRole
from apps.companies.permissions import (
    HasActiveCompany,
    IsCompanyAccountant,
    IsCompanyAdmin,
    IsCompanyMember,
    IsCompanyOwner,
    IsCompanyPurchasing,
    IsCompanySales,
    IsSameCompanyObject,
)
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def _request(user, active_company):
    request = RequestFactory().get("/")
    request.user = user
    request.active_company = active_company
    return request


def test_has_active_company_permission():
    user = UserFactory()
    company = CompanyFactory()

    assert HasActiveCompany().has_permission(_request(user, company), view=None) is True
    assert HasActiveCompany().has_permission(_request(user, None), view=None) is False


@pytest.mark.parametrize(
    "permission_class,granted_role",
    [
        (IsCompanyAdmin, MembershipRole.OWNER),
        (IsCompanyAdmin, MembershipRole.ADMIN),
        (IsCompanyAccountant, MembershipRole.ACCOUNTANT),
        (IsCompanySales, MembershipRole.SALES),
        (IsCompanyPurchasing, MembershipRole.PURCHASING),
        (IsCompanyMember, MembershipRole.READONLY),
    ],
)
def test_role_permission_grants_access_for_matching_role(permission_class, granted_role):
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, role=granted_role)

    assert permission_class().has_permission(_request(user, company), view=None) is True


@pytest.mark.parametrize(
    "permission_class",
    [IsCompanyAdmin, IsCompanyAccountant, IsCompanySales, IsCompanyPurchasing],
)
@pytest.mark.parametrize("management_role", [MembershipRole.OWNER, MembershipRole.ADMIN])
def test_management_roles_are_never_locked_out_of_operational_permissions(
    permission_class, management_role
):
    """Regression guard: owner/admin must pass every operational permission
    class, since they sit above accountant/sales/purchasing in the
    hierarchy (see MANAGEMENT_ROLES)."""
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, role=management_role)

    assert permission_class().has_permission(_request(user, company), view=None) is True


def test_is_company_owner_rejects_admin():
    """Owner-exclusive actions must not grant access to admin."""
    owner = UserFactory()
    admin = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=owner, company=company, role=MembershipRole.OWNER)
    CompanyMembershipFactory(user=admin, company=company, role=MembershipRole.ADMIN)

    assert IsCompanyOwner().has_permission(_request(owner, company), view=None) is True
    assert IsCompanyOwner().has_permission(_request(admin, company), view=None) is False


def test_role_permission_denies_access_for_unrelated_role():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.READONLY)

    assert IsCompanyAdmin().has_permission(_request(user, company), view=None) is False


def test_role_permission_denies_access_without_active_company():
    user = UserFactory()
    CompanyMembershipFactory(user=user, role=MembershipRole.ADMIN)

    assert IsCompanyAdmin().has_permission(_request(user, None), view=None) is False


def test_is_same_company_object_accepts_matching_company():
    company = CompanyFactory()
    membership = CompanyMembershipFactory(company=company)
    request = _request(membership.user, company)

    assert IsSameCompanyObject().has_object_permission(request, view=None, obj=membership) is True


def test_is_same_company_object_rejects_foreign_company():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    membership = CompanyMembershipFactory(company=company_a)
    request = _request(membership.user, company_b)

    assert IsSameCompanyObject().has_object_permission(request, view=None, obj=membership) is False
