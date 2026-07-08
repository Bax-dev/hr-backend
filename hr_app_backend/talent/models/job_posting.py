from django.db import models

from hr_app_backend.authentication.models import Organization


class JobPosting(models.Model):
    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='job_postings')
    title = models.CharField(max_length=150)
    department = models.CharField(max_length=150)
    location = models.CharField(max_length=150)
    type = models.CharField(max_length=64)
    status = models.CharField(max_length=32)
    applicants = models.PositiveIntegerField(default=0)
    posted_date = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-posted_date', '-id']
