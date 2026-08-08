import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from hr_app_backend.authentication.models import Organization, UserProfile

from .models import AuditLog
from .services import record_audit_event
from .views import audit_log_list_view


class AuditLogApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.factory = RequestFactory()
        self.organization = Organization.objects.create(
            name='Northstar Labs', email='admin@northstar.test', phone='12345'
        )
        self.other_organization = Organization.objects.create(
            name='Other Company', email='admin@other.test', phone='67890'
        )
        self.admin = user_model.objects.create_user(
            username='admin', email='admin@northstar.test', password='pass'
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name='Northstar Admin',
            account_type=UserProfile.ACCOUNT_TYPE_COMPANY,
            organization=self.organization,
        )
        self.staff = user_model.objects.create_user(
            username='staff', email='staff@northstar.test', password='pass'
        )
        UserProfile.objects.create(
            user=self.staff,
            full_name='Staff Member',
            account_type=UserProfile.ACCOUNT_TYPE_INDIVIDUAL,
            organization=self.organization,
        )

    def _get(self, user, query=''):
        request = self.factory.get(f'/api/v1/audit-logs/{query}', HTTP_AUTHORIZATION='Bearer token')
        with patch('hr_app_backend.audit_logs.views.get_user_by_token', return_value=user):
            return audit_log_list_view(request)

    def test_list_is_tenant_scoped_and_serialized(self):
        visible = AuditLog.objects.create(
            organization=self.organization,
            actor=self.admin,
            actor_name='Northstar Admin',
            actor_email=self.admin.email,
            action='employee.created',
            category='employees',
            description='Created an employee.',
            resource_type='employee',
            resource_id='EMP-001',
        )
        AuditLog.objects.create(
            organization=self.other_organization,
            action='organization.updated',
            category='settings',
            description='Updated another organization.',
        )

        response = self._get(self.admin)
        payload = json.loads(response.content)['data']

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in payload['logs']], [str(visible.id)])
        self.assertEqual(payload['logs'][0]['actor']['email'], self.admin.email)
        self.assertEqual(payload['logs'][0]['resource']['id'], 'EMP-001')
        self.assertEqual(payload['categories'], ['employees'])

    def test_filters_and_pagination_are_applied(self):
        for index in range(3):
            AuditLog.objects.create(
                organization=self.organization,
                actor_name='Northstar Admin',
                action='auth.login' if index < 2 else 'auth.logout',
                category='authentication',
                description=f'Login event {index}',
                status=AuditLog.STATUS_SUCCESS if index != 1 else AuditLog.STATUS_FAILURE,
            )

        response = self._get(
            self.admin,
            '?search=login&category=authentication&status=success&action=auth.login&page_size=1',
        )
        payload = json.loads(response.content)['data']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload['logs']), 1)
        self.assertEqual(payload['logs'][0]['action'], 'auth.login')
        self.assertEqual(payload['pagination']['total_items'], 1)

    def test_staff_members_cannot_view_logs(self):
        response = self._get(self.staff)
        self.assertEqual(response.status_code, 403)

    def test_invalid_status_is_rejected(self):
        response = self._get(self.admin, '?status=pending')
        self.assertEqual(response.status_code, 400)


class RecordAuditEventTests(TestCase):
    def test_captures_actor_and_request_context(self):
        user_model = get_user_model()
        organization = Organization.objects.create(
            name='Northstar Labs', email='audit@northstar.test', phone='12345'
        )
        user = user_model.objects.create_user(
            username='auditor', email='auditor@northstar.test', password='pass'
        )
        UserProfile.objects.create(
            user=user,
            full_name='Ada Auditor',
            account_type=UserProfile.ACCOUNT_TYPE_COMPANY,
            organization=organization,
        )
        request = RequestFactory().post(
            '/api/v1/employees/',
            HTTP_X_FORWARDED_FOR='203.0.113.7, 10.0.0.1',
            HTTP_USER_AGENT='Audit test agent',
        )
        request.request_id = 'req-123'

        log = record_audit_event(
            organization=organization,
            actor=user,
            request=request,
            action='employee.created',
            category='employees',
            description='Created Ada Employee.',
            resource_type='employee',
            resource_id='EMP-001',
            metadata={'source': 'admin'},
        )

        self.assertEqual(log.actor_name, 'Ada Auditor')
        self.assertEqual(log.ip_address, '203.0.113.7')
        self.assertEqual(log.user_agent, 'Audit test agent')
        self.assertEqual(log.request_id, 'req-123')
        self.assertEqual(log.metadata, {'source': 'admin'})
