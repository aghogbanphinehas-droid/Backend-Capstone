import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Sum, Count
from rest_framework import viewsets, status, response, generics, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .models import Cart, CartItem, Order, OrderItem, Coupon, Payment, Shipment, Notification
from .serializers import (
    CartSerializer, CartItemSerializer, OrderSerializer, 
    CouponSerializer, PaymentSerializer, ShipmentSerializer, NotificationSerializer
)
from store.models import ProductVariant
from store.serializers import ProductVariantSerializer
from accounts.models import User
from store.models import Product

class CartViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer

    def get_cart(self, user):
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    def list(self, request):
        cart = self.get_cart(request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    def create(self, request):
        cart = self.get_cart(request.user)
        variant_id = request.data.get('variant_id')
        quantity = request.data.get('quantity', 1)
        
        if not variant_id:
            return Response({"error": "variant_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            quantity = int(quantity)
        except ValueError:
            return Response({"error": "quantity must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
            
        if quantity <= 0:
            return Response({"error": "quantity must be greater than zero"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            variant = ProductVariant.objects.get(id=variant_id)
        except ProductVariant.DoesNotExist:
            return Response({"error": "Product variant not found"}, status=status.HTTP_404_NOT_FOUND)
            
        if variant.stock < quantity:
            return Response({"error": f"Not enough stock. Available: {variant.stock}"}, status=status.HTTP_400_BAD_REQUEST)
            
        cart_item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
        if not created:
            if variant.stock < (cart_item.quantity + quantity):
                return Response({"error": f"Cannot add {quantity} more. Stock limit: {variant.stock}"}, status=status.HTTP_400_BAD_REQUEST)
            cart_item.quantity += quantity
        else:
            cart_item.quantity = quantity
        cart_item.save()
        
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        cart = self.get_cart(request.user)
        try:
            cart_item = CartItem.objects.get(id=pk, cart=cart)
        except CartItem.DoesNotExist:
            return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)
            
        quantity = request.data.get('quantity')
        if quantity is None:
            return Response({"error": "quantity is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            quantity = int(quantity)
        except ValueError:
            return Response({"error": "quantity must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
            
        if quantity <= 0:
            cart_item.delete()
        else:
            if cart_item.variant.stock < quantity:
                return Response({"error": f"Not enough stock. Available: {cart_item.variant.stock}"}, status=status.HTTP_400_BAD_REQUEST)
            cart_item.quantity = quantity
            cart_item.save()
            
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None):
        cart = self.get_cart(request.user)
        try:
            cart_item = CartItem.objects.get(id=pk, cart=cart)
        except CartItem.DoesNotExist:
            return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)
            
        cart_item.delete()
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)

class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        if self.request.user.role == 'ADMIN':
            return Order.objects.all().order_by('-created_at')
        return Order.objects.filter(user=self.request.user).order_by('-created_at')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        cart = Cart.objects.filter(user=request.user).first()
        if not cart or not cart.items.exists():
            return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        address = request.data.get('address')
        if not address:
            return Response({"error": "Shipping address required"}, status=status.HTTP_400_BAD_REQUEST)

        # Coupon support
        coupon_code = request.data.get('coupon_code')
        coupon = None
        discount_amount = 0.00
        total_amount = cart.total_price

        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code)
                if not coupon.is_valid():
                    return Response({"error": "Coupon is invalid or expired"}, status=status.HTTP_400_BAD_REQUEST)
                discount_amount = coupon.calculate_discount(total_amount)
                total_amount -= discount_amount
            except Coupon.DoesNotExist:
                return Response({"error": "Coupon not found"}, status=status.HTTP_404_NOT_FOUND)

        # Create Order
        order = Order.objects.create(
            user=request.user,
            total_amount=total_amount,
            discount_amount=discount_amount,
            coupon=coupon,
            address=address,
            status='PENDING'
        )

        # Update coupon usage
        if coupon:
            coupon.times_used += 1
            coupon.save()

        # Process Items & Deduct Stock
        for item in cart.items.all():
            if item.variant.stock < item.quantity:
                raise ValidationError(f"Variant {item.variant.sku} ran out of stock.")
            
            item.variant.stock -= item.quantity
            item.variant.save()

            price = item.variant.price_override if item.variant.price_override else item.variant.product.price
            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                quantity=item.quantity,
                price=price
            )

        cart.items.all().delete()
        
        # Send Notification
        Notification.objects.create(
            user=request.user,
            title="Order Placed Successfully",
            message=f"Your order #{order.id} has been placed. Total: {order.total_amount}",
            notification_type='BOTH'
        )
        
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            return Response({"error": "Only admins can modify orders directly."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='cancel')
    @transaction.atomic
    def cancel_order(self, request, pk=None):
        order = self.get_object()
        
        if order.user != request.user and request.user.role != 'ADMIN':
            return Response({"error": "You do not have permission to cancel this order."}, status=status.HTTP_403_FORBIDDEN)
            
        if order.status not in ['PENDING']:
            return Response({"error": f"Cannot cancel an order that is in {order.status} status."}, status=status.HTTP_400_BAD_REQUEST)
            
        for item in order.items.all():
            if item.variant:
                item.variant.stock += item.quantity
                item.variant.save()
                
        order.status = 'CANCELLED'
        order.save()
        
        Notification.objects.create(
            user=order.user,
            title="Order Cancelled",
            message=f"Your order #{order.id} has been cancelled successfully.",
            notification_type='SYSTEM'
        )
        
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='invoice')
    def invoice(self, request, pk=None):
        order = self.get_object()
        
        if order.user != request.user and request.user.role != 'ADMIN':
            return Response({"error": "You do not have permission to view this invoice."}, status=status.HTTP_403_FORBIDDEN)
            
        items_summary = []
        for item in order.items.all():
            items_summary.append({
                "product_name": item.variant.product.name if item.variant else "Unknown Product",
                "sku": item.variant.sku if item.variant else "N/A",
                "size": item.variant.size if item.variant else "N/A",
                "color": item.variant.color if item.variant else "N/A",
                "quantity": item.quantity,
                "unit_price": float(item.price),
                "subtotal": float(item.price * item.quantity)
            })
            
        invoice_data = {
            "invoice_number": f"INV-{order.id}-{order.created_at.strftime('%Y%m%d')}",
            "order_id": order.id,
            "created_at": order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "customer_email": order.user.email,
            "shipping_address": order.address,
            "items": items_summary,
            "discount_amount": float(order.discount_amount),
            "coupon_applied": order.coupon.code if order.coupon else None,
            "subtotal": float(order.total_amount + order.discount_amount),
            "total_amount": float(order.total_amount),
            "payment_status": order.status,
        }
        return Response(invoice_data, status=status.HTTP_200_OK)

class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsAuthenticated(), permissions.IsAdminUser()]

class PaystackInitializeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')
        order = get_object_or_404(Order, id=order_id, user=request.user)

        if order.status != 'PENDING':
            return Response({'error': 'Order is not pending or already paid.'}, status=status.HTTP_400_BAD_REQUEST)

        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "email": request.user.email,
            "amount": int(order.total_amount * 100),
            "reference": f"ORD_{order.id}_{order.created_at.timestamp()}"
        }

        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()

        if response_data.get('status'):
            order.transaction_reference = data['reference']
            order.save()
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

class PaystackVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reference = request.data.get('reference')
        order = get_object_or_404(Order, transaction_reference=reference, user=request.user)

        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        }

        response = requests.get(url, headers=headers)
        response_data = response.json()

        if response_data.get('status') and response_data['data']['status'] == 'success':
            order.status = 'PAID'
            order.save()

            Payment.objects.create(
                order=order,
                amount=order.total_amount,
                status='SUCCESSFUL',
                transaction_reference=reference,
                payment_method='card'
            )

            Shipment.objects.get_or_create(
                order=order,
                defaults={
                    'status': 'PENDING',
                    'carrier': 'Local Delivery'
                }
            )

            Notification.objects.create(
                user=order.user,
                title="Payment Verification Successful",
                message=f"Your payment for order #{order.id} was verified successfully.",
                notification_type='BOTH'
            )
            return Response({'message': 'Payment successful, order updated.'}, status=status.HTTP_200_OK)
            
        return Response({'error': 'Payment verification failed.'}, status=status.HTTP_400_BAD_REQUEST)

class PaymentHistoryView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role == 'ADMIN':
            return Payment.objects.all().order_by('-created_at')
        return Payment.objects.filter(order__user=self.request.user).order_by('-created_at')

class PaymentRefundView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if request.user.role != 'ADMIN':
            return Response({"error": "Only admins can issue refunds."}, status=status.HTTP_403_FORBIDDEN)
            
        payment = get_object_or_404(Payment, id=pk)
        if payment.status != 'SUCCESSFUL':
            return Response({"error": "Can only refund successful payments."}, status=status.HTTP_400_BAD_REQUEST)
            
        payment.status = 'REFUNDED'
        payment.save()
        
        order = payment.order
        order.status = 'REFUNDED'
        order.save()
        
        for item in order.items.all():
            if item.variant:
                item.variant.stock += item.quantity
                item.variant.save()
                
        Notification.objects.create(
            user=order.user,
            title="Refund Processed",
            message=f"A refund of {payment.amount} has been processed for Order #{order.id}.",
            notification_type='BOTH'
        )
        return Response({"message": "Refund processed successfully and stock restored."}, status=status.HTTP_200_OK)

class ShipmentViewSet(viewsets.ModelViewSet):
    serializer_class = ShipmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role == 'ADMIN':
            return Shipment.objects.all().order_by('-id')
        return Shipment.objects.filter(order__user=self.request.user).order_by('-id')

    def update(self, request, *args, **kwargs):
        if self.request.user.role != 'ADMIN':
            return Response({"error": "Only admins can update shipment details."}, status=status.HTTP_403_FORBIDDEN)
            
        response_obj = super().update(request, *args, **kwargs)
        shipment = self.get_object()
        
        order = shipment.order
        if shipment.status == 'DELIVERED':
            order.status = 'DELIVERED'
            order.save()
            Notification.objects.create(
                user=order.user,
                title="Shipment Delivered",
                message=f"Your order #{order.id} has been delivered successfully.",
                notification_type='BOTH'
            )
        elif shipment.status == 'OUT_FOR_DELIVERY':
            order.status = 'SHIPPED'
            order.save()
            Notification.objects.create(
                user=order.user,
                title="Order Out for Delivery",
                message=f"Your order #{order.id} is out for delivery.",
                notification_type='BOTH'
            )
        return response_obj

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='read')
    def mark_as_read(self, request, pk=None):
        notification = get_object_or_404(Notification, id=pk, user=request.user)
        notification.is_read = True
        notification.save()
        return Response({"message": "Notification marked as read"}, status=status.HTTP_200_OK)

class AdminAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'ADMIN':
            return Response({"error": "Only admins can view analytics."}, status=status.HTTP_403_FORBIDDEN)
            
        total_customers = User.objects.filter(role=User.Roles.CUSTOMER).count()
        total_products = Product.objects.count()
        
        total_sales = Order.objects.filter(status='PAID').count()
        revenue = Order.objects.filter(status='PAID').aggregate(total=Sum('total_amount'))['total'] or 0.00
        
        pending_orders = Order.objects.filter(status='PENDING').count()
        completed_orders = Order.objects.filter(status='DELIVERED').count()
        
        low_stock_products = []
        for p in Product.objects.all():
            total_stock = p.stock + sum(v.stock for v in p.variants.all())
            if total_stock < 5:
                low_stock_products.append({
                    "id": p.id,
                    "name": p.name,
                    "sku": p.sku,
                    "stock": total_stock
                })
                
        best_selling_items = OrderItem.objects.values(
            'variant__product__id', 'variant__product__name'
        ).annotate(
            total_sold=Sum('quantity')
        ).order_by('-total_sold')[:5]
        
        best_selling = []
        for item in best_selling_items:
            if item['variant__product__id']:
                best_selling.append({
                    "id": item['variant__product__id'],
                    "name": item['variant__product__name'],
                    "total_sold": item['total_sold']
                })

        analytics_data = {
            "total_customers": total_customers,
            "total_products": total_products,
            "total_sales": total_sales,
            "revenue": float(revenue),
            "pending_orders": pending_orders,
            "completed_orders": completed_orders,
            "low_stock_products": low_stock_products,
            "best_selling_products": best_selling
        }
        
        return Response(analytics_data, status=status.HTTP_200_OK)