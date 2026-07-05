from django.urls import path

from .views import leave_detail_view, leaves_view

urlpatterns = [
    path('', leaves_view, name='leaves'),
    path('<uuid:leave_pk>/', leave_detail_view, name='leave-detail'),
]
