from django.urls import include, path

from hr_app_backend.employees.views import celebrations_view

from .docs import openapi_spec_view, swagger_ui_view

urlpatterns = [
    path('celebrations', celebrations_view, name='celebrations'),
    path('celebrations/', celebrations_view, name='celebrations-slash'),
    path('departments/', include('hr_app_backend.departments.urls')),
    path('jobs/', include('hr_app_backend.talent.jobs_urls')),
    path("docs/", swagger_ui_view, name="swagger-ui"),
    path("docs/openapi.yaml", openapi_spec_view, name="openapi-spec"),
    path("v1/", include(("hr_app_backend.api.v1.urls", "v1"), namespace="v1")),
]
