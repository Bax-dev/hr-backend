import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from hr_app_backend.authentication.models import Organization, UserProfile
from hr_app_backend.authentication.serializers.user import serialize_user
from hr_app_backend.billing.models import Subscription
from hr_app_backend.middleware.api_errors import ApiExceptionMiddleware
from hr_app_backend.utils.errors import PermissionDeniedError, ValidationError

from .models import Employee
from .serializers import serialize_employee
from .services import get_my_employee, list_employees, set_employee_hr_admin


class HrAdminAccessTests(TestCase):
    def setUp(self):
        sessions = patch('hr_app_backend.employees.services.employees.destroy_all_sessions_for_user')
        self.destroy_sessions = sessions.start()
        self.addCleanup(sessions.stop)

        users = get_user_model()
        self.organization = Organization.objects.create(name='Acme', email='owner@acme.test', phone='123')
        self.owner = users.objects.create_user(username='owner', email='owner@acme.test', password='pass')
        UserProfile.objects.create(
            user=self.owner, account_type=UserProfile.ACCOUNT_TYPE_COMPANY, organization=self.organization
        )
        self.employee = Employee.objects.create(
            organization=self.organization, employee_id='E-1', first_name='Ngozi', last_name='Okafor',
            email='ngozi@acme.test',
        )
        self.staff = users.objects.create_user(username='ngozi', email='ngozi@acme.test', password='pass')
        self.staff_profile = UserProfile.objects.create(
            user=self.staff, account_type=UserProfile.ACCOUNT_TYPE_INDIVIDUAL,
            organization=self.organization, employee=self.employee,
        )
        self.no_portal = Employee.objects.create(
            organization=self.organization, employee_id='E-2', first_name='Tunde', last_name='Bakare',
            email='tunde@acme.test',
        )

    def _subscribe(self, plan):
        Subscription.objects.create(
            organization=self.organization, created_by=self.owner, plan=plan, status=Subscription.STATUS_ACTIVE,
            amount=0, reference=f'ref-{plan}', provider=Subscription.PROVIDER_PAYSTACK, start_date='2026-11-01',
        )

    def test_grant_makes_employee_a_company_admin_and_signs_them_out(self):
        self._subscribe(Subscription.PLAN_GROWTH)
        employee = set_employee_hr_admin(self.owner, self.employee.pk, True)

        self.staff_profile.refresh_from_db()
        self.assertEqual(self.staff_profile.account_type, UserProfile.ACCOUNT_TYPE_COMPANY)
        self.assertTrue(serialize_employee(employee)['is_hr_admin'])
        self.destroy_sessions.assert_called_once_with(self.staff.id)
        # The promoted employee now passes admin-only checks.
        self.assertEqual(list_employees(self.staff).count(), 2)
        self.assertEqual(serialize_user(self.staff)['workspace_role'], 'hr_admin')
        self.assertEqual(serialize_user(self.owner)['workspace_role'], 'owner')

    def test_revoke_returns_employee_to_staff_access(self):
        self._subscribe(Subscription.PLAN_GROWTH)
        set_employee_hr_admin(self.owner, self.employee.pk, True)
        set_employee_hr_admin(self.owner, self.employee.pk, False)

        self.staff_profile.refresh_from_db()
        self.assertEqual(self.staff_profile.account_type, UserProfile.ACCOUNT_TYPE_INDIVIDUAL)
        with self.assertRaises(PermissionDeniedError):
            list_employees(self.staff)

    def test_free_plan_allows_only_one_admin(self):
        self._subscribe(Subscription.PLAN_FREE_TRIAL)
        with self.assertRaises(ValidationError) as ctx:
            set_employee_hr_admin(self.owner, self.employee.pk, True)
        self.assertEqual(ctx.exception.code, 'PLAN_ADMIN_LIMIT')

    def test_requires_portal_account(self):
        self._subscribe(Subscription.PLAN_GROWTH)
        with self.assertRaises(ValidationError):
            set_employee_hr_admin(self.owner, self.no_portal.pk, True)

    def test_staff_cannot_grant_access(self):
        with self.assertRaises(PermissionDeniedError):
            set_employee_hr_admin(self.staff, self.no_portal.pk, True)

    def test_admin_cannot_change_own_access(self):
        self._subscribe(Subscription.PLAN_GROWTH)
        set_employee_hr_admin(self.owner, self.employee.pk, True)
        with self.assertRaises(PermissionDeniedError):
            set_employee_hr_admin(self.staff, self.employee.pk, False)

    def test_owner_resolves_own_directory_record_by_email(self):
        self.assertIsNone(get_my_employee(self.owner))
        record = Employee.objects.create(
            organization=self.organization, employee_id='E-3', first_name='Owner', last_name='Person',
            email='OWNER@acme.test',
        )
        self.assertEqual(get_my_employee(self.owner), record)


class ApiExceptionMiddlewareTests(TestCase):
    def setUp(self):
        self.middleware = ApiExceptionMiddleware(lambda request: None)
        self.factory = RequestFactory()

    def test_unhandled_api_error_returns_json_envelope(self):
        request = self.factory.post('/api/v1/ai/assistant/')
        request.request_id = 'req-1'
        with self.assertLogs('hr_app_backend.middleware.api_errors', level='ERROR'):
            response = self.middleware.process_exception(request, RuntimeError('boom'))
        body = json.loads(response.content)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(body['success'])
        self.assertNotIn('boom', body['message'])
        self.assertEqual(body['requestId'], 'req-1')

    def test_non_api_paths_are_left_to_django(self):
        request = self.factory.get('/admin/')
        self.assertIsNone(self.middleware.process_exception(request, RuntimeError('boom')))
