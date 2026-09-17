import pytest
from django.test import Client
from django.urls import reverse

from apps.companies.models import MembershipRole
from apps.companies.services import ACTIVE_COMPANY_SESSION_KEY
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory
from apps.partners.models import Partner
from apps.partners.tests.factories import PartnerFactory

pytestmark = pytest.mark.django_db


def _client_for(user, company=None):
    client = Client()
    client.force_login(user)
    if company is not None:
        session = client.session
        session[ACTIVE_COMPANY_SESSION_KEY] = company.id
        session.save()
    return client


def test_list_view_renders():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.READONLY)
    PartnerFactory(company=company)
    client = _client_for(user, company)

    response = client.get(reverse("partners:list"))

    assert response.status_code == 200


def test_detail_view_renders():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.READONLY)
    partner = PartnerFactory(company=company)
    client = _client_for(user, company)

    response = client.get(reverse("partners:detail", args=[partner.pk]))

    assert response.status_code == 200


def test_create_view_stamps_active_company():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ADMIN)
    client = _client_for(user, company)

    response = client.post(reverse("partners:create"), {"name": "Nuevo", "is_customer": "on"})

    assert response.status_code == 302
    partner = Partner.objects.get(name="Nuevo")
    assert partner.company_id == company.id


def test_create_view_rejects_duplicate_tax_id_with_form_error_not_500():
    """Regression test for the CompanyScopedFormMixin fix: without
    pre-stamping company in get_form_kwargs(), this used to reach
    Partner.clean() with company_id=None (skipping the duplicate check)
    and blow up as an unhandled IntegrityError on save()."""
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ADMIN)
    PartnerFactory(company=company, tax_id="900123456")
    client = _client_for(user, company)

    response = client.post(
        reverse("partners:create"),
        {"name": "Duplicado", "is_customer": "on", "tax_id": "900123456"},
    )

    assert response.status_code == 200
    assert "tax_id" in response.context["form"].errors
    assert Partner.objects.filter(tax_id="900123456").count() == 1


def test_update_view_404s_for_partner_of_another_company():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    partner_b = PartnerFactory(company=company_b)
    client = _client_for(user_a, company_a)

    response = client.get(reverse("partners:edit", args=[partner_b.pk]))

    assert response.status_code == 404


def test_readonly_role_cannot_access_create_view():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.READONLY)
    client = _client_for(user, company)

    response = client.get(reverse("partners:create"))

    assert response.status_code == 403


def test_list_view_requires_active_company():
    user = UserFactory()
    client = _client_for(user)

    response = client.get(reverse("partners:list"))

    assert response.status_code == 403


def test_deactivate_view_sets_partner_inactive():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ADMIN)
    partner = PartnerFactory(company=company, is_active=True)
    client = _client_for(user, company)

    response = client.post(reverse("partners:deactivate", args=[partner.pk]))

    assert response.status_code == 302
    partner.refresh_from_db()
    assert partner.is_active is False


@pytest.mark.parametrize(
    "role", [MembershipRole.SALES, MembershipRole.PURCHASING, MembershipRole.READONLY]
)
def test_non_write_roles_cannot_access_edit_view(role):
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=role)
    partner = PartnerFactory(company=company)
    client = _client_for(user, company)

    response = client.get(reverse("partners:edit", args=[partner.pk]))

    assert response.status_code == 403


@pytest.mark.parametrize(
    "role", [MembershipRole.SALES, MembershipRole.PURCHASING, MembershipRole.READONLY]
)
def test_non_write_roles_cannot_deactivate(role):
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=role)
    partner = PartnerFactory(company=company, is_active=True)
    client = _client_for(user, company)

    response = client.post(reverse("partners:deactivate", args=[partner.pk]))

    assert response.status_code == 403
    partner.refresh_from_db()
    assert partner.is_active is True


def test_deactivate_view_404s_for_foreign_company_partner():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.ADMIN)
    partner_b = PartnerFactory(company=company_b)
    client = _client_for(user_a, company_a)

    response = client.post(reverse("partners:deactivate", args=[partner_b.pk]))

    assert response.status_code == 404
