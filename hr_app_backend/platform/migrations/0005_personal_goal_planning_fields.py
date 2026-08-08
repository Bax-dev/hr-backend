from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('platform', '0004_remove_personal_workspace')]

    operations = [
        migrations.AddField(model_name='personalgoal', name='priority', field=models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium', max_length=10)),
        migrations.AddField(model_name='personalgoal', name='category', field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name='personalgoal', name='due_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='personalgoal', name='completed_at', field=models.DateTimeField(blank=True, null=True)),
    ]
