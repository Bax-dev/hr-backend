from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('platform', '0005_personal_goal_planning_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='platformrecord',
            name='module',
            field=models.CharField(
                choices=[
                    ('approvals', 'Approvals'),
                    ('communications', 'Communications'),
                    ('analytics', 'Analytics'),
                    ('compliance', 'Compliance'),
                    ('ai-features', 'AI Features'),
                    ('notifications', 'Notifications'),
                    ('integrations', 'Integrations'),
                    ('admin-controls', 'Admin Controls'),
                    ('dashboards', 'Dashboards'),
                    ('inventory', 'Inventory'),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
