from django.urls import include, path

urlpatterns = [
    path("v1/", include(("hr_app_backend.api.v1.urls", "v1"), namespace="v1")),
]
