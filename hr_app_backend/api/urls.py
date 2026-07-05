from django.urls import include, path

from .docs import openapi_spec_view, swagger_ui_view

urlpatterns = [
    path('departments/', include('hr_app_backend.departments.urls')),
    path("docs/", swagger_ui_view, name="swagger-ui"),
    path("docs/openapi.yaml", openapi_spec_view, name="openapi-spec"),
    path("v1/", include(("hr_app_backend.api.v1.urls", "v1"), namespace="v1")),
]
