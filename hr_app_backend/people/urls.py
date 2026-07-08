from django.urls import path

from .views import (
    custom_field_detail_view,
    custom_fields_view,
    designation_detail_view,
    designations_view,
    emergency_contact_detail_view,
    emergency_contacts_view,
    employment_history_detail_view,
    employment_history_view,
    organization_chart_view,
    people_department_detail_view,
    people_departments_view,
    people_summary_view,
    team_detail_view,
    teams_view,
    employee_document_detail_view,
    employee_documents_view,
)

urlpatterns = [
    path('summary/', people_summary_view, name='people-summary'),
    path('organization-chart/', organization_chart_view, name='organization-chart'),
    path('departments/', people_departments_view, name='people-departments'),
    path('departments/<uuid:department_pk>/', people_department_detail_view, name='people-department-detail'),
    path('teams/', teams_view, name='people-teams'),
    path('teams/<uuid:team_pk>/', team_detail_view, name='people-team-detail'),
    path('designations/', designations_view, name='people-designations'),
    path('designations/<uuid:designation_pk>/', designation_detail_view, name='people-designation-detail'),
    path('employees/<uuid:employee_pk>/emergency-contacts/', emergency_contacts_view, name='employee-emergency-contacts'),
    path('employees/<uuid:employee_pk>/emergency-contacts/<uuid:contact_pk>/', emergency_contact_detail_view, name='employee-emergency-contact-detail'),
    path('employees/<uuid:employee_pk>/employment-history/', employment_history_view, name='employee-employment-history'),
    path('employees/<uuid:employee_pk>/employment-history/<uuid:entry_pk>/', employment_history_detail_view, name='employee-employment-history-detail'),
    path('employees/<uuid:employee_pk>/documents/', employee_documents_view, name='employee-documents'),
    path('employees/<uuid:employee_pk>/documents/<uuid:document_pk>/', employee_document_detail_view, name='employee-document-detail'),
    path('employees/<uuid:employee_pk>/custom-fields/', custom_fields_view, name='employee-custom-fields'),
    path('employees/<uuid:employee_pk>/custom-fields/<uuid:field_pk>/', custom_field_detail_view, name='employee-custom-field-detail'),
]
