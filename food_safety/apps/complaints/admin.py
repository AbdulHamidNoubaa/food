from django.contrib import admin

from apps.complaints.models import Complaint, ComplaintAttachment, ComplaintStatusHistory


class AttachmentInline(admin.TabularInline):
    model = ComplaintAttachment
    extra = 0


class HistoryInline(admin.TabularInline):
    model = ComplaintStatusHistory
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_by", "notes", "changed_at")


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "severity_level", "product", "store", "created_at")
    list_filter = ("status", "severity_level")
    inlines = [AttachmentInline, HistoryInline]
