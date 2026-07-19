from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CartViewSet, OrderViewSet, CouponViewSet, ShipmentViewSet, 
    NotificationViewSet, PaystackInitializeView, PaystackVerifyView,
    PaymentHistoryView, PaymentRefundView, AdminAnalyticsView
)

router = DefaultRouter()
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'coupons', CouponViewSet, basename='coupons')
router.register(r'shipments', ShipmentViewSet, basename='shipments')
router.register(r'notifications', NotificationViewSet, basename='notifications')

urlpatterns = [
    path('', include(router.urls)),
    path('payments/initialize/', PaystackInitializeView.as_view(), name='payment-init'),
    path('payments/verify/', PaystackVerifyView.as_view(), name='payment-verify'),
    path('payments/history/', PaymentHistoryView.as_view(), name='payment-history'),
    path('payments/<int:pk>/refund/', PaymentRefundView.as_view(), name='payment-refund'),
    path('admin/analytics/', AdminAnalyticsView.as_view(), name='admin-analytics'),
]
