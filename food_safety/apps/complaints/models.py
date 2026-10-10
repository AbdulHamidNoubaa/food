import uuid

from django.conf import settings
from django.db import models


class Complaint(models.Model):
    class Status(models.TextChoices):
        NEW = "NEW", "جديد"
        REVIEWING = "REVIEWING", "قيد المراجعة"
        ASSIGNED = "ASSIGNED", "مُسند"
        UNDER_INVESTIGATION = "UNDER_INVESTIGATION", "قيد التحقيق"
        VERIFIED = "VERIFIED", "موثّق"
        REJECTED = "REJECTED", "مرفوض"
        CLOSED = "CLOSED", "مغلق"

    class Severity(models.TextChoices):
        LOW = "LOW", "منخفض"
        MEDIUM = "MEDIUM", "متوسط"
        HIGH = "HIGH", "مرتفع"
        CRITICAL = "CRITICAL", "حرج"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="complaints"
    )
    product = models.ForeignKey(
        "products.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints"
    )
    scan = models.ForeignKey(
        "scans.ProductScan", on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints"
    )
    store = models.ForeignKey(
        "stores.Store", on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints"
    )
    detected_issue = models.TextField(blank=True)
    safety_result = models.JSONField(default=dict, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.NEW, db_index=True
    )
    severity_score = models.IntegerField(default=0)
    severity_level = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.LOW, db_index=True
    )
    assigned_authority = models.ForeignKey(
        "stores.MunicipalAuthority",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints",
    )
    assigned_inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_complaints",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"بلاغ {str(self.id)[:8]} — {self.status}"


class ComplaintAttachment(models.Model):
    class FileType(models.TextChoices):
        IMAGE = "IMAGE", "صورة"
        DOCUMENT = "DOCUMENT", "مستند"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="complaints/")
    file_type = models.CharField(max_length=20, choices=FileType.choices, default=FileType.IMAGE)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class ComplaintStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name="history")
    old_status = models.CharField(max_length=50, blank=True)
    new_status = models.CharField(max_length=50)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name_plural = "Complaint status histories"
