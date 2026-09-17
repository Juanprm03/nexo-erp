from rest_framework import serializers

from apps.catalog.models import Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "company",
            "sku",
            "name",
            "type",
            "unit_price",
            "tax_rate",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "company", "created_at", "updated_at"]

    def validate_sku(self, value):
        """DB unique constraint is the ultimate guard; this gives a clean
        400 instead of a raw IntegrityError for the common case."""
        request = self.context.get("request")
        company = getattr(request, "active_company", None) if request else None
        if company is not None:
            queryset = Product.objects.filter(company=company, sku=value)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    "Ya existe un producto con este SKU en la empresa activa."
                )
        return value
