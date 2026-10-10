import re
import uuid

from django.db import models


def normalize_alias(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)  # Arabic diacritics
    text = re.sub(r"\s+", " ", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه")
    return text


class Ingredient(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = "LOW", "منخفض"
        MEDIUM = "MEDIUM", "متوسط"
        HIGH = "HIGH", "مرتفع"

    class SafetyStatus(models.TextChoices):
        APPROVED = "APPROVED", "معتمد"
        RESTRICTED = "RESTRICTED", "مقيد"
        PROHIBITED = "PROHIBITED", "محظور"
        UNDER_REVIEW = "UNDER_REVIEW", "قيد المراجعة"
        INACTIVE = "INACTIVE", "غير نشط"

    class DataOrigin(models.TextChoices):
        LOCAL = "LOCAL", "بيانات محلية"
        REFERENCE = "REFERENCE", "مرتبط بمرجع معياري"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_ar = models.CharField("اسم المادة", max_length=200, db_index=True)
    name_en = models.CharField("الاسم بالإنجليزية", max_length=200, db_index=True)
    scientific_name = models.CharField(max_length=200, blank=True)
    e_number = models.CharField("رقم E / INS", max_length=20, blank=True, null=True, db_index=True)
    cas_number = models.CharField("CAS Number", max_length=40, blank=True, null=True, db_index=True)
    category = models.CharField("نوع المادة", max_length=100, blank=True)
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices, default=RiskLevel.HIGH)
    safety_status = models.CharField(
        "حالة المادة",
        max_length=20,
        choices=SafetyStatus.choices,
        default=SafetyStatus.PROHIBITED,
    )
    description = models.TextField(blank=True)
    reason = models.TextField("سبب الحظر", blank=True)
    notes = models.TextField("ملاحظات", blank=True)
    regulatory_status = models.CharField(max_length=200, blank=True)
    source = models.CharField("مصدر / مرجع الحظر", max_length=255, blank=True)
    reference_url = models.URLField(blank=True)
    image = models.ImageField("صورة المادة", upload_to="ingredients/", blank=True, null=True)
    data_origin = models.CharField(
        max_length=20,
        choices=DataOrigin.choices,
        default=DataOrigin.LOCAL,
        db_index=True,
    )
    reference_additive = models.ForeignKey(
        "reference.ReferenceAdditive",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="local_ingredients",
    )
    last_updated = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingredients_created",
    )
    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingredients_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["e_number", "name_en"]

    def __str__(self):
        label = self.e_number or ""
        return f"{label} {self.name_ar}".strip()

    def save(self, *args, **kwargs):
        if self.e_number:
            raw = self.e_number.strip().upper().replace(" ", "")
            if raw.startswith("INS"):
                self.e_number = self.e_number.strip().upper()
            else:
                raw = raw.replace("E-", "E")
                if not raw.startswith("E") and raw and raw[0].isdigit():
                    raw = f"E{raw}"
                self.e_number = raw
        super().save(*args, **kwargs)


class IngredientAlias(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="aliases")
    alias = models.CharField(max_length=200)
    language = models.CharField(max_length=2, choices=[("ar", "العربية"), ("en", "English")])
    alias_normalized = models.CharField(max_length=200, db_index=True)

    class Meta:
        verbose_name_plural = "Ingredient aliases"
        unique_together = [("ingredient", "alias", "language")]

    def save(self, *args, **kwargs):
        self.alias_normalized = normalize_alias(self.alias)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.alias


class IngredientSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="sources")
    source_name = models.CharField(max_length=255)
    reference_url = models.URLField(blank=True)
    document_reference = models.CharField(max_length=255, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.source_name


class IngredientClassification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.CASCADE, related_name="classification_history"
    )
    classification = models.CharField(max_length=100)
    classified_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    classified_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)


class UnmatchedQuery(models.Model):
    """Queries that failed matching — for specialist review."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query_text = models.CharField(max_length=255)
    query_normalized = models.CharField(max_length=255, db_index=True)
    hit_count = models.PositiveIntegerField(default=1)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
