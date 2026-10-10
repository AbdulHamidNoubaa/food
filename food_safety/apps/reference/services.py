"""
Resolve effective regulatory status for an additive.

Priority (explicit rules — no AI):
1) Active LocalRegulatoryOverride for ACTIVE_JURISDICTION (e.g. LY)
2) ReferenceStatusRecord for ACTIVE_JURISDICTION (Libyan imported statuses)
3) Local Ingredient record status (LOCAL-only materials)
4) Informational Codex/JECFA status (does NOT auto-permit in Libya)
5) UNKNOWN
"""
from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.ingredients.models import Ingredient
from apps.reference.models import (
    LocalRegulatoryOverride,
    ReferenceAdditive,
    ReferenceStatusRecord,
    RegulatoryStatus,
)
from apps.scans.models import SafetyAssessment


STATUS_TO_PRODUCT = {
    RegulatoryStatus.PROHIBITED: SafetyAssessment.ProductStatus.UNSAFE,
    RegulatoryStatus.RESTRICTED: SafetyAssessment.ProductStatus.WARNING,
    RegulatoryStatus.UNDER_REVIEW: SafetyAssessment.ProductStatus.WARNING,
    RegulatoryStatus.PERMITTED: SafetyAssessment.ProductStatus.SAFE,
    RegulatoryStatus.UNKNOWN: SafetyAssessment.ProductStatus.UNKNOWN,
}

LEGACY_INGREDIENT_TO_REG = {
    Ingredient.SafetyStatus.PROHIBITED: RegulatoryStatus.PROHIBITED,
    Ingredient.SafetyStatus.RESTRICTED: RegulatoryStatus.RESTRICTED,
    Ingredient.SafetyStatus.UNDER_REVIEW: RegulatoryStatus.UNDER_REVIEW,
    Ingredient.SafetyStatus.APPROVED: RegulatoryStatus.PERMITTED,
    Ingredient.SafetyStatus.INACTIVE: RegulatoryStatus.UNKNOWN,
}


@dataclass
class EffectiveClassification:
    regulatory_status: str
    product_status: str
    reason: str
    source_label: str
    jurisdiction: str
    decision_layer: str  # override | local_ingredient | reference_jurisdiction | reference_info | unknown
    reference_additive_id: str | None = None
    local_ingredient_id: str | None = None
    codex_status: str | None = None
    jecfa_status: str | None = None


def _jurisdiction() -> str:
    return getattr(settings, "ACTIVE_JURISDICTION", "LY")


def _info_statuses(additive: ReferenceAdditive) -> dict[str, str]:
    out = {}
    for rec in additive.status_records.filter(is_active=True).select_related("source"):
        code = (rec.source.code or "").upper()
        if "CODEX" in code:
            out["codex"] = rec.status
        if "JECFA" in code:
            out["jecfa"] = rec.status
    return out


def resolve_for_reference(additive: ReferenceAdditive) -> EffectiveClassification:
    juris = _jurisdiction()
    info = _info_statuses(additive)

    override = (
        LocalRegulatoryOverride.objects.filter(
            reference_additive=additive, jurisdiction=juris, is_active=True
        )
        .order_by("-effective_date", "-updated_at")
        .first()
    )
    if override:
        return EffectiveClassification(
            regulatory_status=override.status,
            product_status=STATUS_TO_PRODUCT.get(
                override.status, SafetyAssessment.ProductStatus.UNKNOWN
            ),
            reason=override.reason
            or f"تصنيف محلي ({juris}) وفق {override.regulatory_source or 'مرجع محلي'}",
            source_label=override.regulatory_source
            or override.reference_number
            or f"Local Override ({juris})",
            jurisdiction=juris,
            decision_layer="override",
            reference_additive_id=str(additive.id),
            codex_status=info.get("codex"),
            jecfa_status=info.get("jecfa"),
        )

    local_ref_status = (
        ReferenceStatusRecord.objects.filter(
            additive=additive, jurisdiction=juris, is_active=True
        )
        .select_related("source")
        .order_by("-effective_date", "-updated_at")
        .first()
    )
    if local_ref_status:
        return EffectiveClassification(
            regulatory_status=local_ref_status.status,
            product_status=STATUS_TO_PRODUCT.get(
                local_ref_status.status, SafetyAssessment.ProductStatus.UNKNOWN
            ),
            reason=local_ref_status.reason
            or f"حالة تنظيمية ({juris}) من {local_ref_status.source}",
            source_label=f"{local_ref_status.source.code}: {local_ref_status.document_reference}".strip(
                ": "
            ),
            jurisdiction=juris,
            decision_layer="reference_jurisdiction",
            reference_additive_id=str(additive.id),
            codex_status=info.get("codex"),
            jecfa_status=info.get("jecfa"),
        )

    # Linked local Ingredient (legacy bridge)
    linked = additive.local_ingredients.filter(data_origin=Ingredient.DataOrigin.LOCAL).first()
    if linked:
        reg = LEGACY_INGREDIENT_TO_REG.get(linked.safety_status, RegulatoryStatus.UNKNOWN)
        return EffectiveClassification(
            regulatory_status=reg,
            product_status=STATUS_TO_PRODUCT.get(reg, SafetyAssessment.ProductStatus.UNKNOWN),
            reason=linked.reason or "تصنيف من السجل المحلي المرتبط",
            source_label=linked.source or "Local Ingredient",
            jurisdiction=juris,
            decision_layer="local_ingredient",
            reference_additive_id=str(additive.id),
            local_ingredient_id=str(linked.id),
            codex_status=info.get("codex"),
            jecfa_status=info.get("jecfa"),
        )

    # Informational only — Codex/JECFA must NOT auto-permit for Libya
    info_rec = (
        ReferenceStatusRecord.objects.filter(additive=additive, is_active=True)
        .exclude(jurisdiction=juris)
        .select_related("source")
        .order_by("-updated_at")
        .first()
    )
    if info_rec:
        return EffectiveClassification(
            regulatory_status=RegulatoryStatus.UNKNOWN,
            product_status=SafetyAssessment.ProductStatus.UNKNOWN,
            reason=(
                f"المادة معروفة في {info_rec.source.code} بحالة {info_rec.get_status_display()}، "
                f"لكن لا يوجد تصنيف نافذ لـ {juris}. لا يُفترض السماح تلقائيًا."
            ),
            source_label=f"{info_rec.source.code} (معلوماتي فقط)",
            jurisdiction=juris,
            decision_layer="reference_info",
            reference_additive_id=str(additive.id),
            codex_status=info.get("codex"),
            jecfa_status=info.get("jecfa"),
        )

    return EffectiveClassification(
        regulatory_status=RegulatoryStatus.UNKNOWN,
        product_status=SafetyAssessment.ProductStatus.UNKNOWN,
        reason="لا يوجد تصنيف تنظيمي نافذ للاختصاص الحالي",
        source_label=None or "—",
        jurisdiction=juris,
        decision_layer="unknown",
        reference_additive_id=str(additive.id),
        codex_status=info.get("codex"),
        jecfa_status=info.get("jecfa"),
    )


def resolve_for_local_ingredient(ingredient: Ingredient) -> EffectiveClassification:
    juris = _jurisdiction()
    if ingredient.reference_additive_id:
        return resolve_for_reference(ingredient.reference_additive)

    reg = LEGACY_INGREDIENT_TO_REG.get(ingredient.safety_status, RegulatoryStatus.UNKNOWN)
    # High risk without clear permit → treat carefully
    product = STATUS_TO_PRODUCT.get(reg, SafetyAssessment.ProductStatus.UNKNOWN)
    if (
        reg == RegulatoryStatus.PERMITTED
        and ingredient.risk_level == Ingredient.RiskLevel.HIGH
    ):
        product = SafetyAssessment.ProductStatus.WARNING
    return EffectiveClassification(
        regulatory_status=reg,
        product_status=product,
        reason=ingredient.reason or "تصنيف من البيانات المحلية فقط",
        source_label=ingredient.source or "Local Data",
        jurisdiction=juris,
        decision_layer="local_ingredient",
        local_ingredient_id=str(ingredient.id),
    )
