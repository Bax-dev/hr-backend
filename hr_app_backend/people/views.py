from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.departments.serializers import department_payload, serialize_department
from hr_app_backend.departments.services import (
    create_department,
    delete_department,
    get_department,
    list_departments,
    update_department,
)
from hr_app_backend.employees.serializers import (
    custom_field_payload,
    designation_payload,
    emergency_contact_payload,
    employee_document_payload,
    employment_history_payload,
    serialize_custom_field,
    serialize_designation,
    serialize_emergency_contact,
    serialize_employee_document,
    serialize_employment_history,
    serialize_team,
    team_payload,
)
from hr_app_backend.employees.services import (
    build_organization_chart,
    build_people_summary,
    create_custom_field,
    create_designation,
    create_emergency_contact,
    create_employee_document,
    create_employment_history,
    create_team,
    delete_custom_field,
    delete_designation,
    delete_emergency_contact,
    delete_employee_document,
    delete_employment_history,
    delete_team,
    get_employee,
    list_custom_fields,
    list_designations,
    list_emergency_contacts,
    list_employee_documents,
    list_employment_history,
    list_teams,
    update_custom_field,
    update_designation,
    update_emergency_contact,
    update_employee_document,
    update_employment_history,
    update_team,
)
from hr_app_backend.employees.views.helpers import require_user
from hr_app_backend.utils.errors import AppError
from hr_app_backend.utils.pagination import paginated_data


@require_http_methods(['GET'])
def people_summary_view(request):
    try:
        user = require_user(request)
        return JsonResponse({'success': True, 'data': build_people_summary(user)})
    except AppError as exc:
        return error_response(exc)


@require_http_methods(['GET'])
def organization_chart_view(request):
    try:
        user = require_user(request)
        return JsonResponse({'success': True, 'data': {'nodes': build_organization_chart(user)}})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def people_departments_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            departments, counts = list_departments(user, search=request.GET.get('search'))
            return JsonResponse({
                'success': True,
                'data': paginated_data(
                    request,
                    departments,
                    lambda department: serialize_department(
                        department,
                        counts.get(department.name.strip().lower(), 0),
                    ),
                    key='departments',
                ),
            })

        department = create_department(user, department_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'department': serialize_department(department, 0)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def people_department_detail_view(request, department_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            department = get_department(user, department_pk)
            return JsonResponse({'success': True, 'data': {'department': serialize_department(department, 0)}})

        if request.method == 'DELETE':
            delete_department(user, department_pk)
            return JsonResponse({'success': True, 'message': 'Department deleted successfully.'})

        department = update_department(user, department_pk, department_payload(parse_json_body(request), partial=True))
        return JsonResponse({'success': True, 'data': {'department': serialize_department(department, 0)}})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def teams_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            teams = list_teams(
                user,
                search=request.GET.get('search'),
                department_id=request.GET.get('department_id') or request.GET.get('departmentId'),
            )
            return JsonResponse({
                'success': True,
                'data': paginated_data(
                    request,
                    teams,
                    lambda team: serialize_team(team, getattr(team, 'member_count', 0)),
                    key='teams',
                ),
            })

        team = create_team(user, team_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'team': serialize_team(team)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def team_detail_view(request, team_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            team = _annotate_team(user, team_pk)
            return JsonResponse({'success': True, 'data': {'team': serialize_team(team, getattr(team, 'member_count', 0))}})

        if request.method == 'DELETE':
            delete_team(user, team_pk)
            return JsonResponse({'success': True, 'message': 'Team deleted successfully.'})

        team = update_team(user, team_pk, team_payload(parse_json_body(request), partial=True))
        return JsonResponse({'success': True, 'data': {'team': serialize_team(team)}})
    except AppError as exc:
        return error_response(exc)


def _annotate_team(user, team_pk):
    team = next((entry for entry in list_teams(user) if str(entry.id) == str(team_pk)), None)
    if team is None:
        raise AppError('Team not found.', status_code=404)
    return team


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def designations_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            designations = list_designations(user, search=request.GET.get('search'))
            return JsonResponse({
                'success': True,
                'data': paginated_data(
                    request,
                    designations,
                    lambda designation: serialize_designation(designation, getattr(designation, 'employee_count', 0)),
                    key='designations',
                ),
            })

        designation = create_designation(user, designation_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'designation': serialize_designation(designation)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def designation_detail_view(request, designation_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            designation = _annotate_designation(user, designation_pk)
            return JsonResponse({'success': True, 'data': {'designation': serialize_designation(designation, getattr(designation, 'employee_count', 0))}})

        if request.method == 'DELETE':
            delete_designation(user, designation_pk)
            return JsonResponse({'success': True, 'message': 'Designation deleted successfully.'})

        designation = update_designation(user, designation_pk, designation_payload(parse_json_body(request), partial=True))
        return JsonResponse({'success': True, 'data': {'designation': serialize_designation(designation)}})
    except AppError as exc:
        return error_response(exc)


def _annotate_designation(user, designation_pk):
    designation = next((entry for entry in list_designations(user) if str(entry.id) == str(designation_pk)), None)
    if designation is None:
        raise AppError('Designation not found.', status_code=404)
    return designation


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def emergency_contacts_view(request, employee_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            employee = get_employee(user, employee_pk)
            contacts = list_emergency_contacts(user, employee_pk)
            return JsonResponse({
                'success': True,
                'data': {
                    'employee_id': str(employee.id),
                    'contacts': [serialize_emergency_contact(contact) for contact in contacts],
                },
            })

        contact = create_emergency_contact(user, employee_pk, emergency_contact_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'contact': serialize_emergency_contact(contact)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def emergency_contact_detail_view(request, employee_pk, contact_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            contact = next((entry for entry in list_emergency_contacts(user, employee_pk) if str(entry.id) == str(contact_pk)), None)
            if contact is None:
                raise AppError('Emergency contact not found.', status_code=404)
            return JsonResponse({'success': True, 'data': {'contact': serialize_emergency_contact(contact)}})

        if request.method == 'DELETE':
            delete_emergency_contact(user, employee_pk, contact_pk)
            return JsonResponse({'success': True, 'message': 'Emergency contact deleted successfully.'})

        contact = update_emergency_contact(
            user,
            employee_pk,
            contact_pk,
            emergency_contact_payload(parse_json_body(request), partial=True),
        )
        return JsonResponse({'success': True, 'data': {'contact': serialize_emergency_contact(contact)}})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def employment_history_view(request, employee_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            history = list_employment_history(user, employee_pk)
            return JsonResponse({'success': True, 'data': {'entries': [serialize_employment_history(entry) for entry in history]}})

        entry = create_employment_history(user, employee_pk, employment_history_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'entry': serialize_employment_history(entry)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def employment_history_detail_view(request, employee_pk, entry_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            entry = next((item for item in list_employment_history(user, employee_pk) if str(item.id) == str(entry_pk)), None)
            if entry is None:
                raise AppError('Employment history entry not found.', status_code=404)
            return JsonResponse({'success': True, 'data': {'entry': serialize_employment_history(entry)}})

        if request.method == 'DELETE':
            delete_employment_history(user, employee_pk, entry_pk)
            return JsonResponse({'success': True, 'message': 'Employment history entry deleted successfully.'})

        entry = update_employment_history(
            user,
            employee_pk,
            entry_pk,
            employment_history_payload(parse_json_body(request), partial=True),
        )
        return JsonResponse({'success': True, 'data': {'entry': serialize_employment_history(entry)}})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def employee_documents_view(request, employee_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            documents = list_employee_documents(user, employee_pk)
            return JsonResponse({'success': True, 'data': {'documents': [serialize_employee_document(document) for document in documents]}})

        document = create_employee_document(user, employee_pk, employee_document_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'document': serialize_employee_document(document)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def employee_document_detail_view(request, employee_pk, document_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            document = next((item for item in list_employee_documents(user, employee_pk) if str(item.id) == str(document_pk)), None)
            if document is None:
                raise AppError('Employee document not found.', status_code=404)
            return JsonResponse({'success': True, 'data': {'document': serialize_employee_document(document)}})

        if request.method == 'DELETE':
            delete_employee_document(user, employee_pk, document_pk)
            return JsonResponse({'success': True, 'message': 'Employee document deleted successfully.'})

        document = update_employee_document(
            user,
            employee_pk,
            document_pk,
            employee_document_payload(parse_json_body(request), partial=True),
        )
        return JsonResponse({'success': True, 'data': {'document': serialize_employee_document(document)}})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def custom_fields_view(request, employee_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            fields = list_custom_fields(user, employee_pk)
            return JsonResponse({'success': True, 'data': {'fields': [serialize_custom_field(field) for field in fields]}})

        field = create_custom_field(user, employee_pk, custom_field_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'field': serialize_custom_field(field)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def custom_field_detail_view(request, employee_pk, field_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            field = next((item for item in list_custom_fields(user, employee_pk) if str(item.id) == str(field_pk)), None)
            if field is None:
                raise AppError('Custom field not found.', status_code=404)
            return JsonResponse({'success': True, 'data': {'field': serialize_custom_field(field)}})

        if request.method == 'DELETE':
            delete_custom_field(user, employee_pk, field_pk)
            return JsonResponse({'success': True, 'message': 'Custom field deleted successfully.'})

        field = update_custom_field(
            user,
            employee_pk,
            field_pk,
            custom_field_payload(parse_json_body(request), partial=True),
        )
        return JsonResponse({'success': True, 'data': {'field': serialize_custom_field(field)}})
    except AppError as exc:
        return error_response(exc)
