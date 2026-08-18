from rest_framework import serializers
from orders.models import Payment, Order


class PaymentInitializeSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()


class PaymentCallbackSerializer(serializers.Serializer):
    reference = serializers.CharField()


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order', 'amount', 'status', 'transaction_reference', 'payment_method', 'created_at']
        read_only_fields = ['id', 'created_at', 'status']
