from django.contrib import admin

from .models import FileAsset, FileShare, Folder, FolderShare, S3Configuration


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'parent', 'visibility', 'created_by', 'created_at')
    search_fields = ('name', 'organization__name')
    list_filter = ('visibility',)


@admin.register(FolderShare)
class FolderShareAdmin(admin.ModelAdmin):
    list_display = ('folder', 'employee', 'department', 'access_level', 'created_at')


@admin.register(FileAsset)
class FileAssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'visibility', 'size_bytes', 'is_deleted', 'created_at')
    search_fields = ('name', 'organization__name', 'storage_key')
    list_filter = ('visibility', 'is_deleted')


@admin.register(FileShare)
class FileShareAdmin(admin.ModelAdmin):
    list_display = ('file', 'employee', 'department', 'access_level', 'created_at')


@admin.register(S3Configuration)
class S3ConfigurationAdmin(admin.ModelAdmin):
    list_display = ('organization', 'bucket_name', 'region', 'is_active')
