from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_update_subscription_plans'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='reminder_5d_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subscription',
            name='reminder_2d_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subscription',
            name='reminder_1d_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
