import pytest
from django.db import IntegrityError, transaction

from apps.companies.models import Company, CompanyMembership, MembershipRole
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_create_company():
    company = CompanyFactory(name="Acme SAS", tax_id="900123456-7")

    assert Company.objects.count() == 1
    assert company.is_active is True
    assert company.created_at is not None
    assert company.updated_at is not None


def test_create_company_membership():
    membership = CompanyMembershipFactory(role=MembershipRole.ADMIN)

    assert CompanyMembership.objects.count() == 1
    assert membership.role == MembershipRole.ADMIN
    assert membership.is_active is True


def test_membership_unique_per_user_and_company():
    user = UserFactory()
    company = CompanyFactory()
    CompanyMembershipFactory(user=user, company=company)

    with pytest.raises(IntegrityError), transaction.atomic():
        CompanyMembershipFactory(user=user, company=company)


def test_membership_role_must_be_a_valid_choice():
    membership = CompanyMembershipFactory(role=MembershipRole.SALES)

    assert membership.role in MembershipRole.values


def test_same_user_can_belong_to_multiple_companies():
    user = UserFactory()
    company_a = CompanyFactory()
    company_b = CompanyFactory()

    CompanyMembershipFactory(user=user, company=company_a)
    CompanyMembershipFactory(user=user, company=company_b)

    assert CompanyMembership.objects.filter(user=user).count() == 2
