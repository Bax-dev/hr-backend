from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('talent', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobposting',
            name='application_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
