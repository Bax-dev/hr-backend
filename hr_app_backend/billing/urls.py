from django.urls import path

from .views import initialize_subscription_payment_view, verify_subscription_payment_view

urlpatterns = [
    path('subscriptions/initialize/', initialize_subscription_payment_view, name='subscription-initialize'),
    path('subscriptions/verify/', verify_subscription_payment_view, name='subscription-verify'),
]
