import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.companies.tests.factories import CompanyFactory
from apps.partners.models import Partner
from apps.partners.tests.factories import PartnerFactory

pytestmark = pytest.mark.django_db


def test_create_valid_partner():
    partner = PartnerFactory(name="Acme", is_customer=True)

    assert Partner.objects.count() == 1
    assert partner.is_active is True


def test_requires_customer_or_supplier_model_clean():
    partner = Partner(company=CompanyFactory(), name="Nadie", is_customer=False, is_supplier=False)

    with pytest.raises(ValidationError):
        partner.full_clean()


def test_requires_customer_or_supplier_db_constraint():
    company = CompanyFactory()

    with pytest.raises(IntegrityError), transaction.atomic():
        Partner.objects.create(company=company, name="Nadie", is_customer=False, is_supplier=False)


def test_can_be_both_customer_and_supplier():
    partner = PartnerFactory(is_customer=True, is_supplier=True)

    partner.full_clean()
    assert partner.is_customer and partner.is_supplier


def test_duplicate_tax_id_same_company_fails_db_constraint():
    company = CompanyFactory()
    PartnerFactory(company=company, tax_id="900123456")

    with pytest.raises(IntegrityError), transaction.atomic():
        PartnerFactory(company=company, tax_id="900123456")


def test_duplicate_tax_id_same_company_fails_model_clean():
    """Django's automatic validate_unique() skips UniqueConstraints with a
    `condition` (our partial index), so Partner.clean() must raise this
    itself — this locks in that it actually does."""
    company = CompanyFactory()
    PartnerFactory(company=company, tax_id="900123456")
    duplicate = Partner(company=company, name="Otro", tax_id="900123456", is_customer=True)

    with pytest.raises(ValidationError):
        duplicate.full_clean()


def test_same_tax_id_different_company_allowed():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    PartnerFactory(company=company_a, tax_id="900123456")
    PartnerFactory(company=company_b, tax_id="900123456")

    assert Partner.objects.filter(tax_id="900123456").count() == 2


def test_multiple_partners_without_tax_id_allowed_in_same_company():
    company = CompanyFactory()
    PartnerFactory(company=company, tax_id="")
    PartnerFactory(company=company, tax_id="")

    assert Partner.objects.filter(company=company, tax_id="").count() == 2


def test_for_company_isolates_partners():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    partner_a = PartnerFactory(company=company_a)
    PartnerFactory(company=company_b)

    assert list(Partner.objects.for_company(company_a)) == [partner_a]
