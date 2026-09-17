import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.companies.models import MembershipRole
from apps.companies.tests.api_helpers import api_client_for
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory
from apps.partners.models import Partner
from apps.partners.tests.factories import PartnerFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("partner-list")


def _detail_url(partner):
    return reverse("partner-detail", args=[partner.pk])


def test_create_ignores_client_supplied_company():
    company = CompanyFactory()
    other_company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ACCOUNTANT)
    client = api_client_for(user, company)

    response = client.post(
        LIST_URL,
        {"name": "Cliente Nuevo", "is_customer": True, "company": other_company.id},
    )

    assert response.status_code == 201, response.data
    partner = Partner.objects.get(pk=response.data["id"])
    assert partner.company_id == company.id


def test_requires_customer_or_supplier_via_api():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ACCOUNTANT)
    client = api_client_for(user, company)

    response = client.post(LIST_URL, {"name": "Nadie"})

    assert response.status_code == 400


def test_list_only_returns_active_company_partners():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    partner_a = PartnerFactory(company=company_a)
    PartnerFactory(company=company_b)
    client = api_client_for(user_a, company_a)

    response = client.get(LIST_URL)

    assert response.status_code == 200
    ids = [item["id"] for item in response.data["results"]]
    assert ids == [partner_a.id]


def test_user_of_company_a_cannot_read_partner_of_company_b():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    partner_b = PartnerFactory(company=company_b)
    client = api_client_for(user_a, company_a)

    response = client.get(_detail_url(partner_b))

    assert response.status_code == 404


def test_user_of_company_a_cannot_update_partner_of_company_b():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    partner_b = PartnerFactory(company=company_b, name="Original")
    client = api_client_for(user_a, company_a)

    response = client.patch(_detail_url(partner_b), {"name": "Hackeado"})

    assert response.status_code == 404
    partner_b.refresh_from_db()
    assert partner_b.name == "Original"


def test_request_without_active_company_is_rejected():
    user = UserFactory()
    CompanyMembershipFactory(user=user, role=MembershipRole.OWNER)
    client = APIClient()
    client.force_login(user)

    response = client.get(LIST_URL)

    assert response.status_code == 403


@pytest.mark.parametrize(
    "role,can_read,can_write",
    [
        (MembershipRole.OWNER, True, True),
        (MembershipRole.ADMIN, True, True),
        (MembershipRole.ACCOUNTANT, True, True),
        (MembershipRole.SALES, True, False),
        (MembershipRole.PURCHASING, True, False),
        (MembershipRole.READONLY, True, False),
    ],
)
def test_role_permissions_for_partners(role, can_read, can_write):
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=role)
    client = api_client_for(user, company)

    list_response = client.get(LIST_URL)
    assert (list_response.status_code == 200) is can_read

    create_response = client.post(LIST_URL, {"name": "Nuevo", "is_customer": True})
    assert (create_response.status_code == 201) is can_write


@pytest.mark.parametrize(
    "role,can_write",
    [
        (MembershipRole.OWNER, True),
        (MembershipRole.ADMIN, True),
        (MembershipRole.ACCOUNTANT, True),
        (MembershipRole.SALES, False),
        (MembershipRole.PURCHASING, False),
        (MembershipRole.READONLY, False),
    ],
)
def test_role_permissions_for_partners_via_patch(role, can_write):
    """PATCH must follow the same write policy as POST — `self.action`
    for partial_update is not "create", so this isn't automatically
    guaranteed by the create-only test above."""
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=role)
    partner = PartnerFactory(company=company, name="Original")
    client = api_client_for(user, company)

    response = client.patch(_detail_url(partner), {"name": "Modificado"})

    assert (response.status_code == 200) is can_write
    partner.refresh_from_db()
    assert partner.name == ("Modificado" if can_write else "Original")


def test_update_ignores_client_supplied_company():
    company = CompanyFactory()
    other_company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.OWNER)
    partner = PartnerFactory(company=company)
    client = api_client_for(user, company)

    response = client.patch(_detail_url(partner), {"company": other_company.id})

    assert response.status_code == 200, response.data
    partner.refresh_from_db()
    assert partner.company_id == company.id
