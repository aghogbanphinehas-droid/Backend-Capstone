from django.shortcuts import render

# Create your views here.
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib import messages
from .utils import initialize_transaction, verify_transaction


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