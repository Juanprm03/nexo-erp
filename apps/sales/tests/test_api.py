from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.tests.factories import ProductFactory
from apps.companies.models import MembershipRole
from apps.companies.tests.api_helpers import api_client_for
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory
from apps.partners.tests.factories import PartnerFactory
from apps.sales.models import InvoiceStatus, SalesInvoice, SalesInvoiceLine
from apps.sales.tests.factories import SalesInvoiceFactory, SalesInvoiceLineFactory

pytestmark = pytest.mark.django_db

INVOICE_LIST_URL = reverse("salesinvoice-list")
LINE_LIST_URL = reverse("salesinvoiceline-list")


def _invoice_detail_url(invoice):
    return reverse("salesinvoice-detail", args=[invoice.pk])


def _issue_url(invoice):
    return reverse("salesinvoice-issue", args=[invoice.pk])


def _void_url(invoice):
    return reverse("salesinvoice-void", args=[invoice.pk])


def _line_detail_url(line):
    return reverse("salesinvoiceline-detail", args=[line.pk])


# --- create / field protection -------------------------------------------


def test_create_draft_via_api():
    company = CompanyFactory()
    partner = PartnerFactory(company=company, is_customer=True)
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    client = api_client_for(user, company)

    response = client.post(INVOICE_LIST_URL, {"partner": partner.id})

    assert response.status_code == 201, response.data
    invoice = SalesInvoice.objects.get(pk=response.data["id"])
    assert invoice.status == InvoiceStatus.DRAFT
    assert invoice.created_by_id == user.id
    assert invoice.company_id == company.id


def test_create_ignores_client_supplied_company_created_by_status_and_totals():
    company = CompanyFactory()
    other_company = CompanyFactory()
    partner = PartnerFactory(company=company, is_customer=True)
    user = UserFactory()
    other_user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    client = api_client_for(user, company)

    response = client.post(
        INVOICE_LIST_URL,
        {
            "partner": partner.id,
            "company": other_company.id,
            "created_by": other_user.id,
            "status": InvoiceStatus.PAID,
            "number": "INV-999999",
            "subtotal": "999.00",
            "tax_total": "999.00",
            "total": "999.00",
        },
    )

    assert response.status_code == 201, response.data
    invoice = SalesInvoice.objects.get(pk=response.data["id"])
    assert invoice.company_id == company.id
    assert invoice.created_by_id == user.id
    assert invoice.status == InvoiceStatus.DRAFT
    assert invoice.number == ""
    assert invoice.subtotal == Decimal("0")
    assert invoice.total == Decimal("0")


def test_partner_of_another_company_rejected():
    company = CompanyFactory()
    other_company = CompanyFactory()
    foreign_partner = PartnerFactory(company=other_company, is_customer=True)
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    client = api_client_for(user, company)

    response = client.post(INVOICE_LIST_URL, {"partner": foreign_partner.id})

    assert response.status_code == 400


def test_non_customer_partner_rejected():
    company = CompanyFactory()
    supplier_only = PartnerFactory(company=company, is_customer=False, is_supplier=True)
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    client = api_client_for(user, company)

    response = client.post(INVOICE_LIST_URL, {"partner": supplier_only.id})

    assert response.status_code == 400


def test_update_ignores_client_supplied_status_and_totals():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    client = api_client_for(user, company)

    response = client.patch(
        _invoice_detail_url(invoice),
        {"status": InvoiceStatus.PAID, "total": "500.00"},
    )

    assert response.status_code == 200, response.data
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.DRAFT
    assert invoice.total == Decimal("0")


# --- lines -----------------------------------------------------------------


def test_add_line_via_api_snapshots_product_price():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    product = ProductFactory(company=company, unit_price="25.00", tax_rate="19.00")
    client = api_client_for(user, company)

    response = client.post(
        LINE_LIST_URL, {"invoice": invoice.pk, "product": product.pk, "quantity": "2"}
    )

    assert response.status_code == 201, response.data
    line = SalesInvoiceLine.objects.get(pk=response.data["id"])
    assert line.unit_price == Decimal("25.00")
    assert line.subtotal == Decimal("50.00")
    assert line.tax_amount == Decimal("9.50")


def test_add_line_rejects_product_of_another_company():
    company = CompanyFactory()
    other_company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    foreign_product = ProductFactory(company=other_company)
    client = api_client_for(user, company)

    response = client.post(
        LINE_LIST_URL, {"invoice": invoice.pk, "product": foreign_product.pk, "quantity": "1"}
    )

    assert response.status_code == 400


def test_add_line_rejects_invoice_of_another_company():
    company = CompanyFactory()
    other_company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    foreign_invoice = SalesInvoiceFactory(company=other_company)
    product = ProductFactory(company=company)
    client = api_client_for(user, company)

    response = client.post(
        LINE_LIST_URL, {"invoice": foreign_invoice.pk, "product": product.pk, "quantity": "1"}
    )

    assert response.status_code == 400


def test_cannot_add_line_to_issued_invoice_via_api():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    product = ProductFactory(company=company)
    client = api_client_for(user, company)
    client.post(LINE_LIST_URL, {"invoice": invoice.pk, "product": product.pk, "quantity": "1"})
    client.post(_issue_url(invoice), {})

    response = client.post(
        LINE_LIST_URL, {"invoice": invoice.pk, "product": product.pk, "quantity": "1"}
    )

    assert response.status_code == 400


def test_delete_line_via_api():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    line = SalesInvoiceLineFactory(invoice=invoice, company=company)
    client = api_client_for(user, company)

    response = client.delete(_line_detail_url(line))

    assert response.status_code == 204
    assert not SalesInvoiceLine.objects.filter(pk=line.pk).exists()


# --- issue / void ------------------------------------------------------------


def test_issue_via_api():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    product = ProductFactory(company=company, unit_price="10.00", tax_rate="0")
    client = api_client_for(user, company)
    client.post(LINE_LIST_URL, {"invoice": invoice.pk, "product": product.pk, "quantity": "1"})

    response = client.post(_issue_url(invoice))

    assert response.status_code == 200, response.data
    assert response.data["status"] == InvoiceStatus.ISSUED
    assert response.data["number"] == "INV-000001"


def test_issue_without_lines_fails_via_api():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    client = api_client_for(user, company)

    response = client.post(_issue_url(invoice))

    assert response.status_code == 400


def test_void_via_api():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ACCOUNTANT)
    invoice = SalesInvoiceFactory(company=company, status=InvoiceStatus.ISSUED, number="INV-000001")

    client = api_client_for(user, company)
    response = client.post(_void_url(invoice))

    assert response.status_code == 200, response.data
    assert response.data["status"] == InvoiceStatus.VOID


def test_sales_role_cannot_void():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company, status=InvoiceStatus.ISSUED, number="INV-000001")
    client = api_client_for(user, company)

    response = client.post(_void_url(invoice))

    assert response.status_code == 403


def test_accountant_cannot_issue():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ACCOUNTANT)
    invoice = SalesInvoiceFactory(company=company)
    product = ProductFactory(company=company)
    client = api_client_for(user, company)
    # Line added directly (bypassing permission) to isolate the issue-permission check.
    SalesInvoiceLineFactory(invoice=invoice, company=company, product=product)

    response = client.post(_issue_url(invoice))

    assert response.status_code == 403


# --- multiempresa isolation --------------------------------------------------


def test_user_of_company_a_cannot_read_invoice_of_company_b():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    invoice_b = SalesInvoiceFactory(company=company_b)
    client = api_client_for(user_a, company_a)

    response = client.get(_invoice_detail_url(invoice_b))

    assert response.status_code == 404


def test_user_of_company_a_cannot_update_invoice_of_company_b():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    invoice_b = SalesInvoiceFactory(company=company_b)
    client = api_client_for(user_a, company_a)

    response = client.patch(_invoice_detail_url(invoice_b), {"due_date": "2030-01-01"})

    assert response.status_code == 404


def test_list_only_returns_active_company_invoices():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    invoice_a = SalesInvoiceFactory(company=company_a)
    SalesInvoiceFactory(company=company_b)
    client = api_client_for(user_a, company_a)

    response = client.get(INVOICE_LIST_URL)

    ids = [item["id"] for item in response.data["results"]]
    assert ids == [invoice_a.id]


def test_lines_of_other_company_invoice_not_readable():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.OWNER)
    invoice_b = SalesInvoiceFactory(company=company_b)
    line_b = SalesInvoiceLineFactory(invoice=invoice_b, company=company_b)
    client = api_client_for(user_a, company_a)

    response = client.get(_line_detail_url(line_b))

    assert response.status_code == 404


# --- permissions matrix -------------------------------------------------------


@pytest.mark.parametrize(
    "role,can_write,can_issue",
    [
        (MembershipRole.OWNER, True, True),
        (MembershipRole.ADMIN, True, True),
        (MembershipRole.SALES, True, True),
        (MembershipRole.ACCOUNTANT, False, False),
        (MembershipRole.PURCHASING, False, False),
        (MembershipRole.READONLY, False, False),
    ],
)
def test_role_permissions_for_invoice_write_and_issue(role, can_write, can_issue):
    company = CompanyFactory()
    partner = PartnerFactory(company=company, is_customer=True)
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=role)
    client = api_client_for(user, company)

    read_response = client.get(INVOICE_LIST_URL)
    assert read_response.status_code == 200

    create_response = client.post(INVOICE_LIST_URL, {"partner": partner.id})
    assert (create_response.status_code == 201) is can_write

    if create_response.status_code == 201:
        created_invoice = SalesInvoice.objects.get(pk=create_response.data["id"])
        product = ProductFactory(company=company, unit_price="1.00", tax_rate="0")
        SalesInvoiceLineFactory(invoice=created_invoice, company=company, product=product)
        issue_response = client.post(reverse("salesinvoice-issue", args=[created_invoice.pk]))
        assert (issue_response.status_code == 200) is can_issue


@pytest.mark.parametrize(
    "role,can_void",
    [
        (MembershipRole.OWNER, True),
        (MembershipRole.ADMIN, True),
        (MembershipRole.ACCOUNTANT, True),
        (MembershipRole.SALES, False),
        (MembershipRole.PURCHASING, False),
        (MembershipRole.READONLY, False),
    ],
)
def test_role_permissions_for_void(role, can_void):
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=role)
    invoice = SalesInvoiceFactory(company=company, status=InvoiceStatus.ISSUED, number="INV-1")
    client = api_client_for(user, company)

    response = client.post(_void_url(invoice))

    assert (response.status_code == 200) is can_void
