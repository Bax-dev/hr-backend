from django.urls import path

from .views import (
    initialize_paid_signup_checkout_view,
    initialize_subscription_payment_view,
    verify_paid_signup_checkout_view,
    verify_subscription_payment_view,
)

urlpatterns = [
    path('subscriptions/initialize/', initialize_subscription_payment_view, name='subscription-initialize'),
    path('subscriptions/verify/', verify_subscription_payment_view, name='subscription-verify'),
    path('signup/initialize/', initialize_paid_signup_checkout_view, name='signup-checkout-initialize'),
    path('signup/verify/', verify_paid_signup_checkout_view, name='signup-checkout-verify'),
]
