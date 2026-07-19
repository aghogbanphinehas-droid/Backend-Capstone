from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from accounts.models import User, CustomerProfile

class AuthenticationTests(APITestCase):
    def setUp(self):
        self.register_url = reverse('auth_register')
        self.login_url = reverse('token_obtain_pair')
        self.logout_url = reverse('auth_logout')
        self.profile_url = reverse('user_profile')
        self.reset_req_url = reverse('auth_reset_password')
        self.reset_conf_url = reverse('auth_reset_password_confirm')
        self.verify_req_url = reverse('auth_verify_email')
        self.verify_conf_url = reverse('auth_verify_email_confirm')
        
        self.user_data = {
            'email': 'testuser@example.com',
            'password': 'StrongPassword123!',
            'first_name': 'Test',
            'last_name': 'User'
        }

    def test_user_registration(self):
        """Ensure a new user can register successfully."""
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().email, 'testuser@example.com')

    def test_user_login(self):
        """Ensure a registered user can log in and receive JWT tokens."""
        User.objects.create_user(
            email='testuser@example.com', 
            username='testuser@example.com', 
            password='StrongPassword123!', 
            role='CUSTOMER'
        )
        
        login_data = {'email': 'testuser@example.com', 'password': 'StrongPassword123!'}
        response = self.client.post(self.login_url, login_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_profile_retrieval_and_update(self):
        """Ensure a logged-in user can retrieve and update their profile."""
        user = User.objects.create_user(
            email='testuser@example.com', 
            username='testuser@example.com', 
            password='StrongPassword123!', 
            role='CUSTOMER'
        )
        CustomerProfile.objects.get_or_create(user=user)
        
        # Authenticate
        self.client.force_authenticate(user=user)
        
        # Retrieve Profile
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'testuser@example.com')
        
        # Update Profile
        update_data = {
            'first_name': 'UpdatedFirst',
            'last_name': 'UpdatedLast',
            'profile': {
                'phone_number': '1234567890',
                'address': '123 Test Street',
                'city': 'Lagos',
                'country': 'Nigeria'
            }
        }
        response = self.client.put(self.profile_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'UpdatedFirst')
        self.assertEqual(user.profile.phone_number, '1234567890')
        self.assertEqual(user.profile.city, 'Lagos')

    def test_logout(self):
        """Ensure a logged-in user can logout and blacklist their refresh token."""
        user = User.objects.create_user(
            email='testuser@example.com', 
            username='testuser@example.com', 
            password='StrongPassword123!', 
            role='CUSTOMER'
        )
        self.client.force_authenticate(user=user)
        
        # Obtain tokens
        login_data = {'email': 'testuser@example.com', 'password': 'StrongPassword123!'}
        login_response = self.client.post(self.login_url, login_data, format='json')
        refresh_token = login_response.data['refresh']
        
        # Logout
        logout_response = self.client.post(self.logout_url, {'refresh': refresh_token}, format='json')
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)
        
        # Attempt to use the same refresh token to get a new access token (should fail)
        refresh_url = reverse('token_refresh')
        refresh_response = self.client.post(refresh_url, {'refresh': refresh_token}, format='json')
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_flow(self):
        """Ensure password reset requesting and confirmation works."""
        user = User.objects.create_user(
            email='testuser@example.com', 
            username='testuser@example.com', 
            password='StrongPassword123!', 
            role='CUSTOMER'
        )
        
        # Request password reset
        response = self.client.post(self.reset_req_url, {'email': 'testuser@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Generate token manually for test confirmation
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        # Confirm password reset
        confirm_data = {
            'uidb64': uidb64,
            'token': token,
            'new_password': 'NewStrongPassword123!'
        }
        response = self.client.post(self.reset_conf_url, confirm_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check login with new password
        login_data = {'email': 'testuser@example.com', 'password': 'NewStrongPassword123!'}
        login_response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_email_verification_flow(self):
        """Ensure email verification requesting and confirmation works."""
        user = User.objects.create_user(
            email='testuser@example.com', 
            username='testuser@example.com', 
            password='StrongPassword123!', 
            role='CUSTOMER'
        )
        self.client.force_authenticate(user=user)
        
        # Request verification
        response = self.client.post(self.verify_req_url, {'email': 'testuser@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Manually construct tokens for confirm verification
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        # Confirm email verification
        self.client.logout() # Test can be done anonymously
        confirm_data = {
            'uidb64': uidb64,
            'token': token
        }
        response = self.client.post(self.verify_conf_url, confirm_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)