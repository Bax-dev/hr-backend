from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('authentication', '0006_organization_status_organization_suspended_at_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userprofile',
            name='individual_plan',
        ),
    ]
