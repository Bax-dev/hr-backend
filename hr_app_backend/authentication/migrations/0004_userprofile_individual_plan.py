from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('authentication', '0003_userprofile_email_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='individual_plan',
            field=models.CharField(
                blank=True,
                choices=[('free', 'Free'), ('essential_2000', 'Essential'), ('premium', 'Premium')],
                max_length=20,
            ),
        ),
    ]
