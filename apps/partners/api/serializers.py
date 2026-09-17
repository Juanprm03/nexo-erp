from rest_framework import serializers

from apps.partners.models import Partner


class PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = [
            "id",
            "company",
            "name",
            "tax_id",
            "is_customer",
            "is_supplier",
            "email",
            "phone",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "company", "created_at", "updated_at"]

    def validate_tax_id(self, value):
        """DB partial unique index is the ultimate guard; this just turns
        the common case into a clean 400 instead of a raw IntegrityError."""
        request = self.context.get("request")
        company = getattr(request, "active_company", None) if request else None
        if value and company is not None:
            queryset = Partner.objects.filter(company=company, tax_id=value)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    "Ya existe un tercero con este tax_id en la empresa activa."
                )
        return value

    def validate(self, attrs):
        is_customer = attrs.get("is_customer", getattr(self.instance, "is_customer", False))
        is_supplier = attrs.get("is_supplier", getattr(self.instance, "is_supplier", False))
        if not is_customer and not is_supplier:
            raise serializers.ValidationError(
                "El tercero debe ser cliente, proveedor o ambos."
            )
        return attrs
