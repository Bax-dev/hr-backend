from django.urls import path

from .views import employee_detail_view, employees_view

urlpatterns = [
    path('', employees_view, name='employees'),
    path('<uuid:employee_pk>/', employee_detail_view, name='employee-detail'),
]
