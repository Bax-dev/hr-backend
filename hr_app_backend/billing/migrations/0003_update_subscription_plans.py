from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_alter_subscription_created_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='plan',
            field=models.CharField(
                choices=[
                    ('free_trial', 'Free Trial'),
                    ('starter', 'Starter'),
                    ('growth', 'Growth'),
                    ('enterprise', 'Enterprise'),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='currency',
            field=models.CharField(default='NGN', max_length=10),
        ),
    ]
