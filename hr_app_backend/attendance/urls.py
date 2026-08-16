from django.urls import path

from .views import (
    attendance_view,
    check_in_view,
    check_out_view,
    location_detail_view,
    locations_view,
    mark_remote_view,
    remote_workers_view,
)

urlpatterns = [
    path('', attendance_view, name='attendance'),
    path('locations/', locations_view, name='attendance-locations'),
    path('locations/<uuid:location_pk>/', location_detail_view, name='attendance-location-detail'),
    path('check-in/', check_in_view, name='attendance-check-in'),
    path('check-out/', check_out_view, name='attendance-check-out'),
    path('remote/', mark_remote_view, name='attendance-mark-remote'),
    path('remote-workers/', remote_workers_view, name='attendance-remote-workers'),
]
