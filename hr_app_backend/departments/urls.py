from django.urls import path

from .views import department_detail_view, departments_view

urlpatterns = [
    path('', departments_view, name='departments'),
    path('<uuid:department_pk>/', department_detail_view, name='department-detail'),
]
