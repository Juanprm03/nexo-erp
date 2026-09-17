from decimal import Decimal

from django import forms

from apps.catalog.models import Product
from apps.partners.models import Partner
from apps.sales.models import SalesInvoice


class SalesInvoiceForm(forms.ModelForm):
    """Bound to `request.active_company` for its querysets/validation, but
    persistence always goes through apps.sales.services — see
    SalesInvoiceCreateView/UpdateView. Never used with .save()."""

    class Meta:
        model = SalesInvoice
        fields = ["partner", "due_date"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields["partner"].queryset = Partner.objects.for_company(company).filter(
                is_customer=True, is_active=True
            )


class SalesInvoiceLineAddForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.none())
    quantity = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    # Optional: falls back to the product's current price when left blank
    # (snapshotted by services.add_line, never re-read afterward).
    unit_price = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False
    )

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields["product"].queryset = Product.objects.for_company(company).filter(
                is_active=True
            )


class SalesInvoiceLineEditForm(forms.Form):
    """Product is intentionally not editable here — see
    services.update_line's docstring for why."""

    quantity = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    unit_price = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"))
