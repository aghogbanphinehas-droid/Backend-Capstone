from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    RegisterUserView,
    UserProfileView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    EmailVerificationRequestView,
    EmailVerificationConfirmView,
    AdminCustomerListView
)

urlpatterns = [
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', RegisterUserView.as_view(), name='auth_register'),
    path('auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('auth/reset-password/', PasswordResetRequestView.as_view(), name='auth_reset_password'),
    path('auth/reset-password/confirm/', PasswordResetConfirmView.as_view(), name='auth_reset_password_confirm'),
    path('auth/verify-email/', EmailVerificationRequestView.as_view(), name='auth_verify_email'),
    path('auth/verify-email/confirm/', EmailVerificationConfirmView.as_view(), name='auth_verify_email_confirm'),
    
    path('accounts/profile/', UserProfileView.as_view(), name='user_profile'),
    path('accounts/customers/', AdminCustomerListView.as_view(), name='admin_customers'),
]