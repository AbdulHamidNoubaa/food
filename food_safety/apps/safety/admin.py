from django.contrib import admin

from apps.safety.models import SafetyRule


@admin.register(SafetyRule)
class SafetyRuleAdmin(admin.ModelAdmin):
    list_display = ("rule_name", "resulting_status", "weight", "is_active")
