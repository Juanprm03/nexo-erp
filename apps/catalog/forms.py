from django import forms

from apps.catalog.models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        # `company` intentionally excluded: it comes from
        # CompanyScopedFormMixin, never from client input.
        fields = ["sku", "name", "type", "unit_price", "tax_rate", "is_active"]
