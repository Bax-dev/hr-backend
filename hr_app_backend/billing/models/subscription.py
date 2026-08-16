from django.conf import settings
from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel


class Subscription(TimeStampedModel):
    PLAN_FREE_TRIAL = 'free_trial'
    PLAN_STARTER = 'starter'
    PLAN_GROWTH = 'growth'
    PLAN_ENTERPRISE = 'enterprise'
    PLAN_CHOICES = [
        (PLAN_FREE_TRIAL, 'Free'),
        (PLAN_STARTER, 'Essential'),
        (PLAN_GROWTH, 'Premium'),
        (PLAN_ENTERPRISE, 'Enterprise'),
    ]

    PROVIDER_PAYSTACK = 'paystack'
    PROVIDER_FLUTTERWAVE = 'flutterwave'
    PROVIDER_CHOICES = [
        (PROVIDER_PAYSTACK, 'Paystack'),
        (PROVIDER_FLUTTERWAVE, 'Flutterwave'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.CASCADE, related_name='subscriptions')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reference = models.CharField(max_length=64, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='NGN')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    payment_url = models.URLField(blank=True)
    access_code = models.CharField(max_length=128, blank=True)
    gateway_transaction_id = models.CharField(max_length=128, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)

    # Set once each expiry reminder has been emailed, so a daily job never
    # sends the same window's reminder twice for the same subscription.
    reminder_5d_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_2d_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_1d_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        owner = self.organization.name if self.organization else self.created_by.email
        return f'{owner} - {self.plan} ({self.reference})'
