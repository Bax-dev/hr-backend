from django.contrib import admin

from .models import Organization, UserProfile


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'size', 'industry', 'status', 'created_at')
    search_fields = ('name', 'email', 'phone')
    list_filter = ('status',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'account_type', 'phone', 'organization', 'created_at')
    search_fields = ('user__email', 'full_name', 'phone', 'invite_code')
    list_filter = ('account_type',)
