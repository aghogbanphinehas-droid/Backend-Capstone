import uuid
from django.conf import settings
from paystackapi.paystack import Paystack

paystack = Paystack(secret_key="sk_test_29bfdfaf399a7fa338444aff100ddff6b81de19f")


def initialize_transaction(email, amount_naira, callback_url):
    """amount_naira: amount in Naira (will be converted to kobo)."""
    reference = str(uuid.uuid4())  # unique per transaction — never hardcode this
    response = paystack.transaction.initialize(
        reference=reference,
        amount=int(amount_naira * 100),  # NGN -> kobo
        email=email,
        callback_url=callback_url,
    )
    return response, reference


def verify_transaction(reference):
    return paystack.transaction.verify(reference=reference)








# # Create a transaction
# response = paystack.transaction.initialize(
#     reference="unique_transaction_ref_123",
#     amount=500000,  # Amount in kobo (500000 kobo = 5000 NGN)
#     email="customer@email.com",
#     callback_url="https://yourwebsite.com"
# )

# # Get the checkout URL
# payment_url = response['data']['authorization_url']
# print(f"Send client to: {payment_url}")


# # Verify using the unique reference
# verification = paystack.transaction.verify(reference="unique_transaction_ref_123")

# if verification['data']['status'] == 'success':
#     print("Payment successful!")
# else:
#     print("Payment failed or pending.")