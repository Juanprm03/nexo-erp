from decimal import Decimal

import pytest

from apps.catalog.tests.factories import ProductFactory
from apps.core.money import quantize_money
from apps.sales import services
from apps.sales.tests.factories import SalesInvoiceFactory

pytestmark = pytest.mark.django_db


def test_quantize_money_rounds_half_up():
    assert quantize_money(Decimal("1.005")) == Decimal("1.01")
    assert quantize_money(Decimal("1.004")) == Decimal("1.00")
    assert quantize_money(Decimal("2.675")) == Decimal("2.68")


def test_line_subtotal_is_quantity_times_unit_price():
    invoice = SalesInvoiceFactory()
    product = ProductFactory(company=invoice.company, unit_price="10.50", tax_rate="0")

    line = services.add_line(invoice, product=product, quantity=Decimal("3"))

    assert line.subtotal == Decimal("31.50")


def test_line_tax_amount_uses_percentage_convention():
    """tax_rate is a percentage (19.00 = 19%), not a fraction (0.19)."""
    invoice = SalesInvoiceFactory()
    product = ProductFactory(company=invoice.company, unit_price="100.00", tax_rate="19.00")

    line = services.add_line(invoice, product=product, quantity=Decimal("1"))

    assert line.tax_rate == Decimal("19.00")
    assert line.tax_amount == Decimal("19.00")
    assert line.total == Decimal("119.00")


def test_line_amounts_round_half_up():
    """unit_price itself must stay within 2 decimal places (a model field
    constraint) — the rounding case comes from the *product*
    quantity * unit_price, not from unit_price alone."""
    invoice = SalesInvoiceFactory()
    # subtotal = 2.5 * 10.01 = 25.025 -> rounds to 25.03 (half up)
    product = ProductFactory(company=invoice.company, unit_price="10.01", tax_rate="0")

    line = services.add_line(invoice, product=product, quantity=Decimal("2.5"))

    assert line.subtotal == Decimal("25.03")


def test_invoice_totals_are_sum_of_line_totals():
    invoice = SalesInvoiceFactory()
    product_a = ProductFactory(company=invoice.company, unit_price="10.00", tax_rate="19.00")
    product_b = ProductFactory(company=invoice.company, unit_price="5.00", tax_rate="0")

    services.add_line(invoice, product=product_a, quantity=Decimal("2"))
    services.add_line(invoice, product=product_b, quantity=Decimal("1"))
    invoice.refresh_from_db()

    # line A: subtotal 20.00, tax 3.80, total 23.80
    # line B: subtotal 5.00, tax 0.00, total 5.00
    assert invoice.subtotal == Decimal("25.00")
    assert invoice.tax_total == Decimal("3.80")
    assert invoice.total == Decimal("28.80")


def test_removing_a_line_recalculates_totals():
    invoice = SalesInvoiceFactory()
    product = ProductFactory(company=invoice.company, unit_price="10.00", tax_rate="0")
    line = services.add_line(invoice, product=product, quantity=Decimal("2"))
    invoice.refresh_from_db()
    assert invoice.total == Decimal("20.00")

    services.remove_line(line)
    invoice.refresh_from_db()

    assert invoice.total == Decimal("0")
    assert invoice.subtotal == Decimal("0")


def test_product_price_change_does_not_alter_historical_line():
    """The whole point of the snapshot: a later Product price/tax change
    must never alter an already-added line."""
    invoice = SalesInvoiceFactory()
    product = ProductFactory(company=invoice.company, unit_price="10.00", tax_rate="19.00")

    line = services.add_line(invoice, product=product, quantity=Decimal("1"))
    assert line.unit_price == Decimal("10.00")
    assert line.tax_rate == Decimal("19.00")

    product.unit_price = Decimal("999.00")
    product.tax_rate = Decimal("0.00")
    product.save(update_fields=["unit_price", "tax_rate"])

    line.refresh_from_db()
    assert line.unit_price == Decimal("10.00")
    assert line.tax_rate == Decimal("19.00")
    assert line.subtotal == Decimal("10.00")


def test_manual_unit_price_override_is_kept_as_snapshot():
    invoice = SalesInvoiceFactory()
    product = ProductFactory(company=invoice.company, unit_price="10.00", tax_rate="0")

    line = services.add_line(
        invoice, product=product, quantity=Decimal("1"), unit_price=Decimal("7.50")
    )

    assert line.unit_price == Decimal("7.50")
    assert line.subtotal == Decimal("7.50")
