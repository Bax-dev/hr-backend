from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('authentication', '0004_userprofile_individual_plan')]

    operations = [
        migrations.AddField(model_name='userprofile', name='gender', field=models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('prefer_not_to_say', 'Prefer not to say')], max_length=32)),
        migrations.AddField(model_name='userprofile', name='country', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='userprofile', name='date_of_birth', field=models.DateField(blank=True, null=True)),
    ]
