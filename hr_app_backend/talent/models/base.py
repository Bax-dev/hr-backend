from django.db import models


class TalentStatusMixin(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_APPROVED = 'approved'
    STATUS_CLOSED = 'closed'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_ARCHIVED, 'Archived'),
    ]

    class Meta:
        abstract = True


class TalentPriorityMixin(models.Model):
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CRITICAL = 'critical'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_CRITICAL, 'Critical'),
    ]

    class Meta:
        abstract = True
