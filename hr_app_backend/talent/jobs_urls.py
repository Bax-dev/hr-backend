from django.urls import path

from .views import job_detail_view, jobs_view

urlpatterns = [
    path('', jobs_view, name='jobs'),
    path('<int:job_id>', job_detail_view, name='job-detail'),
    path('<int:job_id>/', job_detail_view, name='job-detail-slash'),
]
