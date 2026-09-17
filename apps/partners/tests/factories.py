import factory
from factory.django import DjangoModelFactory

from apps.companies.tests.factories import CompanyFactory
from apps.partners.models import Partner


class PartnerFactory(DjangoModelFactory):
    class Meta:
        model = Partner

    company = factory.SubFactory(CompanyFactory)
    name = factory.Sequence(lambda n: f"Partner {n}")
    is_customer = True
    is_supplier = False
