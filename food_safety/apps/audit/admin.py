from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "entity_type", "entity_id", "created_at")
    list_filter = ("action",)
    readonly_fields = (
        "user",
        "action",
        "entity_type",
        "entity_id",
        "old_value",
        "new_value",
        "ip_address",
        "device_info",
        "created_at",
    )
