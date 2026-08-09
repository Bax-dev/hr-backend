from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from hr_app_backend.utils.errors import ExternalServiceError

from .service import ask_assistant


@override_settings(BEDROCK_MODEL_ID='us.amazon.nova-pro-v1:0', BEDROCK_MAX_TOKENS=500)
class AssistantServiceTests(SimpleTestCase):
    def test_uses_converse_and_returns_text(self):
        client = Mock()
        client.converse.return_value = {
            'output': {'message': {'content': [{'text': 'Here is your answer.'}]}},
            'usage': {'inputTokens': 12, 'outputTokens': 5},
        }

        result = ask_assistant(
            messages=[{'role': 'user', 'content': 'Help me draft a review'}],
            page='/workspace/performance',
            user_label='HR Manager',
            client=client,
        )

        self.assertEqual(result['message'], 'Here is your answer.')
        kwargs = client.converse.call_args.kwargs
        self.assertEqual(kwargs['modelId'], 'us.amazon.nova-pro-v1:0')
        self.assertIn('/workspace/performance', kwargs['system'][0]['text'])

    def test_does_not_send_more_than_twelve_messages(self):
        client = Mock()
        client.converse.return_value = {'output': {'message': {'content': [{'text': 'OK'}]}}}
        messages = [{'role': 'user', 'content': str(index)} for index in range(15)]

        ask_assistant(messages=messages, page='/', user_label='User', client=client)

        self.assertEqual(len(client.converse.call_args.kwargs['messages']), 12)

    def test_service_errors_are_safe(self):
        client = Mock()
        client.converse.side_effect = __import__('botocore').exceptions.BotoCoreError()

        with self.assertRaises(ExternalServiceError):
            ask_assistant(
                messages=[{'role': 'user', 'content': 'Hello'}],
                page='/', user_label='User', client=client,
            )
