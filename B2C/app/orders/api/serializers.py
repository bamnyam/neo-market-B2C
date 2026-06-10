from rest_framework import serializers

from app.buyers.models import Address, PaymentMethod


class CheckoutItemSerializer(serializers.Serializer):
    sku_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class CheckoutSerializer(serializers.Serializer):
    allowed_fields = {"items", "address_id", "payment_method_id", "comment"}

    items = CheckoutItemSerializer(many=True, allow_empty=False)
    address_id = serializers.UUIDField()
    payment_method_id = serializers.UUIDField()
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
    )

    def validate(self, attrs):
        unknown_fields = set(self.initial_data) - self.allowed_fields

        if unknown_fields:
            raise serializers.ValidationError("Unknown fields are not accepted")

        buyer = self.context.get("buyer")
        address = Address.objects.filter(
            buyer=buyer,
            uuid=attrs["address_id"],
        ).first()
        payment_method = PaymentMethod.objects.filter(
            buyer=buyer,
            uuid=attrs["payment_method_id"],
        ).first()

        if address is None:
            raise serializers.ValidationError({"address_id": "Address not found"})

        if payment_method is None:
            raise serializers.ValidationError(
                {"payment_method_id": "Payment method not found"}
            )

        attrs["address"] = address
        attrs["payment_method"] = payment_method

        return attrs
