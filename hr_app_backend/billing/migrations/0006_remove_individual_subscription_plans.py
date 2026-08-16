from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('billing', '0005_individual_subscription_plans'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='plan',
            field=models.CharField(
                choices=[
                    ('free_trial', 'Free'),
                    ('starter', 'Essential'),
                    ('growth', 'Premium'),
                    ('enterprise', 'Enterprise'),
                ],
                max_length=20,
            ),
        ),
    ]
