import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from hr_app_backend.authentication.models import Organization, UserProfile
from hr_app_backend.billing.models import Subscription
from hr_app_backend.employees.models import Employee

from .views.companies import company_list_view, company_status_view
from .views.records import archived_records_view
from .views.users import user_list_view


class SuperadminAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.factory = RequestFactory()
        self.organization = Organization.objects.create(name='Northstar Labs', email='admin@northstar.test', phone='1')
        self.superuser = user_model.objects.create_superuser(
            username='root@platform.test', email='root@platform.test', password='pass'
        )
        self.company_admin = user_model.objects.create_user(
            username='admin@northstar.test', email='admin@northstar.test', password='pass'
        )
        UserProfile.objects.create(
            user=self.company_admin, account_type=UserProfile.ACCOUNT_TYPE_COMPANY,
            organization=self.organization, full_name='Northstar Admin',
        )

    def _get(self, view, user, path, query=''):
        request = self.factory.get(f'{path}{query}', HTTP_AUTHORIZATION='Bearer token')
        with patch('hr_app_backend.employees.views.helpers.get_user_by_token', return_value=user):
            return view(request)

    def test_non_superuser_gets_403(self):
        response = self._get(company_list_view, self.company_admin, '/api/v1/superadmin/companies/')
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_list_companies(self):
        response = self._get(company_list_view, self.superuser, '/api/v1/superadmin/companies/')
        payload = json.loads(response.content)['data']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload['companies']), 1)
        self.assertEqual(payload['companies'][0]['name'], 'Northstar Labs')

    def test_company_status_filter(self):
        Subscription.objects.create(
            organization=self.organization, created_by=self.company_admin, plan=Subscription.PLAN_STARTER,
            provider=Subscription.PROVIDER_PAYSTACK, status=Subscription.STATUS_ACTIVE, reference='ref-1',
            amount=1000, start_date='2026-01-01',
        )
        response = self._get(company_list_view, self.superuser, '/api/v1/superadmin/companies/', '?status=active')
        payload = json.loads(response.content)['data']
        self.assertEqual(len(payload['companies']), 1)
        self.assertEqual(payload['companies'][0]['bucket'], 'active')

        response = self._get(company_list_view, self.superuser, '/api/v1/superadmin/companies/', '?status=trial')
        payload = json.loads(response.content)['data']
        self.assertEqual(len(payload['companies']), 0)

    def test_suspend_company_writes_audit_log(self):
        request = self.factory.patch(
            f'/api/v1/superadmin/companies/{self.organization.id}/status/',
            data=json.dumps({'status': 'suspended', 'reason': 'Non-payment'}),
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer token',
        )
        with patch('hr_app_backend.employees.views.helpers.get_user_by_token', return_value=self.superuser):
            response = company_status_view(request, org_id=self.organization.id)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)['data']
        self.assertEqual(payload['company']['status'], 'suspended')

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.status, Organization.STATUS_SUSPENDED)
        self.assertEqual(self.organization.audit_logs.count(), 1)

    def test_user_list_role_buckets(self):
        employee = Employee.objects.create(
            organization=self.organization, employee_id='EMP-1', first_name='Ada', last_name='Lovelace',
            email='ada@northstar.test', hire_date='2026-01-01',
        )
        employee_user = get_user_model().objects.create_user(
            username='ada@northstar.test', email='ada@northstar.test', password='pass'
        )
        UserProfile.objects.create(
            user=employee_user, account_type=UserProfile.ACCOUNT_TYPE_COMPANY,
            organization=self.organization, employee=employee, full_name='Ada Lovelace',
        )

        response = self._get(user_list_view, self.superuser, '/api/v1/superadmin/users/', '?role=company_admin')
        payload = json.loads(response.content)['data']
        self.assertEqual([u['email'] for u in payload['users']], [self.company_admin.email])

        response = self._get(user_list_view, self.superuser, '/api/v1/superadmin/users/', '?role=employee')
        payload = json.loads(response.content)['data']
        self.assertEqual([u['email'] for u in payload['users']], [employee_user.email])

    def test_archived_records_only_returns_soft_deleted(self):
        active = Employee.objects.create(
            organization=self.organization, employee_id='EMP-2', first_name='Grace', last_name='Hopper',
            email='grace@northstar.test', hire_date='2026-01-01',
        )
        deleted = Employee.objects.create(
            organization=self.organization, employee_id='EMP-3', first_name='Alan', last_name='Turing',
            email='alan@northstar.test', hire_date='2026-01-01', is_deleted=True,
        )

        response = self._get(archived_records_view, self.superuser, '/api/v1/superadmin/records/archived/')
        payload = json.loads(response.content)['data']

        self.assertEqual([e['id'] for e in payload['employees']], [str(deleted.id)])
        self.assertNotIn(str(active.id), [e['id'] for e in payload['employees']])
