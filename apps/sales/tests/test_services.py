import threading
import time
from decimal import Decimal

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.catalog.tests.factories import ProductFactory
from apps.companies.tests.factories import CompanyFactory
from apps.sales import services
from apps.sales.models import InvoiceStatus, SalesInvoice, SalesInvoiceSequence
from apps.sales.tests.factories import SalesInvoiceFactory

pytestmark = pytest.mark.django_db


def _add_default_line(invoice, **overrides):
    product = ProductFactory(company=invoice.company, unit_price="10.00", tax_rate="19.00")
    return services.add_line(invoice, product=product, quantity=Decimal("1"), **overrides)


# --- draft editing -----------------------------------------------------


def test_draft_invoice_is_editable():
    invoice = SalesInvoiceFactory()
    from apps.partners.tests.factories import PartnerFactory

    new_partner = PartnerFactory(company=invoice.company, is_customer=True)

    services.update_draft_invoice(invoice, partner=new_partner)

    invoice.refresh_from_db()
    assert invoice.partner_id == new_partner.id


def test_issued_invoice_cannot_be_edited():
    invoice = SalesInvoiceFactory()
    _add_default_line(invoice)
    services.issue_invoice(invoice)

    with pytest.raises(services.InvalidInvoiceStateError):
        services.update_draft_invoice(invoice, due_date=None)


def test_void_invoice_cannot_be_edited():
    invoice = SalesInvoiceFactory()
    _add_default_line(invoice)
    services.issue_invoice(invoice)
    services.void_invoice(invoice)

    with pytest.raises(services.InvalidInvoiceStateError):
        services.update_draft_invoice(invoice, due_date=None)


def test_cannot_add_line_to_issued_invoice():
    invoice = SalesInvoiceFactory()
    _add_default_line(invoice)
    services.issue_invoice(invoice)
    product = ProductFactory(company=invoice.company)

    with pytest.raises(services.InvalidInvoiceStateError):
        services.add_line(invoice, product=product, quantity=Decimal("1"))


def test_cannot_edit_line_of_issued_invoice():
    invoice = SalesInvoiceFactory()
    line = _add_default_line(invoice)
    services.issue_invoice(invoice)

    with pytest.raises(services.InvalidInvoiceStateError):
        services.update_line(line, quantity=Decimal("5"))


def test_cannot_remove_line_of_issued_invoice():
    invoice = SalesInvoiceFactory()
    line = _add_default_line(invoice)
    services.issue_invoice(invoice)

    with pytest.raises(services.InvalidInvoiceStateError):
        services.remove_line(line)


# --- issuance ------------------------------------------------------------


def test_cannot_issue_invoice_without_lines():
    invoice = SalesInvoiceFactory()

    with pytest.raises(services.EmptyInvoiceError):
        services.issue_invoice(invoice)

    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.DRAFT
    assert invoice.number == ""


def test_issue_invoice_assigns_number_and_status():
    invoice = SalesInvoiceFactory()
    _add_default_line(invoice)

    services.issue_invoice(invoice)
    invoice.refresh_from_db()

    assert invoice.status == InvoiceStatus.ISSUED
    assert invoice.number == "INV-000001"
    assert invoice.issue_date is not None


def test_issue_invoice_twice_fails():
    invoice = SalesInvoiceFactory()
    _add_default_line(invoice)
    services.issue_invoice(invoice)

    with pytest.raises(services.InvalidInvoiceStateError):
        services.issue_invoice(invoice)


def test_numbering_increments_within_same_company():
    company = CompanyFactory()
    invoice1 = SalesInvoiceFactory(company=company)
    _add_default_line(invoice1)
    invoice2 = SalesInvoiceFactory(company=company)
    _add_default_line(invoice2)

    services.issue_invoice(invoice1)
    services.issue_invoice(invoice2)
    invoice1.refresh_from_db()
    invoice2.refresh_from_db()

    assert invoice1.number == "INV-000001"
    assert invoice2.number == "INV-000002"


def test_two_companies_can_both_have_inv_000001():
    company_a = CompanyFactory()
    company_b = CompanyFactory()
    invoice_a = SalesInvoiceFactory(company=company_a)
    _add_default_line(invoice_a)
    invoice_b = SalesInvoiceFactory(company=company_b)
    _add_default_line(invoice_b)

    services.issue_invoice(invoice_a)
    services.issue_invoice(invoice_b)
    invoice_a.refresh_from_db()
    invoice_b.refresh_from_db()

    assert invoice_a.number == "INV-000001"
    assert invoice_b.number == "INV-000001"


def test_status_never_becomes_paid_through_any_service():
    """`paid` exists in the domain but no function in this module ever
    assigns it — that belongs to a future `treasury` app."""
    invoice = SalesInvoiceFactory()
    _add_default_line(invoice)
    services.issue_invoice(invoice)
    invoice.refresh_from_db()
    assert invoice.status != InvoiceStatus.PAID


def test_void_rejects_draft():
    draft_invoice = SalesInvoiceFactory()

    with pytest.raises(services.InvalidInvoiceStateError):
        services.void_invoice(draft_invoice)

    draft_invoice.refresh_from_db()
    assert draft_invoice.status == InvoiceStatus.DRAFT


def test_void_rejects_paid():
    """No service ever sets `paid` (that's treasury's job later), but
    void_invoice() must still refuse it if something else ever does."""
    invoice = SalesInvoiceFactory()
    _add_default_line(invoice)
    services.issue_invoice(invoice)
    SalesInvoice.objects.filter(pk=invoice.pk).update(status=InvoiceStatus.PAID)
    invoice.refresh_from_db()

    with pytest.raises(services.InvalidInvoiceStateError):
        services.void_invoice(invoice)

    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.PAID


def test_void_rejects_already_void():
    invoice = SalesInvoiceFactory()
    _add_default_line(invoice)
    services.issue_invoice(invoice)
    services.void_invoice(invoice)

    with pytest.raises(services.InvalidInvoiceStateError):
        services.void_invoice(invoice)

    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.VOID


def test_void_issued_invoice_preserves_lines_and_history():
    invoice = SalesInvoiceFactory()
    line = _add_default_line(invoice)

    services.issue_invoice(invoice)
    number = invoice.number
    total = invoice.total

    services.void_invoice(invoice)
    invoice.refresh_from_db()
    line.refresh_from_db()

    assert invoice.status == InvoiceStatus.VOID
    assert invoice.number == number
    assert invoice.total == total
    assert line.pk is not None


@pytest.mark.django_db(transaction=True)
def test_concurrent_issue_generates_unique_sequential_numbers():
    """Real concurrency test against Postgres: two threads (separate DB
    connections) issue two different draft invoices of the SAME company
    at roughly the same time. select_for_update() on the per-company
    SalesInvoiceSequence row must serialize them so neither gets a
    duplicate or skipped number."""
    company = CompanyFactory()
    invoice1 = SalesInvoiceFactory(company=company)
    invoice2 = SalesInvoiceFactory(company=company)
    product = ProductFactory(company=company, unit_price="10.00", tax_rate="0")
    services.add_line(invoice1, product=product, quantity=Decimal("1"))
    services.add_line(invoice2, product=product, quantity=Decimal("1"))

    results = {}
    errors = []
    barrier = threading.Barrier(2)

    def issue(invoice, key):
        try:
            barrier.wait(timeout=5)
            services.issue_invoice(invoice)
            invoice.refresh_from_db()
            results[key] = invoice.number
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()

    t1 = threading.Thread(target=issue, args=(invoice1, "a"))
    t2 = threading.Thread(target=issue, args=(invoice2, "b"))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, errors
    assert sorted(results.values()) == ["INV-000001", "INV-000002"]
    assert SalesInvoiceSequence.objects.get(company=company).last_number == 2


@pytest.mark.django_db(transaction=True)
def test_concurrent_line_edit_is_blocked_and_rejected_while_invoice_is_being_issued():
    """Regression test for the _lock_draft_invoice() fix.

    Before that fix, update_line()/add_line()/remove_line() only checked
    the in-memory `.status` of whatever `invoice` object the caller
    passed in — never re-fetched it. A child SalesInvoiceLine row can be
    UPDATEd/DELETEd without Postgres needing to touch (or lock) its
    parent invoice row at all, so a concurrent edit could sneak in and
    silently corrupt a just-issued invoice's totals.

    This test deterministically reproduces the race instead of hoping a
    plain thread-barrier lands the "bad" interleaving: thread 1 acquires
    the invoice's row lock and holds it open (simulating being "mid
    issue"); thread 2's update_line() call, which also needs
    select_for_update() on that same row via _lock_draft_invoice(), must
    block until thread 1 releases it, and must then see the fresh
    "issued" status and reject the edit.
    """
    company = CompanyFactory()
    invoice = SalesInvoiceFactory(company=company)
    product = ProductFactory(company=company, unit_price="10.00", tax_rate="0")
    line = services.add_line(invoice, product=product, quantity=Decimal("1"))

    lock_acquired = threading.Event()
    release_lock = threading.Event()
    edit_outcome = {}

    def hold_lock_then_issue():
        with transaction.atomic():
            locked = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)
            lock_acquired.set()
            release_lock.wait(timeout=5)
            # Inlined equivalent of issue_invoice()'s final steps, so we
            # control exactly when the lock is released relative to t2.
            locked.number = "INV-000001"
            locked.issue_date = timezone.localdate()
            locked.status = InvoiceStatus.ISSUED
            locked.save()
        connection.close()

    def try_edit_line():
        lock_acquired.wait(timeout=5)
        try:
            services.update_line(line, quantity=Decimal("999"))
            edit_outcome["result"] = "succeeded"
        except services.InvalidInvoiceStateError:
            edit_outcome["result"] = "rejected"
        finally:
            connection.close()

    t1 = threading.Thread(target=hold_lock_then_issue)
    t2 = threading.Thread(target=try_edit_line)
    t1.start()
    assert lock_acquired.wait(timeout=5)
    t2.start()
    # Give t2 time to reach select_for_update() and actually start
    # blocking on the row lock before we release it.
    time.sleep(0.5)
    release_lock.set()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert edit_outcome.get("result") == "rejected"

    invoice.refresh_from_db()
    line.refresh_from_db()
    assert invoice.status == InvoiceStatus.ISSUED
    assert line.quantity == Decimal("1")
    assert invoice.total == Decimal("10.00")
