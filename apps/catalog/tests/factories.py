import factory
from factory.django import DjangoModelFactory

from apps.catalog.models import Product, ProductType
from apps.companies.tests.factories import CompanyFactory


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    company = factory.SubFactory(CompanyFactory)
    sku = factory.Sequence(lambda n: f"SKU-{n}")
    name = factory.Sequence(lambda n: f"Product {n}")
    type = ProductType.GOOD
    unit_price = "100.00"
    tax_rate = "19.00"
