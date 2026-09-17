import pytest
from django.test import Client
from django.urls import reverse

from apps.catalog.models import Product, ProductType
from apps.catalog.tests.factories import ProductFactory
from apps.companies.models import MembershipRole
from apps.companies.services import ACTIVE_COMPANY_SESSION_KEY
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def _client_for(user, company=None):
    client = Client()
    client.force_login(user)
    if company is not None:
        session = client.session
        session[ACTIVE_COMPANY_SESSION_KEY] = company.id
        session.save()
    return client


def test_detail_view_renders():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.READONLY)
    product = ProductFactory(company=company)
    client = _client_for(user, company)

    response = client.get(reverse("catalog:detail", args=[product.pk]))

    assert response.status_code == 200


def test_create_view_form_renders():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ADMIN)
    client = _client_for(user, company)

    response = client.get(reverse("catalog:create"))

    assert response.status_code == 200


def test_create_view_stamps_active_company():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ADMIN)
    client = _client_for(user, company)

    response = client.post(
        reverse("catalog:create"),
        {
            "sku": "SKU-1",
            "name": "Nuevo",
            "type": ProductType.GOOD,
            "unit_price": "10.00",
            "tax_rate": "0",
        },
    )

    assert response.status_code == 302
    product = Product.objects.get(sku="SKU-1")
    assert product.company_id == company.id


def test_update_view_404s_for_product_of_another_company():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    product_b = ProductFactory(company=company_b)
    client = _client_for(user_a, company_a)

    response = client.get(reverse("catalog:edit", args=[product_b.pk]))

    assert response.status_code == 404


def test_sales_role_cannot_access_create_view():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    client = _client_for(user, company)

    response = client.get(reverse("catalog:create"))

    assert response.status_code == 403


def test_sales_role_can_access_list_view():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    client = _client_for(user, company)

    response = client.get(reverse("catalog:list"))

    assert response.status_code == 200


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.ACCOUNTANT,
        MembershipRole.SALES,
        MembershipRole.PURCHASING,
        MembershipRole.READONLY,
    ],
)
def test_non_write_roles_cannot_access_edit_view(role):
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=role)
    product = ProductFactory(company=company)
    client = _client_for(user, company)

    response = client.get(reverse("catalog:edit", args=[product.pk]))

    assert response.status_code == 403


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.ACCOUNTANT,
        MembershipRole.SALES,
        MembershipRole.PURCHASING,
        MembershipRole.READONLY,
    ],
)
def test_non_write_roles_cannot_deactivate(role):
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=role)
    product = ProductFactory(company=company, is_active=True)
    client = _client_for(user, company)

    response = client.post(reverse("catalog:deactivate", args=[product.pk]))

    assert response.status_code == 403
    product.refresh_from_db()
    assert product.is_active is True


def test_admin_can_deactivate_product():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ADMIN)
    product = ProductFactory(company=company, is_active=True)
    client = _client_for(user, company)

    response = client.post(reverse("catalog:deactivate", args=[product.pk]))

    assert response.status_code == 302
    product.refresh_from_db()
    assert product.is_active is False


def test_deactivate_view_404s_for_foreign_company_product():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.ADMIN)
    product_b = ProductFactory(company=company_b)
    client = _client_for(user_a, company_a)

    response = client.post(reverse("catalog:deactivate", args=[product_b.pk]))

    assert response.status_code == 404
