from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import datetime
import uuid


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('platform', '0002_notification'),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonalWorkspace',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_date', models.DateField(default=datetime.date.today, editable=False)),
                ('private_notes', models.TextField(blank=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='personal_workspace', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='PersonalGoal',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_date', models.DateField(default=datetime.date.today, editable=False)),
                ('title', models.CharField(max_length=255)),
                ('completed', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='personal_goals', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['completed', '-created_at']},
        ),
    ]
