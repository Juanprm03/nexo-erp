import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.catalog.models import Product, ProductType
from apps.catalog.tests.factories import ProductFactory
from apps.companies.tests.factories import CompanyFactory

pytestmark = pytest.mark.django_db


def test_create_valid_product():
    product = ProductFactory()

    assert Product.objects.count() == 1
    assert product.is_active is True


def test_sku_unique_per_company_db_constraint():
    company = CompanyFactory()
    ProductFactory(company=company, sku="SKU-1")

    with pytest.raises(IntegrityError), transaction.atomic():
        ProductFactory(company=company, sku="SKU-1")


def test_sku_unique_per_company_model_clean():
    company = CompanyFactory()
    ProductFactory(company=company, sku="SKU-1")
    duplicate = Product(
        company=company, sku="SKU-1", name="Otro", type=ProductType.GOOD, unit_price="1.00"
    )

    with pytest.raises(ValidationError):
        duplicate.full_clean()


def test_same_sku_different_company_allowed():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    ProductFactory(company=company_a, sku="SKU-1")
    ProductFactory(company=company_b, sku="SKU-1")

    assert Product.objects.filter(sku="SKU-1").count() == 2


def test_unit_price_cannot_be_negative_model_clean():
    product = Product(
        company=CompanyFactory(), sku="X", name="X", type=ProductType.GOOD, unit_price="-1.00"
    )

    with pytest.raises(ValidationError):
        product.full_clean()


def test_unit_price_cannot_be_negative_db_constraint():
    company = CompanyFactory()

    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.create(
            company=company, sku="X", name="X", type=ProductType.GOOD, unit_price="-1.00"
        )


def test_tax_rate_cannot_be_negative_model_clean():
    product = Product(
        company=CompanyFactory(),
        sku="X",
        name="X",
        type=ProductType.GOOD,
        unit_price="1.00",
        tax_rate="-1.00",
    )

    with pytest.raises(ValidationError):
        product.full_clean()


def test_tax_rate_cannot_be_negative_db_constraint():
    company = CompanyFactory()

    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.create(
            company=company,
            sku="X",
            name="X",
            type=ProductType.GOOD,
            unit_price="1.00",
            tax_rate="-1.00",
        )


def test_for_company_isolates_products():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    product_a = ProductFactory(company=company_a)
    ProductFactory(company=company_b)

    assert list(Product.objects.for_company(company_a)) == [product_a]
