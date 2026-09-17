import pytest
from django.urls import reverse

from apps.catalog.models import Product, ProductType
from apps.catalog.tests.factories import ProductFactory
from apps.companies.models import MembershipRole
from apps.companies.tests.api_helpers import api_client_for
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("product-list")


def _detail_url(product):
    return reverse("product-detail", args=[product.pk])


def test_create_ignores_client_supplied_company():
    company = CompanyFactory()
    other_company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ADMIN)
    client = api_client_for(user, company)

    response = client.post(
        LIST_URL,
        {
            "sku": "SKU-1",
            "name": "Producto",
            "type": ProductType.GOOD,
            "unit_price": "10.00",
            "tax_rate": "19.00",
            "company": other_company.id,
        },
    )

    assert response.status_code == 201, response.data
    product = Product.objects.get(pk=response.data["id"])
    assert product.company_id == company.id


def test_negative_unit_price_rejected_via_api():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ADMIN)
    client = api_client_for(user, company)

    response = client.post(
        LIST_URL,
        {"sku": "SKU-1", "name": "Producto", "type": ProductType.GOOD, "unit_price": "-1.00"},
    )

    assert response.status_code == 400
    assert "unit_price" in response.data


def test_negative_tax_rate_rejected_via_api():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ADMIN)
    client = api_client_for(user, company)

    response = client.post(
        LIST_URL,
        {
            "sku": "SKU-1",
            "name": "Producto",
            "type": ProductType.GOOD,
            "unit_price": "10.00",
            "tax_rate": "-1.00",
        },
    )

    assert response.status_code == 400
    assert "tax_rate" in response.data


def test_isolation_between_companies_via_api():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    product_a = ProductFactory(company=company_a)
    ProductFactory(company=company_b)
    client = api_client_for(user_a, company_a)

    response = client.get(LIST_URL)

    ids = [item["id"] for item in response.data["results"]]
    assert ids == [product_a.id]


def test_user_of_company_a_cannot_read_product_of_company_b():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    product_b = ProductFactory(company=company_b)
    client = api_client_for(user_a, company_a)

    response = client.get(_detail_url(product_b))

    assert response.status_code == 404


@pytest.mark.parametrize(
    "role,can_write",
    [
        (MembershipRole.OWNER, True),
        (MembershipRole.ADMIN, True),
        (MembershipRole.ACCOUNTANT, False),
        (MembershipRole.SALES, False),
        (MembershipRole.PURCHASING, False),
        (MembershipRole.READONLY, False),
    ],
)
def test_role_permissions_for_products(role, can_write):
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=role)
    client = api_client_for(user, company)

    read_response = client.get(LIST_URL)
    assert read_response.status_code == 200

    create_response = client.post(
        LIST_URL,
        {"sku": "SKU-X", "name": "X", "type": ProductType.GOOD, "unit_price": "1.00"},
    )
    assert (create_response.status_code == 201) is can_write


@pytest.mark.parametrize(
    "role,can_write",
    [
        (MembershipRole.OWNER, True),
        (MembershipRole.ADMIN, True),
        (MembershipRole.ACCOUNTANT, False),
        (MembershipRole.SALES, False),
        (MembershipRole.PURCHASING, False),
        (MembershipRole.READONLY, False),
    ],
)
def test_role_permissions_for_products_via_patch(role, can_write):
    """PATCH must follow the same write policy as POST."""
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=role)
    product = ProductFactory(company=company, name="Original")
    client = api_client_for(user, company)

    response = client.patch(_detail_url(product), {"name": "Modificado"})

    assert (response.status_code == 200) is can_write
    product.refresh_from_db()
    assert product.name == ("Modificado" if can_write else "Original")


def test_update_ignores_client_supplied_company():
    company = CompanyFactory()
    other_company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ADMIN)
    product = ProductFactory(company=company)
    client = api_client_for(user, company)

    response = client.patch(_detail_url(product), {"company": other_company.id})

    assert response.status_code == 200, response.data
    product.refresh_from_db()
    assert product.company_id == company.id
