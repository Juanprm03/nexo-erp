import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from apps.companies.middleware import ActiveCompanyMiddleware
from apps.companies.services import ACTIVE_COMPANY_SESSION_KEY
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def _run_middleware(user, session):
    request = RequestFactory().get("/")
    request.user = user
    request.session = session
    ActiveCompanyMiddleware(get_response=lambda r: r)(request)
    return request


def test_resolves_active_company_from_valid_session():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, is_active=True)

    request = _run_middleware(user, {ACTIVE_COMPANY_SESSION_KEY: company.id})

    assert request.active_company == company


def test_anonymous_user_has_no_active_company():
    request = _run_middleware(AnonymousUser(), {})

    assert request.active_company is None


def test_no_active_company_without_session_key():
    user = UserFactory()

    request = _run_middleware(user, {})

    assert request.active_company is None


def test_revoked_membership_clears_active_company():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company, is_active=False)
    session = {ACTIVE_COMPANY_SESSION_KEY: company.id}

    request = _run_middleware(user, session)

    assert request.active_company is None
    assert ACTIVE_COMPANY_SESSION_KEY not in session


def test_deactivated_company_clears_active_company():
    user = UserFactory()
    company = CompanyFactory(is_active=False)
    CompanyMembershipFactory(user=user, company=company, is_active=True)
    session = {ACTIVE_COMPANY_SESSION_KEY: company.id}

    request = _run_middleware(user, session)

    assert request.active_company is None
    assert ACTIVE_COMPANY_SESSION_KEY not in session


def test_session_referencing_foreign_company_is_ignored():
    user = UserFactory()
    foreign_company = CompanyFactory()

    request = _run_middleware(user, {ACTIVE_COMPANY_SESSION_KEY: foreign_company.id})

    assert request.active_company is None
