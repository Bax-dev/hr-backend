from django.contrib import admin

from .models import Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager', 'organization', 'created_at')
    search_fields = ('name', 'manager', 'organization__name')
