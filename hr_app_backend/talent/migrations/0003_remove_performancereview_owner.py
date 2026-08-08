from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('talent', '0002_jobposting_application_email'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='performancereview',
            name='owner',
        ),
    ]
