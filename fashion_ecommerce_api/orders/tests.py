from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from store.models import Category, Brand, Product, ProductVariant
from orders.models import Cart, CartItem, Order, OrderItem, Coupon, Payment, Shipment, Notification

User = get_user_model()

class OrdersAndPaymentsTests(APITestCase):
    def setUp(self):
        # Create users
        self.admin_user = User.objects.create_user(
            email='admin@example.com', username='admin@example.com', password='Password123!', role='ADMIN'
        )
        self.customer_user = User.objects.create_user(
            email='customer@example.com', username='customer@example.com', password='Password123!', role='CUSTOMER'
        )

        # Create Category and Brand
        self.category = Category.objects.create(name='Men', slug='men')
        self.brand = Brand.objects.create(name='Zara')

        # Create Product and Variants
        self.product = Product.objects.create(
            name='Summer Jeans',
            slug='summer-jeans',
            description='Blue slim fit jeans',
            category=self.category,
            brand=self.brand,
            sku='JEANS-SUM-002',
            price=200.00,
            stock=100,
            status='PUBLISHED',
            created_by=self.admin_user
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            size='32',
            color='Blue',
            stock=10,
            sku='JEANS-SUM-002-32-BLU'
        )

        # URLs
        self.cart_url = reverse('cart-list') # Maps to CartViewSet list/create
        self.orders_url = reverse('orders-list')
        self.coupon_url = reverse('coupons-list')
        self.payment_history_url = reverse('payment-history')
        self.analytics_url = reverse('admin-analytics')

    def test_cart_operations(self):
        """Ensure full CRUD cart actions work correctly."""
        self.client.force_authenticate(user=self.customer_user)

        # 1. Add item to cart (POST /api/cart/)
        cart_data = {'variant_id': self.variant.id, 'quantity': 2}
        response = self.client.post(self.cart_url, cart_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['items'][0]['quantity'], 2)
        
        # 2. View Cart (GET /api/cart/)
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['total_price']), 400.00)
        
        # Get cart item ID
        cart_item_id = response.data['items'][0]['id']
        cart_detail_url = reverse('cart-detail', args=[cart_item_id])

        # 3. Update quantity (PUT /api/cart/{id}/)
        response = self.client.put(cart_detail_url, {'quantity': 5}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['items'][0]['quantity'], 5)

        # 4. Remove item (DELETE /api/cart/{id}/)
        response = self.client.delete(cart_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 0)

    def test_checkout_and_coupon_application(self):
        """Ensure order checkout deducts stock and applies coupons correctly."""
        # Create a Coupon
        start = timezone.now() - timezone.timedelta(days=1)
        end = timezone.now() + timezone.timedelta(days=5)
        coupon = Coupon.objects.create(
            code='SAVE50',
            discount_type='FIXED',
            discount_value=50.00,
            active=True,
            start_date=start,
            end_date=end,
            usage_limit=10
        )

        # Add item to cart
        self.client.force_authenticate(user=self.customer_user)
        self.client.post(self.cart_url, {'variant_id': self.variant.id, 'quantity': 2}, format='json')

        # Checkout with coupon
        order_data = {
            'address': '123 Capstone Ave, Lagos',
            'coupon_code': 'SAVE50'
        }
        response = self.client.post(self.orders_url, order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(response.data['total_amount']), 350.00) # (200 * 2) - 50 = 350
        self.assertEqual(float(response.data['discount_amount']), 50.00)

        # Check stock deduction
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 8) # 10 - 2 = 8

        # Test Order Cancellation restores stock
        order_id = response.data['id']
        cancel_url = reverse('orders-cancel-order', args=[order_id])
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'CANCELLED')

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 10) # Restored back to 10!

    def test_invoice_generation(self):
        """Ensure invoice generation matches expectations."""
        self.client.force_authenticate(user=self.customer_user)
        # Add item and checkout
        self.client.post(self.cart_url, {'variant_id': self.variant.id, 'quantity': 1}, format='json')
        order_response = self.client.post(self.orders_url, {'address': 'Lagos'}, format='json')
        
        order_id = order_response.data['id']
        invoice_url = reverse('orders-invoice', args=[order_id])
        
        response = self.client.get(invoice_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('invoice_number', response.data)
        self.assertEqual(response.data['total_amount'], 200.00)

    def test_shipment_delivery_and_notifications(self):
        """Ensure shipments and notifications work, and shipment updates affect order status."""
        self.client.force_authenticate(user=self.customer_user)
        # Place order
        self.client.post(self.cart_url, {'variant_id': self.variant.id, 'quantity': 1}, format='json')
        order_resp = self.client.post(self.orders_url, {'address': 'Shipping address'}, format='json')
        order_id = order_resp.data['id']
        order = Order.objects.get(id=order_id)
        
        # Simulating payment verified (creates shipment)
        order.status = 'PAID'
        order.save()
        shipment, _ = Shipment.objects.get_or_create(order=order, defaults={'status': 'PENDING'})

        # Admin updates shipment to DELIVERED
        self.client.force_authenticate(user=self.admin_user)
        shipment_detail_url = reverse('shipments-detail', args=[shipment.id])
        response = self.client.patch(shipment_detail_url, {'status': 'DELIVERED'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Order status must automatically shift to DELIVERED
        order.refresh_from_db()
        self.assertEqual(order.status, 'DELIVERED')

        # Check notification creation
        self.client.force_authenticate(user=self.customer_user)
        notif_url = reverse('notifications-list')
        response = self.client.get(notif_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)
        self.assertEqual(response.data[0]['title'], 'Shipment Delivered')

    def test_admin_analytics_dashboard(self):
        """Ensure analytics dashboard returns correct data for admins and denies customers."""
        # 1. Customers should be denied
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(self.analytics_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Admins should get correct statistics
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.analytics_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_customers', response.data)
        self.assertIn('total_products', response.data)
        self.assertIn('revenue', response.data)
