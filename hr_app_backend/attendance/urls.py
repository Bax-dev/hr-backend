from django.urls import path

from .views import attendance_view, check_in_view, check_out_view, locations_view

urlpatterns = [
    path('', attendance_view, name='attendance'),
    path('locations/', locations_view, name='attendance-locations'),
    path('check-in/', check_in_view, name='attendance-check-in'),
    path('check-out/', check_out_view, name='attendance-check-out'),
]
