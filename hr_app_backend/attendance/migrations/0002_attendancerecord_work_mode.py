from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancerecord',
            name='work_mode',
            field=models.CharField(
                choices=[('onsite', 'On-site'), ('remote', 'Remote')],
                default='onsite',
                max_length=20,
            ),
        ),
    ]
