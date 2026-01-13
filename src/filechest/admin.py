from django.contrib import admin
from .models import Volume, VolumePermission


class VolumePermissionInline(admin.TabularInline):
    model = VolumePermission
    extra = 1


@admin.register(Volume)
class VolumeAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "verbose_name",
        "path",
        "public_read",
        "is_active",
        "created_at",
    ]
    list_filter = ["public_read", "is_active"]
    search_fields = ["name", "path"]
    inlines = [VolumePermissionInline]


@admin.register(VolumePermission)
class VolumePermissionAdmin(admin.ModelAdmin):
    list_display = ["user", "volume", "role"]
    list_filter = ["role", "volume"]
    search_fields = ["user__username", "volume__name"]
