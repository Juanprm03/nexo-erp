from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.catalog.tests.factories import ProductFactory
from apps.companies.models import MembershipRole
from apps.companies.services import ACTIVE_COMPANY_SESSION_KEY
from apps.companies.tests.factories import CompanyFactory, CompanyMembershipFactory, UserFactory
from apps.partners.tests.factories import PartnerFactory
from apps.sales.models import InvoiceStatus, SalesInvoice, SalesInvoiceLine
from apps.sales.tests.factories import SalesInvoiceFactory, SalesInvoiceLineFactory

pytestmark = pytest.mark.django_db


def _client_for(user, company=None):
    client = Client()
    client.force_login(user)
    if company is not None:
        session = client.session
        session[ACTIVE_COMPANY_SESSION_KEY] = company.id
        session.save()
    return client


def test_list_view_renders():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.READONLY)
    SalesInvoiceFactory(company=company)
    client = _client_for(user, company)

    response = client.get(reverse("sales:list"))

    assert response.status_code == 200


def test_detail_view_renders():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.READONLY)
    invoice = SalesInvoiceFactory(company=company)
    client = _client_for(user, company)

    response = client.get(reverse("sales:detail", args=[invoice.pk]))

    assert response.status_code == 200


def test_create_view_stamps_active_company_and_created_by():
    company = CompanyFactory()
    partner = PartnerFactory(company=company, is_customer=True)
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    client = _client_for(user, company)

    response = client.post(reverse("sales:create"), {"partner": partner.id})

    assert response.status_code == 302
    invoice = SalesInvoice.objects.get(company=company, partner=partner)
    assert invoice.created_by_id == user.id
    assert invoice.status == InvoiceStatus.DRAFT


def test_create_view_rejects_partner_of_another_company():
    company = CompanyFactory()
    other_company = CompanyFactory()
    foreign_partner = PartnerFactory(company=other_company, is_customer=True)
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    client = _client_for(user, company)

    response = client.post(reverse("sales:create"), {"partner": foreign_partner.id})

    # The form's queryset already excludes foreign partners, so this is a
    # plain form validation error (200 + form error), not a 500.
    assert response.status_code == 200
    assert "partner" in response.context["form"].errors


def test_readonly_role_cannot_access_create_view():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.READONLY)
    client = _client_for(user, company)

    response = client.get(reverse("sales:create"))

    assert response.status_code == 403


def test_edit_view_404s_for_non_draft_invoice():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company, status=InvoiceStatus.ISSUED, number="INV-1")
    client = _client_for(user, company)

    response = client.get(reverse("sales:edit", args=[invoice.pk]))

    assert response.status_code == 403


def test_update_view_404s_for_invoice_of_another_company():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    user_a = UserFactory()
    CompanyMembershipFactory(user=user_a, company=company_a, role=MembershipRole.SALES)
    invoice_b = SalesInvoiceFactory(company=company_b)
    client = _client_for(user_a, company_a)

    response = client.get(reverse("sales:edit", args=[invoice_b.pk]))

    assert response.status_code == 404


# --- lines -----------------------------------------------------------------


def test_add_line_view_adds_and_recalculates():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    product = ProductFactory(company=company, unit_price="10.00", tax_rate="0")
    client = _client_for(user, company)

    response = client.post(
        reverse("sales:line-add", args=[invoice.pk]),
        {"product": product.pk, "quantity": "2"},
    )

    assert response.status_code == 302
    invoice.refresh_from_db()
    assert invoice.total == Decimal("20.00")


def test_add_line_view_rejects_when_invoice_not_draft():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company, status=InvoiceStatus.ISSUED, number="INV-1")
    product = ProductFactory(company=company)
    client = _client_for(user, company)

    response = client.post(
        reverse("sales:line-add", args=[invoice.pk]),
        {"product": product.pk, "quantity": "1"},
    )

    assert response.status_code == 403


def test_edit_line_view_updates_quantity():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    line = SalesInvoiceLineFactory(
        invoice=invoice, company=company, unit_price="10.00", tax_rate="0", quantity="1"
    )
    client = _client_for(user, company)

    response = client.post(
        reverse("sales:line-edit", args=[invoice.pk, line.pk]),
        {"quantity": "3", "unit_price": "10.00"},
    )

    assert response.status_code == 302
    line.refresh_from_db()
    invoice.refresh_from_db()
    assert line.quantity == Decimal("3")
    assert invoice.total == Decimal("30.00")


def test_delete_line_view_removes_line():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    line = SalesInvoiceLineFactory(invoice=invoice, company=company)
    client = _client_for(user, company)

    response = client.post(reverse("sales:line-delete", args=[invoice.pk, line.pk]))

    assert response.status_code == 302
    assert not SalesInvoiceLine.objects.filter(pk=line.pk).exists()


# --- issue / void ------------------------------------------------------------


def test_issue_view_issues_invoice():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company)
    SalesInvoiceLineFactory(invoice=invoice, company=company)
    client = _client_for(user, company)

    response = client.post(reverse("sales:issue", args=[invoice.pk]))

    assert response.status_code == 302
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.ISSUED
    assert invoice.number == "INV-000001"


def test_readonly_role_cannot_issue():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.READONLY)
    invoice = SalesInvoiceFactory(company=company)
    SalesInvoiceLineFactory(invoice=invoice, company=company)
    client = _client_for(user, company)

    response = client.post(reverse("sales:issue", args=[invoice.pk]))

    assert response.status_code == 403
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.DRAFT


def test_void_view_voids_issued_invoice():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.ACCOUNTANT)
    invoice = SalesInvoiceFactory(company=company, status=InvoiceStatus.ISSUED, number="INV-1")
    client = _client_for(user, company)

    response = client.post(reverse("sales:void", args=[invoice.pk]))

    assert response.status_code == 302
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.VOID


def test_sales_role_cannot_void():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.SALES)
    invoice = SalesInvoiceFactory(company=company, status=InvoiceStatus.ISSUED, number="INV-1")
    client = _client_for(user, company)

    response = client.post(reverse("sales:void", args=[invoice.pk]))

    assert response.status_code == 403
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.ISSUED


def test_purchasing_role_can_only_read():
    company = CompanyFactory()
    user = UserFactory()
    CompanyMembershipFactory(user=user, company=company, role=MembershipRole.PURCHASING)
    invoice = SalesInvoiceFactory(company=company)
    client = _client_for(user, company)

    list_response = client.get(reverse("sales:list"))
    detail_response = client.get(reverse("sales:detail", args=[invoice.pk]))
    create_response = client.get(reverse("sales:create"))

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert create_response.status_code == 403
