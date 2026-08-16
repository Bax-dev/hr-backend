from django.db import migrations, models


def backfill_folder_storage_keys(apps, schema_editor):
    Folder = apps.get_model('file_management', 'Folder')
    S3Configuration = apps.get_model('file_management', 'S3Configuration')
    folders = list(Folder.objects.all())
    by_id = {folder.id: folder for folder in folders}
    org_uses_own_bucket = {
        config.organization_id
        for config in S3Configuration.objects.all()
        if config.is_active and config.bucket_name and config.access_key_id
    }

    def prefix_for(folder):
        parts = []
        node = folder
        seen = set()
        while node is not None and node.id not in seen:
            seen.add(node.id)
            parts.append((node.name or '').strip() or str(node.id))
            node = by_id.get(node.parent_id) if node.parent_id else None
        parts.reverse()
        if folder.organization_id in org_uses_own_bucket:
            base = 'files/'
        else:
            base = f'files/{folder.organization_id}/'
        return base + '/'.join(parts) + '/'

    for folder in folders:
        Folder.objects.filter(pk=folder.pk).update(storage_key=prefix_for(folder))


class Migration(migrations.Migration):

    dependencies = [
        ('file_management', '0002_folder_visibility_foldershare'),
    ]

    operations = [
        migrations.AddField(
            model_name='folder',
            name='storage_key',
            field=models.CharField(blank=True, max_length=1024),
        ),
        migrations.RunPython(backfill_folder_storage_keys, migrations.RunPython.noop),
    ]
