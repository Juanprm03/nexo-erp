import pytest
from django.test import RequestFactory

from apps.companies.models import MembershipRole
from apps.companies.services import (
    ACTIVE_COMPANY_SESSION_KEY,
    CompanyAccessDenied,
    activate_company,
    get_active_membership,
    user_has_role,
)
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def _request():
    request = RequestFactory().get("/")
    request.session = {}
    return request


def test_user_can_activate_a_company_they_belong_to():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, is_active=True)
    request = _request()

    membership = activate_company(request, user, company)

    assert membership.company == company
    assert request.session[ACTIVE_COMPANY_SESSION_KEY] == company.id


def test_user_cannot_activate_a_foreign_company():
    user = UserFactory()
    own_company = CompanyFactory()
    foreign_company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=own_company, is_active=True)
    request = _request()

    with pytest.raises(CompanyAccessDenied):
        activate_company(request, user, foreign_company)

    assert ACTIVE_COMPANY_SESSION_KEY not in request.session


def test_inactive_membership_cannot_activate_company():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, is_active=False)
    request = _request()

    with pytest.raises(CompanyAccessDenied):
        activate_company(request, user, company)

    assert ACTIVE_COMPANY_SESSION_KEY not in request.session


def test_inactive_company_cannot_be_activated():
    """Regression: activation must reject a deactivated Company itself,
    not just a deactivated membership — otherwise it "succeeds" only for
    ActiveCompanyMiddleware to silently revert it on the very next
    request, since the middleware already re-checks company.is_active."""
    user = UserFactory()
    company = CompanyFactory(is_active=False)
    CompanyMembershipFactory(user=user, company=company, is_active=True)
    request = _request()

    with pytest.raises(CompanyAccessDenied):
        activate_company(request, user, company)

    assert ACTIVE_COMPANY_SESSION_KEY not in request.session


def test_get_active_membership_returns_none_for_anonymous_or_missing_company():
    user = UserFactory()

    assert get_active_membership(user, None) is None


def test_user_has_role_checks_active_membership_and_role():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ACCOUNTANT)

    assert user_has_role(user, company, MembershipRole.ACCOUNTANT) is True
    assert user_has_role(user, company, MembershipRole.SALES) is False


def test_user_has_role_is_false_for_inactive_membership():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(
        user=user, company=company, role=MembershipRole.ADMIN, is_active=False
    )

    assert user_has_role(user, company, MembershipRole.ADMIN) is False
