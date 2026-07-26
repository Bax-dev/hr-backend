from pathlib import Path

from django.core.management.base import BaseCommand

from hr_app_backend.api.schema import default_output_path, write_openapi_spec


class Command(BaseCommand):
    help = "Build the OpenAPI document consumed by the Swagger UI."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=str(default_output_path()),
            help="Destination file for the generated OpenAPI YAML.",
        )

    def handle(self, *args, **options):
        output = Path(options["output"]).expanduser().resolve()
        write_openapi_spec(output)
        self.stdout.write(self.style.SUCCESS(f"OpenAPI spec written to {output}"))
