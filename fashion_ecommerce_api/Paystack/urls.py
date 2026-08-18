from django.urls import path
from . import views

urlpatterns = [
    # Template views (legacy)
    path("pay/", views.start_payment, name="start_payment"),
    path("payment/callback/", views.payment_callback, name="payment_callback"),
    
    # REST API endpoints
    path("api/payments/initialize/", views.initialize_payment_api, name="payment_initialize_api"),
    path("api/payments/callback/", views.payment_callback_api, name="payment_callback_api"),
]