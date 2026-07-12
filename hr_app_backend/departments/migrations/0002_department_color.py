from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('departments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='color',
            field=models.CharField(default='#2563eb', max_length=7),
        ),
    ]
