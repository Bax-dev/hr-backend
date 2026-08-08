from django.db import migrations


REMOVED_FIELDS = {'assetType', 'assettype', 'images', 'imageUrl', 'imageURL', 'image_url'}


def remove_inventory_fields(apps, schema_editor):
    PlatformRecord = apps.get_model('platform', 'PlatformRecord')
    for record in PlatformRecord.objects.filter(module='inventory').iterator():
        payload = dict(record.payload)
        cleaned = {key: value for key, value in payload.items() if key not in REMOVED_FIELDS}
        if cleaned != payload:
            record.payload = cleaned
            record.save(update_fields=['payload'])


class Migration(migrations.Migration):
    dependencies = [('platform', '0007_bulknotification_notificationemailjob')]

    operations = [migrations.RunPython(remove_inventory_fields, migrations.RunPython.noop)]
