from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0005_employee_deleted_at_employee_is_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='work_mode',
            field=models.CharField(
                choices=[('onsite', 'On-site'), ('remote', 'Remote')],
                default='onsite',
                max_length=20,
            ),
        ),
    ]
