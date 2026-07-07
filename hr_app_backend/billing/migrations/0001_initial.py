from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('authentication', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_date', models.DateField(editable=False)),
                ('plan', models.CharField(choices=[('starter', 'Starter'), ('professional', 'Professional'), ('custom', 'Custom')], max_length=20)),
                ('provider', models.CharField(choices=[('paystack', 'Paystack'), ('flutterwave', 'Flutterwave')], max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('active', 'Active'), ('failed', 'Failed'), ('cancelled', 'Cancelled'), ('expired', 'Expired')], default='pending', max_length=20)),
                ('reference', models.CharField(max_length=64, unique=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(default='USD', max_length=10)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('payment_url', models.URLField(blank=True)),
                ('access_code', models.CharField(blank=True, max_length=128)),
                ('gateway_transaction_id', models.CharField(blank=True, max_length=128)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('provider_response', models.JSONField(blank=True, default=dict)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscriptions', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscriptions', to='authentication.organization')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
