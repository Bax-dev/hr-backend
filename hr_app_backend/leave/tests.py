from django.contrib.auth import get_user_model
from django.test import TestCase

from hr_app_backend.authentication.models import Organization, UserProfile
from hr_app_backend.employees.models import Employee
from hr_app_backend.utils.errors import NotFoundError, PermissionDeniedError

from .models import LeaveRequest
from .services import create_leave, delete_leave, get_leave, list_leaves, update_leave


class LeaveRoleWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.organization = Organization.objects.create(
            name='Workiva Test', email='hr@example.com', phone='12345'
        )
        self.admin = user_model.objects.create_user(username='admin', email='hr@example.com', password='pass')
        UserProfile.objects.create(
            user=self.admin,
            account_type=UserProfile.ACCOUNT_TYPE_COMPANY,
            organization=self.organization,
        )
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_id='EMP-001',
            first_name='Ada',
            last_name='Staff',
            email='ada@example.com',
            department='Engineering',
        )
        self.other_employee = Employee.objects.create(
            organization=self.organization,
            employee_id='EMP-002',
            first_name='Tomi',
            last_name='Staff',
            email='tomi@example.com',
        )
        self.staff = user_model.objects.create_user(username='ada', email='ada@example.com', password='pass')
        UserProfile.objects.create(
            user=self.staff,
            account_type=UserProfile.ACCOUNT_TYPE_INDIVIDUAL,
            organization=self.organization,
            employee=self.employee,
        )

    def _payload(self, employee=None):
        return {
            'employee_id': str((employee or self.employee).id),
            'leave_type': 'Annual',
            'start_date': '2026-08-10',
            'end_date': '2026-08-12',
            'reason': 'Family commitment',
        }

    def test_staff_submission_is_visible_to_staff_and_admin(self):
        leave = create_leave(self.staff, self._payload(self.other_employee))
        self.assertEqual(leave.employee, self.employee)
        self.assertEqual(leave.status, LeaveRequest.STATUS_PENDING)
        self.assertEqual(list(list_leaves(self.staff)), [leave])
        self.assertIn(leave, list(list_leaves(self.admin)))

    def test_staff_cannot_see_or_review_another_employee_request(self):
        other_leave = create_leave(self.admin, self._payload(self.other_employee))
        with self.assertRaises(NotFoundError):
            get_leave(self.staff, other_leave.id)
        with self.assertRaises(PermissionDeniedError):
            update_leave(self.staff, other_leave.id, {'status': 'approved'})

    def test_admin_can_approve_and_staff_cannot_cancel_processed_leave(self):
        leave = create_leave(self.staff, self._payload())
        approved = update_leave(self.admin, leave.id, {'status': 'approved'})
        self.assertEqual(approved.status, LeaveRequest.STATUS_APPROVED)
        with self.assertRaises(PermissionDeniedError):
            delete_leave(self.staff, leave.id)

    def test_admin_can_optionally_explain_a_rejection(self):
        leave = create_leave(self.staff, self._payload())
        rejected = update_leave(
            self.admin,
            leave.id,
            {'status': 'rejected', 'rejection_reason': 'Insufficient coverage.'},
        )
        self.assertEqual(rejected.status, LeaveRequest.STATUS_REJECTED)
        self.assertEqual(rejected.rejection_reason, 'Insufficient coverage.')

        another_leave = create_leave(self.staff, self._payload())
        rejected_without_reason = update_leave(self.admin, another_leave.id, {'status': 'rejected'})
        self.assertEqual(rejected_without_reason.rejection_reason, '')

    def test_staff_can_cancel_own_pending_request(self):
        leave = create_leave(self.staff, self._payload())
        delete_leave(self.staff, leave.id)
        self.assertFalse(LeaveRequest.objects.filter(pk=leave.id).exists())
