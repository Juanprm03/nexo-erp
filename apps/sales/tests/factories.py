from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from apps.catalog.tests.factories import ProductFactory
from apps.companies.tests.factories import CompanyFactory, UserFactory
from apps.partners.tests.factories import PartnerFactory
from apps.sales.models import SalesInvoice, SalesInvoiceLine


class SalesInvoiceFactory(DjangoModelFactory):
    class Meta:
        model = SalesInvoice

    company = factory.SubFactory(CompanyFactory)
    # SubFactory + SelfAttribute (not a LazyAttribute wrapping a raw
    # PartnerFactory(...) call) so `.build()` propagates correctly: a
    # LazyAttribute calling a factory directly always forces the `create`
    # strategy regardless of the parent's, which blows up under `.build()`
    # with "unsaved related object" once `company` itself is unsaved too.
    partner = factory.SubFactory(
        PartnerFactory, company=factory.SelfAttribute("..company"), is_customer=True
    )
    created_by = factory.SubFactory(UserFactory)


class SalesInvoiceLineFactory(DjangoModelFactory):
    class Meta:
        model = SalesInvoiceLine

    invoice = factory.SubFactory(SalesInvoiceFactory)
    company = factory.LazyAttribute(lambda o: o.invoice.company)
    product = factory.SubFactory(
        ProductFactory, company=factory.SelfAttribute("..invoice.company")
    )
    quantity = Decimal("1.00")
    unit_price = Decimal("100.00")
    tax_rate = Decimal("19.00")
    subtotal = Decimal("100.00")
    tax_amount = Decimal("19.00")
    total = Decimal("119.00")
