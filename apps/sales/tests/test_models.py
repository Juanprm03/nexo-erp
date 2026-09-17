import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.catalog.tests.factories import ProductFactory
from apps.companies.tests.factories import CompanyFactory, UserFactory
from apps.partners.tests.factories import PartnerFactory
from apps.sales.models import SalesInvoice, SalesInvoiceLine
from apps.sales.tests.factories import SalesInvoiceFactory, SalesInvoiceLineFactory

pytestmark = pytest.mark.django_db


def test_create_valid_draft_invoice():
    invoice = SalesInvoiceFactory()

    assert SalesInvoice.objects.count() == 1
    assert invoice.status == "draft"
    assert invoice.number == ""


def test_partner_must_be_customer():
    company = CompanyFactory()
    supplier_only = PartnerFactory(company=company, is_customer=False, is_supplier=True)
    invoice = SalesInvoice(
        company=company, partner=supplier_only, created_by=UserFactory()
    )

    with pytest.raises(ValidationError):
        invoice.full_clean(exclude=["number"])


def test_partner_must_belong_to_same_company():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    foreign_partner = PartnerFactory(company=company_b, is_customer=True)
    invoice = SalesInvoice(
        company=company_a, partner=foreign_partner, created_by=UserFactory()
    )

    with pytest.raises(ValidationError):
        invoice.full_clean(exclude=["number"])


def test_line_product_must_belong_to_same_company_as_invoice():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    invoice = SalesInvoiceFactory(company=company_a)
    foreign_product = ProductFactory(company=company_b)
    line = SalesInvoiceLine(
        company=company_a,
        invoice=invoice,
        product=foreign_product,
        quantity="1.00",
        unit_price="10.00",
        tax_rate="0",
        subtotal="10.00",
        tax_amount="0",
        total="10.00",
    )

    with pytest.raises(ValidationError):
        line.full_clean()


def test_quantity_must_be_positive():
    line = SalesInvoiceLineFactory.build(quantity="0")

    with pytest.raises(ValidationError):
        line.full_clean()


def test_quantity_zero_rejected_by_db_constraint():
    invoice = SalesInvoiceFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        SalesInvoiceLine.objects.create(
            company=invoice.company,
            invoice=invoice,
            product=ProductFactory(company=invoice.company),
            quantity="0",
            unit_price="10.00",
            tax_rate="0",
            subtotal="0",
            tax_amount="0",
            total="0",
        )


def test_unit_price_cannot_be_negative():
    line = SalesInvoiceLineFactory.build(unit_price="-1.00")

    with pytest.raises(ValidationError):
        line.full_clean()


def test_invoice_totals_cannot_be_negative_db_constraint():
    invoice = SalesInvoiceFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        SalesInvoice.objects.filter(pk=invoice.pk).update(total=-1)


def test_number_unique_per_company_when_present():
    company = CompanyFactory()
    SalesInvoiceFactory(company=company, number="INV-000001")

    with pytest.raises(IntegrityError), transaction.atomic():
        SalesInvoiceFactory(company=company, number="INV-000001")


def test_multiple_drafts_without_number_allowed_in_same_company():
    company = CompanyFactory()
    SalesInvoiceFactory(company=company, number="")
    SalesInvoiceFactory(company=company, number="")

    assert SalesInvoice.objects.filter(company=company, number="").count() == 2


def test_same_number_allowed_in_different_companies():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    SalesInvoiceFactory(company=company_a, number="INV-000001")
    SalesInvoiceFactory(company=company_b, number="INV-000001")

    assert SalesInvoice.objects.filter(number="INV-000001").count() == 2


def test_for_company_isolates_invoices():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    invoice_a = SalesInvoiceFactory(company=company_a)
    SalesInvoiceFactory(company=company_b)

    assert list(SalesInvoice.objects.for_company(company_a)) == [invoice_a]
