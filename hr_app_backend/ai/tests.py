import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from hr_app_backend.attendance.models import AttendanceRecord
from hr_app_backend.authentication.models import Organization, UserProfile
from hr_app_backend.employees.models import Employee
from hr_app_backend.leave.models import LeaveRequest
from hr_app_backend.platform.models import Notification
from hr_app_backend.talent.models import PerformanceReview
from hr_app_backend.utils import today_local
from hr_app_backend.utils.errors import ExternalServiceError, PermissionDeniedError

from .intelligence import (
    query_absences,
    query_flight_risk,
    query_salary_reviews,
    simulate_payroll_increment,
)
from .service import ask_assistant
from .tools import execute_tool
from .workflows import create_review_cycle, notify_employees


def _user_stub(*, admin=True):
    return SimpleNamespace(
        email='hr@example.com',
        get_full_name=lambda: 'HR Manager',
        profile=SimpleNamespace(
            full_name='HR Manager',
            account_type='company' if admin else 'individual',
            organization=None,
            employee=None,
        ),
    )


@override_settings(BEDROCK_MODEL_ID='us.amazon.nova-pro-v1:0', BEDROCK_MAX_TOKENS=500)
class AssistantServiceTests(SimpleTestCase):
    def test_uses_converse_and_returns_text(self):
        client = Mock()
        client.converse.return_value = {
            'output': {'message': {'content': [{'text': 'Here is your answer.'}]}},
            'stopReason': 'end_turn',
            'usage': {'inputTokens': 12, 'outputTokens': 5},
        }

        result = ask_assistant(
            messages=[{'role': 'user', 'content': 'Help me draft a review'}],
            page='/workspace/performance',
            user=_user_stub(),
            client=client,
        )

        self.assertEqual(result['message'], 'Here is your answer.')
        self.assertEqual(result['actions'], [])
        kwargs = client.converse.call_args.kwargs
        self.assertEqual(kwargs['modelId'], 'us.amazon.nova-pro-v1:0')
        self.assertIn('/workspace/performance', kwargs['system'][0]['text'])
        self.assertIn('tools', kwargs['toolConfig'])

    def test_strips_thinking_tags_from_replies(self):
        client = Mock()
        client.converse.return_value = {
            'output': {
                'message': {
                    'content': [{
                        'text': (
                            '<thinking> The tool result indicates that there are no employees '
                            'whose performance has dropped over the last 3 months. '
                            'I will inform the user of this finding. </thinking>\n'
                            'Nobody’s performance has dropped over the last 3 months.'
                        )
                    }]
                }
            },
            'stopReason': 'end_turn',
        }

        result = ask_assistant(
            messages=[{'role': 'user', 'content': 'Any performance drops?'}],
            page='/',
            user=_user_stub(),
            client=client,
        )

        self.assertEqual(result['message'], 'Nobody’s performance has dropped over the last 3 months.')
        self.assertNotIn('thinking', result['message'].lower())

    def test_does_not_send_more_than_twelve_messages(self):
        client = Mock()
        client.converse.return_value = {
            'output': {'message': {'content': [{'text': 'OK'}]}},
            'stopReason': 'end_turn',
        }
        messages = [{'role': 'user', 'content': str(index)} for index in range(15)]

        ask_assistant(messages=messages, page='/', user=_user_stub(), client=client)

        self.assertEqual(len(client.converse.call_args.kwargs['messages']), 12)

    def test_runs_tools_then_answers(self):
        client = Mock()
        client.converse.side_effect = [
            {
                'output': {
                    'message': {
                        'role': 'assistant',
                        'content': [{
                            'toolUse': {
                                'toolUseId': 'tool-1',
                                'name': 'query_absences',
                                'input': {'min_count': 3},
                            }
                        }],
                    }
                },
                'stopReason': 'tool_use',
            },
            {
                'output': {'message': {'content': [{'text': 'Ada was absent 4 times.'}]}},
                'stopReason': 'end_turn',
                'usage': {'inputTokens': 20, 'outputTokens': 8},
            },
        ]

        with patch('hr_app_backend.ai.service.execute_tool', return_value=({'count': 1}, None)):
            result = ask_assistant(
                messages=[{'role': 'user', 'content': 'Who has been absent more than 3 times?'}],
                page='/',
                user=_user_stub(),
                client=client,
            )

        self.assertEqual(result['message'], 'Ada was absent 4 times.')
        self.assertEqual(client.converse.call_count, 2)
        follow_up = client.converse.call_args_list[1].kwargs['messages'][-1]
        self.assertEqual(follow_up['content'][0]['toolResult']['toolUseId'], 'tool-1')

    def test_collects_actions_from_tools(self):
        client = Mock()
        client.converse.side_effect = [
            {
                'output': {
                    'message': {
                        'content': [{
                            'toolUse': {
                                'toolUseId': 'tool-2',
                                'name': 'create_review_cycle',
                                'input': {'department': 'Engineering', 'start_date': '2026-09-01'},
                            }
                        }],
                    }
                },
                'stopReason': 'tool_use',
            },
            {
                'output': {'message': {'content': [{'text': 'Cycle created.'}]}},
                'stopReason': 'end_turn',
            },
        ]
        action = {'type': 'create_review_cycle', 'label': 'Created 2 reviews', 'details': 'Engineering'}

        with patch('hr_app_backend.ai.service.execute_tool', return_value=({'reviews_created': 2}, action)):
            result = ask_assistant(
                messages=[{'role': 'user', 'content': 'Create a review cycle for engineering starting September 1'}],
                page='/',
                user=_user_stub(),
                client=client,
            )

        self.assertEqual(result['actions'], [action])

    def test_service_errors_are_safe(self):
        client = Mock()
        client.converse.side_effect = __import__('botocore').exceptions.BotoCoreError()

        with self.assertRaises(ExternalServiceError):
            ask_assistant(
                messages=[{'role': 'user', 'content': 'Hello'}],
                page='/',
                user=_user_stub(),
                client=client,
            )


class CopilotIntelligenceTests(TestCase):
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
        self.ada = Employee.objects.create(
            organization=self.organization,
            employee_id='EMP-001',
            first_name='Ada',
            last_name='Staff',
            email='ada@example.com',
            department='Engineering',
            salary=Decimal('500000'),
            hire_date=today_local() - datetime.timedelta(days=365),
        )
        self.tomi = Employee.objects.create(
            organization=self.organization,
            employee_id='EMP-002',
            first_name='Tomi',
            last_name='Staff',
            email='tomi@example.com',
            department='Sales',
            salary=Decimal('300000'),
            hire_date=datetime.date(2024, 1, 15),
        )
        self.staff = user_model.objects.create_user(username='ada', email='ada@example.com', password='pass')
        UserProfile.objects.create(
            user=self.staff,
            account_type=UserProfile.ACCOUNT_TYPE_INDIVIDUAL,
            organization=self.organization,
            employee=self.ada,
        )
        today = today_local()
        self.current_month = today.strftime('%Y-%m')
        for offset in (2, 4, 6, 8):
            AttendanceRecord.objects.create(
                organization=self.organization,
                employee=self.ada,
                date=today.replace(day=1) + datetime.timedelta(days=offset),
                check_in=datetime.time(9, 0),
                status=AttendanceRecord.STATUS_ABSENT,
            )

    def test_absences_over_threshold(self):
        result = query_absences(self.admin, min_count=3, month=self.current_month)
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['employees'][0]['name'], 'Ada Staff')
        self.assertEqual(result['employees'][0]['absent_count'], 4)

    def test_staff_only_sees_own_absences(self):
        result = query_absences(self.staff, min_count=3, month=self.current_month)
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['employees'][0]['name'], 'Ada Staff')

    def test_staff_cannot_view_flight_risk(self):
        with self.assertRaises(PermissionDeniedError):
            query_flight_risk(self.staff)

    def test_salary_review_uses_hire_anniversary(self):
        result = query_salary_reviews(self.admin, within_days=45)
        names = [item['name'] for item in result['employees']]
        self.assertIn('Ada Staff', names)

    def test_payroll_increment_preview(self):
        result = simulate_payroll_increment(self.admin, percent=10)
        self.assertEqual(result['current_monthly_payroll'], 800000.0)
        self.assertEqual(result['increase'], 80000.0)
        self.assertEqual(result['annual_increase'], 960000.0)

    def test_create_review_cycle_assigns_and_notifies(self):
        result = create_review_cycle(
            self.admin,
            department='Engineering',
            start_date='2026-09-01',
            cycle_name='Engineering H2',
        )
        self.assertEqual(result['reviews_created'], 1)
        self.assertEqual(result['employees_selected'], 1)
        review = PerformanceReview.objects.get(review_cycle='Engineering H2')
        self.assertEqual(review.employee_name, 'Ada Staff')
        self.assertIn('Due: 2026-10-01', review.notes)
        self.assertTrue(
            Notification.objects.filter(recipient=self.ada, title__icontains='Engineering H2').exists()
        )

    def test_notify_employees_by_department(self):
        result = notify_employees(
            self.admin,
            title='Review kickoff',
            body='Please complete your goals before Friday.',
            department='Engineering',
        )
        self.assertEqual(result['notified'], 1)
        self.assertEqual(Notification.objects.filter(title='Review kickoff').count(), 1)

    def test_staff_cannot_create_review_cycle(self):
        with self.assertRaises(PermissionDeniedError):
            create_review_cycle(self.staff, department='Engineering', start_date='2026-09-01')

    def test_execute_tool_returns_permission_error_payload(self):
        result, action = execute_tool('query_flight_risk', {}, self.staff)
        self.assertIn('error', result)
        self.assertIsNone(action)

    def test_flight_risk_includes_high_absence_employee(self):
        LeaveRequest.objects.create(
            organization=self.organization,
            employee=self.ada,
            leave_type=LeaveRequest.TYPE_ANNUAL,
            start_date=datetime.date(2026, 7, 1),
            end_date=datetime.date(2026, 7, 3),
            days=3,
            reason='Vacation',
            status=LeaveRequest.STATUS_REJECTED,
        )
        result = query_flight_risk(self.admin)
        names = [item['name'] for item in result['employees']]
        self.assertIn('Ada Staff', names)
