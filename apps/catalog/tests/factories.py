from decimal import Decimal

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
    # Decimal, not str: Model.objects.create() does not coerce field values
    # in-memory (only on the way to/from the DB), so a str literal here
    # would silently stay a str on the returned instance — harmless until
    # something does real arithmetic on product.unit_price, as
    # apps/sales/services.py now does.
    unit_price = Decimal("100.00")
    tax_rate = Decimal("19.00")
