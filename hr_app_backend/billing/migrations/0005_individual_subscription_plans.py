from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('billing', '0004_subscription_expiry_reminders'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='subscriptions',
                to='authentication.organization',
            ),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='plan',
            field=models.CharField(
                choices=[
                    ('free_trial', 'Free Trial'),
                    ('starter', 'Starter'),
                    ('growth', 'Growth'),
                    ('enterprise', 'Enterprise'),
                    ('essential_2000', 'Individual Essential'),
                    ('premium', 'Individual Premium'),
                ],
                max_length=20,
            ),
        ),
    ]
