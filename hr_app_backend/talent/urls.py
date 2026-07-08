from django.urls import path

from .views import (
    learning_detail_view,
    learning_view,
    offboarding_detail_view,
    offboarding_view,
    onboarding_detail_view,
    onboarding_view,
    performance_detail_view,
    performance_view,
    talent_summary_view,
)

urlpatterns = [
    path('summary/', talent_summary_view, name='talent-summary'),
    path('onboarding/', onboarding_view, name='talent-onboarding'),
    path('onboarding/<uuid:record_pk>/', onboarding_detail_view, name='talent-onboarding-detail'),
    path('performance/', performance_view, name='talent-performance'),
    path('performance/<uuid:record_pk>/', performance_detail_view, name='talent-performance-detail'),
    path('learning/', learning_view, name='talent-learning'),
    path('learning/<uuid:record_pk>/', learning_detail_view, name='talent-learning-detail'),
    path('offboarding/', offboarding_view, name='talent-offboarding'),
    path('offboarding/<uuid:record_pk>/', offboarding_detail_view, name='talent-offboarding-detail'),
]
