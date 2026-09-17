"""Domain services for sales invoicing.

Every multi-table invariant (numbering, totals, state transitions) lives
here — never in models, views, serializers, or signals — so templates and
the API call the exact same code and can never drift apart. No signals
are used anywhere in this module, per the architecture decision to keep
these state changes explicit and traceable in one place.

Audit hook: a transversal `audit` app doesn't exist yet, but every
mutating function below is a single, well-named call site (e.g.
`issue_invoice`) that receives the acting user — wiring
`AuditLog.objects.create(action="invoice_issued", actor=actor, ...)` in
later will mean touching only these functions, not views/serializers.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.money import ZERO, quantize_money
from apps.sales.models import InvoiceStatus, SalesInvoice, SalesInvoiceLine, SalesInvoiceSequence


class InvoiceError(Exception):
    """Base class for sales-invoice domain-rule violations."""


class InvalidInvoiceStateError(InvoiceError):
    """Raised when an operation isn't allowed in the invoice's current status."""


class EmptyInvoiceError(InvoiceError):
    """Raised when trying to issue an invoice with no lines."""


def _lock_draft_invoice(invoice):
    """Re-fetch and lock `invoice` fresh inside the caller's transaction,
    re-validating draft status against the DB — never trust the status of
    whatever (possibly stale) Python object the caller passed in.

    This is what actually prevents a race with issue_invoice()/void_invoice():
    both of those also take select_for_update() on the SAME invoice row, so
    whichever transaction gets there first blocks the other until it
    commits — the second one then sees the fresh, post-commit status and
    correctly rejects the edit if the invoice is no longer a draft.
    Without this, a caller holding a draft `invoice`/`line.invoice` object
    fetched *before* a concurrent issue_invoice() started would still pass
    an in-memory `status == "draft"` check and mutate a line that just got
    issued — the child SalesInvoiceLine row can be UPDATEd/DELETEd without
    Postgres needing to touch (or lock) its parent invoice row at all, so
    nothing but this explicit lock closes that window. Locking the
    invoice (the aggregate root) is enough: it's the row every line
    mutation must check before doing anything, so there's no need to
    separately lock the SalesInvoiceLine rows themselves.
    """
    locked_invoice = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)
    if locked_invoice.status != InvoiceStatus.DRAFT:
        raise InvalidInvoiceStateError("Solo se pueden modificar facturas en borrador.")
    return locked_invoice


def _validate_partner(partner, company):
    if partner.company_id != company.id:
        raise InvoiceError("El tercero debe pertenecer a la empresa activa.")
    if not partner.is_customer:
        raise InvoiceError("El tercero debe ser cliente.")


def _line_amounts(quantity: Decimal, unit_price: Decimal, tax_rate: Decimal):
    """tax_rate is a percentage (19.00 means 19%), matching
    catalog.Product.tax_rate — never a fraction like 0.19.

    Coerces inputs to Decimal defensively: this is a public domain-service
    boundary, and Django does NOT cast a field's value in-memory just
    because it came from a Decimal column — `Model.objects.create(x="1")`
    leaves `instance.x` as the literal str `"1"` until it's reloaded from
    the DB. Callers (forms, DRF) always hand over real Decimals already,
    but this guards against any future caller that doesn't.
    """
    quantity = Decimal(quantity)
    unit_price = Decimal(unit_price)
    tax_rate = Decimal(tax_rate)
    subtotal = quantize_money(quantity * unit_price)
    tax_amount = quantize_money(subtotal * tax_rate / Decimal("100"))
    total = subtotal + tax_amount
    return subtotal, tax_amount, total


def create_draft_invoice(*, company, partner, created_by, due_date=None):
    _validate_partner(partner, company)
    invoice = SalesInvoice(
        company=company,
        partner=partner,
        created_by=created_by,
        due_date=due_date,
        status=InvoiceStatus.DRAFT,
    )
    invoice.full_clean(exclude=["number"])
    invoice.save()
    # audit: invoice_created (actor=created_by)
    return invoice


def update_draft_invoice(invoice, *, partner=None, due_date=None):
    with transaction.atomic():
        locked_invoice = _lock_draft_invoice(invoice)
        if partner is not None:
            _validate_partner(partner, locked_invoice.company)
            locked_invoice.partner = partner
        if due_date is not None:
            locked_invoice.due_date = due_date
        locked_invoice.full_clean(exclude=["number"])
        locked_invoice.save()
    invoice.refresh_from_db()
    return invoice


def add_line(invoice, *, product, quantity, unit_price=None):
    with transaction.atomic():
        locked_invoice = _lock_draft_invoice(invoice)
        if product.company_id != locked_invoice.company_id:
            raise InvoiceError("El producto debe pertenecer a la empresa de la factura.")

        quantity = Decimal(quantity)
        resolved_unit_price = Decimal(product.unit_price if unit_price is None else unit_price)
        tax_rate = Decimal(product.tax_rate)
        subtotal, tax_amount, total = _line_amounts(quantity, resolved_unit_price, tax_rate)

        line = SalesInvoiceLine(
            company=locked_invoice.company,
            invoice=locked_invoice,
            product=product,
            quantity=quantity,
            unit_price=resolved_unit_price,
            tax_rate=tax_rate,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total=total,
        )
        line.full_clean()
        line.save()
        recalculate_totals(locked_invoice)
    return line


def update_line(line, *, quantity=None, unit_price=None):
    """Only quantity/unit_price are editable — product and tax_rate are
    fixed once the line exists. Swapping the product on an existing line
    isn't supported in this MVP: delete and re-add instead, which keeps
    the snapshot semantics unambiguous."""
    with transaction.atomic():
        locked_invoice = _lock_draft_invoice(line.invoice)

        new_quantity = Decimal(line.quantity if quantity is None else quantity)
        new_unit_price = Decimal(line.unit_price if unit_price is None else unit_price)
        subtotal, tax_amount, total = _line_amounts(new_quantity, new_unit_price, line.tax_rate)

        line.quantity = new_quantity
        line.unit_price = new_unit_price
        line.subtotal = subtotal
        line.tax_amount = tax_amount
        line.total = total
        line.full_clean()
        line.save()
        recalculate_totals(locked_invoice)
    return line


def remove_line(line):
    with transaction.atomic():
        locked_invoice = _lock_draft_invoice(line.invoice)
        line.delete()
        recalculate_totals(locked_invoice)


def recalculate_totals(invoice):
    """Invoice totals are always the sum of the (already rounded) line
    totals — never trust a client-sent value, never recompute from
    scratch at the invoice level (see apps/core/money.py for why)."""
    aggregates = invoice.lines.aggregate(
        subtotal=Sum("subtotal"), tax_total=Sum("tax_amount"), total=Sum("total")
    )
    invoice.subtotal = aggregates["subtotal"] or ZERO
    invoice.tax_total = aggregates["tax_total"] or ZERO
    invoice.total = aggregates["total"] or ZERO
    invoice.save(update_fields=["subtotal", "tax_total", "total", "updated_at"])
    return invoice


def _next_invoice_number(company):
    """INV-000001, incrementing per company, never MAX(number) + 1.

    A dedicated SalesInvoiceSequence row per company is locked with
    select_for_update() for the lifetime of the caller's transaction, so
    two concurrent issue_invoice() calls for the SAME company serialize
    on this row (one blocks until the other commits) instead of racing
    to read the same "current max" and computing the same next value.
    Different companies use different rows, so they never contend with
    each other. get_or_create() handles the first-ever-invoice race for
    a company via its own internal savepoint.
    """
    sequence, _ = SalesInvoiceSequence.objects.select_for_update().get_or_create(company=company)
    sequence.last_number += 1
    sequence.save(update_fields=["last_number"])
    return f"INV-{sequence.last_number:06d}"


def issue_invoice(invoice, *, actor=None):
    with transaction.atomic():
        # Lock the invoice row itself too: two concurrent issue attempts
        # on the SAME invoice must not both pass the draft check before
        # either commits.
        locked_invoice = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)
        if locked_invoice.status != InvoiceStatus.DRAFT:
            raise InvalidInvoiceStateError("Solo una factura en borrador puede emitirse.")

        lines = list(locked_invoice.lines.select_related("product"))
        if not lines:
            raise EmptyInvoiceError("No se puede emitir una factura sin líneas.")

        for line in lines:
            if line.product.company_id != locked_invoice.company_id:
                raise InvoiceError("Una línea referencia un producto de otra empresa.")
        _validate_partner(locked_invoice.partner, locked_invoice.company)

        recalculate_totals(locked_invoice)

        locked_invoice.number = _next_invoice_number(locked_invoice.company)
        locked_invoice.issue_date = locked_invoice.issue_date or timezone.localdate()
        locked_invoice.status = InvoiceStatus.ISSUED
        locked_invoice.full_clean()
        locked_invoice.save()
        # audit: invoice_issued (actor=actor)

    invoice.refresh_from_db()
    return invoice


def void_invoice(invoice, *, actor=None):
    """Only an ISSUED invoice can be voided in this MVP — a draft has
    nothing to "void" yet (edit/delete its lines instead), and paid/void
    invoices are already final."""
    with transaction.atomic():
        locked_invoice = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)
        if locked_invoice.status != InvoiceStatus.ISSUED:
            raise InvalidInvoiceStateError("Solo una factura emitida puede anularse.")
        locked_invoice.status = InvoiceStatus.VOID
        locked_invoice.full_clean()
        locked_invoice.save(update_fields=["status", "updated_at"])
        # audit: invoice_voided (actor=actor)

    invoice.refresh_from_db()
    return invoice
