from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from orders.models import Order, Payment
from .utils import initialize_transaction, verify_transaction
from .serializers import PaymentInitializeSerializer, PaymentCallbackSerializer


# REST API Views
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initialize_payment_api(request):
    """Initialize payment for an order"""
    serializer = PaymentInitializeSerializer(data=request.data)
    if serializer.is_valid():
        order_id = serializer.validated_data['order_id']
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Initialize payment with Paystack
        callback_url = request.build_absolute_uri(reverse("payment_callback_api"))
        response, reference = initialize_transaction(
            request.user.email,
            float(order.total_amount),
            callback_url
        )

        if response.get("status"):
            # Create payment record
            payment = Payment.objects.create(
                order=order,
                amount=order.total_amount,
                transaction_reference=reference,
                status='PENDING'
            )
            order.transaction_reference = reference
            order.save()

            return Response({
                "success": True,
                "authorization_url": response["data"]["authorization_url"],
                "access_code": response["data"]["access_code"],
                "reference": reference,
                "payment_id": payment.id
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Could not initialize payment"},
                status=status.HTTP_400_BAD_REQUEST
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def payment_callback_api(request):
    """Handle payment callback from Paystack"""
    serializer = PaymentCallbackSerializer(data=request.data)
    if serializer.is_valid():
        reference = serializer.validated_data['reference']
        
        # Verify transaction with Paystack
        verification = verify_transaction(reference)
        
        if verification and verification.get("data", {}).get("status") == "success":
            try:
                payment = Payment.objects.get(transaction_reference=reference)
                payment.status = 'SUCCESSFUL'
                payment.save()
                
                order = payment.order
                order.status = 'PAID'
                order.save()
                
                return Response({
                    "success": True,
                    "message": "Payment verified successfully",
                    "order_id": order.id
                }, status=status.HTTP_200_OK)
            except Payment.DoesNotExist:
                return Response(
                    {"error": "Payment record not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {"error": "Payment verification failed"},
                status=status.HTTP_400_BAD_REQUEST
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Template Views (Legacy - kept for backward compatibility)
def start_payment(request):
    email = "customer@email.com"  # replace with request.user.email or form input
    amount = 5000  # Naira

    callback_url = request.build_absolute_uri(reverse("payment_callback"))
    response, reference = initialize_transaction(email, amount, callback_url)

    if response.get("status"):
        # Save `reference` against the user's pending order here, e.g.:
        # Order.objects.create(user=request.user, reference=reference, amount=amount, status="pending")
        payment_url = response["data"]["authorization_url"]
        return redirect(payment_url)

    messages.error(request, "Could not start payment. Please try again.")
    return redirect("checkout")


def payment_callback(request):
    reference = request.GET.get("reference")
    if not reference:
        messages.error(request, "No payment reference found.")
        return redirect("checkout")

    verification = verify_transaction(reference)

    if verification["data"]["status"] == "success":
        # Order.objects.filter(reference=reference).update(status="paid")
        messages.success(request, "Payment successful!")
        return render(request, "payment_success.html", {"data": verification["data"]})

    messages.error(request, "Payment failed or is still pending.")
    return render(request, "payment_failed.html")