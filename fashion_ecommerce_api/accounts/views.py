from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .models import User
from .serializers import (
    UserRegistrationSerializer, 
    UserProfileSerializer, 
    PasswordResetRequestSerializer, 
    PasswordResetConfirmSerializer,
    EmailVerificationRequestSerializer,
    EmailVerificationConfirmSerializer
)
from orders.models import Notification

class RegisterUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserRegistrationSerializer

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            
            reset_link = f"/api/auth/reset-password/confirm/?uidb64={uidb64}&token={token}"
            print(f"\n--- PASSWORD RESET REQUEST ---")
            print(f"User: {email}")
            print(f"UIDB64: {uidb64}")
            print(f"Token: {token}")
            print(f"Simulated Link: {reset_link}")
            print(f"---------------------------------\n")

            Notification.objects.create(
                user=user,
                title="Password Reset Request",
                message=f"Use token {token} and uidb64 {uidb64} to reset your password.",
                notification_type='EMAIL'
            )
        except User.DoesNotExist:
            pass

        return Response({"message": "Password reset token sent if email exists."}, status=status.HTTP_200_OK)

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        new_password = serializer.validated_data['new_password']
        
        user.set_password(new_password)
        user.save()

        Notification.objects.create(
            user=user,
            title="Password Reset Successful",
            message="Your password has been successfully reset.",
            notification_type='EMAIL'
        )
        return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)

class EmailVerificationRequestView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmailVerificationRequestSerializer

    def post(self, request):
        user = request.user
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        verify_link = f"/api/auth/verify-email/confirm/?uidb64={uidb64}&token={token}"
        print(f"\n--- EMAIL VERIFICATION REQUEST ---")
        print(f"User: {user.email}")
        print(f"UIDB64: {uidb64}")
        print(f"Token: {token}")
        print(f"Simulated Link: {verify_link}")
        print(f"------------------------------------\n")

        Notification.objects.create(
            user=user,
            title="Verify Your Email Address",
            message=f"Use token {token} and uidb64 {uidb64} to verify your email.",
            notification_type='EMAIL'
        )
        return Response({"message": "Verification token sent to email."}, status=status.HTTP_200_OK)

class EmailVerificationConfirmView(APIView):
    permission_classes = [AllowAny]
    serializer_class = EmailVerificationConfirmSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        user.is_email_verified = True
        user.save()

        Notification.objects.create(
            user=user,
            title="Email Verified Successfully",
            message="Your email address has been verified.",
            notification_type='SYSTEM'
        )
        return Response({"message": "Email address verified successfully."}, status=status.HTTP_200_OK)

class AdminCustomerListView(generics.ListAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role != 'ADMIN':
            raise PermissionDenied("Only admin users can view the customer list.")
        return User.objects.filter(role=User.Roles.CUSTOMER)