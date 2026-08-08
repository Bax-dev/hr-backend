import django.db.models.deletion
import datetime
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [('authentication', '0005_userprofile_personal_details'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_date', models.DateField(default=datetime.date.today, editable=False)), ('actor_name', models.CharField(blank=True, max_length=255)),
                ('actor_email', models.EmailField(blank=True, max_length=254)), ('action', models.CharField(max_length=120)),
                ('category', models.CharField(db_index=True, max_length=64)), ('resource_type', models.CharField(blank=True, max_length=100)),
                ('resource_id', models.CharField(blank=True, max_length=100)), ('description', models.CharField(max_length=500)),
                ('status', models.CharField(choices=[('success', 'Success'), ('failure', 'Failure')], db_index=True, default='success', max_length=16)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)), ('user_agent', models.TextField(blank=True)),
                ('request_id', models.CharField(blank=True, max_length=100)), ('metadata', models.JSONField(blank=True, default=dict)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='authentication.organization')),
            ], options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(model_name='auditlog', index=models.Index(fields=['organization', '-created_at'], name='audit_org_created_idx')),
        migrations.AddIndex(model_name='auditlog', index=models.Index(fields=['organization', 'action'], name='audit_org_action_idx')),
    ]
