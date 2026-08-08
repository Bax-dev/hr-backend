import time

from django.core.management.base import BaseCommand

from hr_app_backend.platform.bulk_notifications import process_email_queue


class Command(BaseCommand):
    help = 'Process queued employee notification emails.'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=100)
        parser.add_argument('--once', action='store_true', help='Process one batch and exit.')
        parser.add_argument('--poll-seconds', type=float, default=2)

    def handle(self, *args, **options):
        while True:
            count = process_email_queue(batch_size=max(1, options['batch_size']))
            if options['once']:
                self.stdout.write(self.style.SUCCESS(f'Processed {count} queued email(s).'))
                return
            if count == 0:
                time.sleep(max(0.1, options['poll_seconds']))
