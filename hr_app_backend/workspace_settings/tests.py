from django.contrib.auth import get_user_model
from django.test import TestCase

from hr_app_backend.authentication.models import Organization, UserProfile
from hr_app_backend.authentication.serializers.user import serialize_user
from hr_app_backend.workspace_settings.models import WorkspaceSettings
from hr_app_backend.workspace_settings.services import is_copilot_enabled, update_company_profile


class CopilotSettingsTests(TestCase):
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

    def test_copilot_defaults_to_enabled(self):
        self.assertTrue(is_copilot_enabled(self.organization))
        self.assertTrue(serialize_user(self.admin)['copilot_enabled'])

    def test_admin_can_disable_copilot(self):
        organization, settings = update_company_profile(self.admin, {'copilot_enabled': False})
        self.assertFalse(settings.copilot_enabled)
        self.assertFalse(is_copilot_enabled(organization))
        self.assertFalse(serialize_user(self.admin)['copilot_enabled'])

    def test_admin_can_enable_copilot_again(self):
        WorkspaceSettings.objects.create(organization=self.organization, copilot_enabled=False)
        _, settings = update_company_profile(self.admin, {'copilot_enabled': True})
        self.assertTrue(settings.copilot_enabled)
        self.assertTrue(is_copilot_enabled(self.organization))
