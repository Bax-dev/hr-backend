from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('platform', '0008_remove_inventory_asset_type_and_images'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PersonalGoal',
        ),
    ]
