"""
Standard Food Additives Reference Database + Local Regulatory Overrides.

Design goals:
- Reference data (Codex / JECFA / …) is updatable independently.
- Local Libya classifications never get wiped by a reference sync.
- Codex Permitted ≠ Libya Permitted (jurisdiction-aware status).
- SQLite now; schema is PostgreSQL-ready (UUIDs, explicit FKs, no vendor locks).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.ingredients.models import normalize_alias


class RegulatoryStatus(models.TextChoices):
    PERMITTED = "PERMITTED", "مسموح"
    RESTRICTED = "RESTRICTED", "مقيد"
    PROHIBITED = "PROHIBITED", "محظور"
    UNKNOWN = "UNKNOWN", "غير معروف"
    UNDER_REVIEW = "UNDER_REVIEW", "قيد المراجعة"


class ReferenceSource(models.Model):
    """Codex GSFA, JECFA, Libyan regulation, or future sources."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    name_en = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    website_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.name_ar or self.name_en or self.code


class ReferenceAdditive(models.Model):
    """Canonical additive identity from a standard database (Reference Data)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_ar = models.CharField(max_length=255, blank=True, db_index=True)
    name_en = models.CharField(max_length=255, db_index=True)
    scientific_name = models.CharField(max_length=255, blank=True)
    e_number = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    ins_number = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    cas_number = models.CharField(max_length=40, blank=True, null=True, db_index=True)
    functional_class = models.CharField(max_length=150, blank=True)
    uses = models.TextField(blank=True)
    # Primary catalog source of this reference row (usually Codex or JECFA import)
    primary_source = models.ForeignKey(
        ReferenceSource,
        on_delete=models.PROTECT,
        related_name="additives",
        null=True,
        blank=True,
    )
    external_id = models.CharField(max_length=100, blank=True, db_index=True)
    reference_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["e_number", "ins_number", "name_en"]
        indexes = [
            models.Index(fields=["name_en"]),
            models.Index(fields=["e_number", "ins_number"]),
        ]

    def __str__(self):
        code = self.e_number or self.ins_number or ""
        return f"{code} {self.name_en}".strip()

    def save(self, *args, **kwargs):
        if self.e_number:
            raw = self.e_number.strip().upper().replace(" ", "").replace("E-", "E")
            if raw and not raw.startswith("E") and raw[0].isdigit():
                raw = f"E{raw}"
            self.e_number = raw or None
        if self.ins_number:
            self.ins_number = self.ins_number.strip().upper().replace("INS", "").strip() or None
            if self.ins_number and not self.ins_number.upper().startswith("INS"):
                # store bare number; display can prefix INS
                self.ins_number = self.ins_number.replace(" ", "")
        if self.cas_number:
            self.cas_number = self.cas_number.strip()
        super().save(*args, **kwargs)


class ReferenceSynonym(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    additive = models.ForeignKey(
        ReferenceAdditive, on_delete=models.CASCADE, related_name="synonyms"
    )
    synonym = models.CharField(max_length=255)
    language = models.CharField(max_length=8, default="en")
    synonym_normalized = models.CharField(max_length=255, db_index=True)

    class Meta:
        unique_together = [("additive", "synonym", "language")]

    def save(self, *args, **kwargs):
        self.synonym_normalized = normalize_alias(self.synonym)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.synonym


class ReferenceStatusRecord(models.Model):
    """
    Status tied to Source + Jurisdiction + Effective Date.
    Example: Codex/GLOBAL/PERMITTED vs Libya/LY/PROHIBITED for same additive.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    additive = models.ForeignKey(
        ReferenceAdditive, on_delete=models.CASCADE, related_name="status_records"
    )
    source = models.ForeignKey(
        ReferenceSource, on_delete=models.PROTECT, related_name="status_records"
    )
    jurisdiction = models.CharField(
        max_length=16,
        default="GLOBAL",
        db_index=True,
        help_text="LY, GLOBAL, EU, …",
    )
    status = models.CharField(
        max_length=20, choices=RegulatoryStatus.choices, db_index=True
    )
    usage_conditions = models.TextField(blank=True)
    max_level = models.CharField(max_length=120, blank=True)
    adi_info = models.CharField(max_length=255, blank=True)
    reason = models.TextField(blank=True)
    document_reference = models.CharField(max_length=255, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_date", "-updated_at"]
        indexes = [
            models.Index(fields=["jurisdiction", "status", "is_active"]),
        ]

    def __str__(self):
        return f"{self.additive} [{self.jurisdiction}/{self.source.code}]={self.status}"


class LocalRegulatoryOverride(models.Model):
    """
    Local classification linked to a reference additive (no duplicate identity).
    Used when Libya (or another local authority) differs from Codex/JECFA.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_additive = models.ForeignKey(
        ReferenceAdditive,
        on_delete=models.CASCADE,
        related_name="local_overrides",
    )
    jurisdiction = models.CharField(max_length=16, default="LY", db_index=True)
    status = models.CharField(max_length=20, choices=RegulatoryStatus.choices)
    reason = models.TextField(blank=True)
    regulatory_source = models.CharField(max_length=255, blank=True)
    reference_number = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    image = models.ImageField(upload_to="overrides/", blank=True, null=True)
    effective_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overrides_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overrides_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("reference_additive", "jurisdiction")]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Override {self.jurisdiction}:{self.status} → {self.reference_additive}"


class ReferenceSyncLog(models.Model):
    """Tracks import/sync of reference databases without touching local overrides."""

    class Action(models.TextChoices):
        IMPORT = "IMPORT", "Import"
        SYNC = "SYNC", "Sync"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        ReferenceSource, on_delete=models.SET_NULL, null=True, blank=True
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    records_read = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    records_skipped = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    success = models.BooleanField(default=True)

    class Meta:
        ordering = ["-started_at"]
