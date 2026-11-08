import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from hr_app_backend.authentication.models import Organization, UserProfile
from hr_app_backend.employees.models import Employee

from .models import Announcement, PayrollRecord
from .views import announcements_view, payroll_run_view

REQUIRE_USER = 'hr_app_backend.platform.views.require_user'


class AdminOnlyActionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        users = get_user_model().objects
        self.organization = Organization.objects.create(name='Acme', email='hr@example.com', phone='1')
        self.admin = users.create_user(username='admin', email='hr@example.com', password='x')
        UserProfile.objects.create(
            user=self.admin, account_type=UserProfile.ACCOUNT_TYPE_COMPANY, organization=self.organization,
        )
        self.employee = Employee.objects.create(
            organization=self.organization, employee_id='EMP-1', first_name='Ada', last_name='Staff',
            email='ada@example.com', department='Engineering', salary=Decimal('100000'),
        )
        self.staff = users.create_user(username='ada', email='ada@example.com', password='x')
        UserProfile.objects.create(
            user=self.staff, account_type=UserProfile.ACCOUNT_TYPE_INDIVIDUAL,
            organization=self.organization, employee=self.employee,
        )

    def _post(self, view, user, body):
        request = self.factory.post('/', data=json.dumps(body), content_type='application/json')
        with patch(REQUIRE_USER, return_value=user):
            return view(request)

    def test_staff_cannot_post_company_announcements(self):
        response = self._post(announcements_view, self.staff, {'title': 'Hello', 'content': 'Everyone gets a bonus.'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Announcement.objects.exists())

    def test_admin_can_post_announcements(self):
        response = self._post(announcements_view, self.admin, {'title': 'Hello', 'content': 'Office closes at 3pm.'})
        self.assertEqual(response.status_code, 201)

    def test_staff_can_still_read_announcements(self):
        request = self.factory.get('/')
        with patch(REQUIRE_USER, return_value=self.staff):
            self.assertEqual(announcements_view(request).status_code, 200)

    def test_repeated_payroll_run_creates_each_record_once(self):
        for _ in range(2):
            response = self._post(payroll_run_view, self.admin, {'month': '2026-11'})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(PayrollRecord.objects.filter(month='2026-11').count(), 1)
