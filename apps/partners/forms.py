from django import forms

from apps.partners.models import Partner


class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        # `company` intentionally excluded: it comes from
        # CompanyScopedFormMixin, never from client input.
        fields = [
            "name",
            "tax_id",
            "is_customer",
            "is_supplier",
            "email",
            "phone",
            "address",
            "is_active",
        ]
