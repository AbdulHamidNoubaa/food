import uuid

from django.conf import settings
from django.db import models


class ProductScan(models.Model):
    class Method(models.TextChoices):
        BARCODE = "BARCODE", "باركود"
        SEARCH = "SEARCH", "بحث"
        IMAGE = "IMAGE", "صورة"
        TEXT = "TEXT", "نص يدوي"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scans",
    )
    product = models.ForeignKey(
        "products.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="scans"
    )
    scan_method = models.CharField(max_length=10, choices=Method.choices)
    store = models.ForeignKey(
        "stores.Store", on_delete=models.SET_NULL, null=True, blank=True, related_name="scans"
    )
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_consent = models.BooleanField(default=False)
    query_text = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ScanImage(models.Model):
    class ImageType(models.TextChoices):
        PACKAGE = "PACKAGE", "عبوة"
        LABEL = "LABEL", "ملصق"
        INGREDIENTS = "INGREDIENTS", "مكونات"
        BARCODE = "BARCODE", "باركود"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scan = models.ForeignKey(ProductScan, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="scans/")
    image_type = models.CharField(
        max_length=20, choices=ImageType.choices, default=ImageType.INGREDIENTS
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)


class OCRResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scan_image = models.OneToOneField(
        ScanImage, on_delete=models.CASCADE, related_name="ocr_result"
    )
    raw_text = models.TextField(blank=True)
    extracted_ingredients = models.JSONField(default=list)  # [{text, confidence, needs_verification}]
    overall_confidence = models.FloatField(default=0.0)
    processing_time_ms = models.PositiveIntegerField(default=0)
    engine_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SafetyAssessment(models.Model):
    class ProductStatus(models.TextChoices):
        SAFE = "SAFE", "آمن"
        WARNING = "WARNING", "تحذير"
        UNSAFE = "UNSAFE", "غير آمن"
        UNKNOWN = "UNKNOWN", "غير معروف"
        PENDING = "PENDING", "قيد الانتظار"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scan = models.OneToOneField(ProductScan, on_delete=models.CASCADE, related_name="assessment")
    product_status = models.CharField(
        max_length=20, choices=ProductStatus.choices, default=ProductStatus.PENDING
    )
    ingredient_results = models.JSONField(default=list)
    summary_reason = models.TextField(blank=True)
    computed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_status} @ {self.computed_at:%Y-%m-%d %H:%M}"
