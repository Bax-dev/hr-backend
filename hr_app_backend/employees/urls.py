from django.urls import path

from .views import employee_detail_view, employee_hr_admin_view, employees_view, my_employee_view

urlpatterns = [
    path('', employees_view, name='employees'),
    path('me/', my_employee_view, name='employee-me'),
    path('<uuid:employee_pk>/', employee_detail_view, name='employee-detail'),
    path('<uuid:employee_pk>/hr-admin/', employee_hr_admin_view, name='employee-hr-admin'),
]
