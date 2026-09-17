"""Tests for CompanyScopedModel / CompanyScopedQuerySet.

Uses CompanyMembership as the concrete CompanyScopedModel under test,
since no business resource (Partner, Product, ...) exists yet.
"""

import pytest

from apps.companies.models import CompanyMembership
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_for_company_returns_only_matching_company_records():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    membership_a = CompanyMembershipFactory(company=company_a)
    CompanyMembershipFactory(company=company_b)

    result = CompanyMembership.objects.for_company(company_a)

    assert list(result) == [membership_a]


def test_for_company_returns_empty_for_company_without_records():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    CompanyMembershipFactory(company=company_a)

    assert CompanyMembership.objects.for_company(company_b).count() == 0


def test_default_manager_is_not_scoped_automatically():
    """The manager must NOT filter silently — .all() sees every company."""
    CompanyMembershipFactory(company=CompanyFactory())
    CompanyMembershipFactory(company=CompanyFactory())

    assert CompanyMembership.objects.all().count() == 2


def test_cross_company_isolation_base_case():
    user_a = UserFactory()
    user_b = UserFactory()
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    membership_a = CompanyMembershipFactory(user=user_a, company=company_a)
    membership_b = CompanyMembershipFactory(user=user_b, company=company_b)

    scoped_to_a = CompanyMembership.objects.for_company(company_a)
    scoped_to_b = CompanyMembership.objects.for_company(company_b)

    assert membership_a in scoped_to_a
    assert membership_a not in scoped_to_b
    assert membership_b in scoped_to_b
    assert membership_b not in scoped_to_a
