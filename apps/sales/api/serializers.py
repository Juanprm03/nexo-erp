from decimal import Decimal

from rest_framework import serializers

from apps.sales.models import SalesInvoice, SalesInvoiceLine


class SalesInvoiceLineSerializer(serializers.ModelSerializer):
    # Declared explicitly (not auto-generated) so it can be optional: an
    # omitted unit_price falls back to the product's current price,
    # snapshotted by services.add_line — see that module's docstring.
    unit_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, min_value=Decimal("0")
    )

    class Meta:
        model = SalesInvoiceLine
        fields = [
            "id",
            "company",
            "invoice",
            "product",
            "quantity",
            "unit_price",
            "tax_rate",
            "subtotal",
            "tax_amount",
            "total",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "tax_rate",
            "subtotal",
            "tax_amount",
            "total",
            "created_at",
            "updated_at",
        ]

    def validate_invoice(self, value):
        request = self.context.get("request")
        company = getattr(request, "active_company", None) if request else None
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError("La factura no pertenece a la empresa activa.")
        return value

    def validate_product(self, value):
        request = self.context.get("request")
        company = getattr(request, "active_company", None) if request else None
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError("El producto no pertenece a la empresa activa.")
        return value


class SalesInvoiceSerializer(serializers.ModelSerializer):
    lines = SalesInvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = SalesInvoice
        fields = [
            "id",
            "company",
            "partner",
            "number",
            "status",
            "issue_date",
            "due_date",
            "subtotal",
            "tax_total",
            "total",
            "created_by",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "number",
            "status",
            "issue_date",
            "subtotal",
            "tax_total",
            "total",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate_partner(self, value):
        request = self.context.get("request")
        company = getattr(request, "active_company", None) if request else None
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError("El tercero no pertenece a la empresa activa.")
        if not value.is_customer:
            raise serializers.ValidationError("El tercero debe ser cliente.")
        return value
