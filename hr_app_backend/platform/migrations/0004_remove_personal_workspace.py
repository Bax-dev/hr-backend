from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('platform', '0003_personal_workspace_personal_goal')]

    operations = [
        migrations.DeleteModel(name='PersonalWorkspace'),
    ]
