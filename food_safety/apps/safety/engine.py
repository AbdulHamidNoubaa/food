"""Explicit deterministic Safety Rules Engine — no AI."""
from __future__ import annotations

from apps.ingredients.matching import match_ingredient
from apps.scans.models import SafetyAssessment


PRIORITY = {
    SafetyAssessment.ProductStatus.UNSAFE: 4,
    SafetyAssessment.ProductStatus.WARNING: 3,
    SafetyAssessment.ProductStatus.UNKNOWN: 2,
    SafetyAssessment.ProductStatus.SAFE: 1,
    SafetyAssessment.ProductStatus.PENDING: 0,
}

# Common pantry words from OCR that are not regulated additives — ignore in aggregation
_IGNORE_TOKENS = {
    "water",
    "salt",
    "sugar",
    "flour",
    "wheat flour",
    "palm oil",
    "flavor",
    "flavour",
    "natural flavor",
    "natural flavour",
    "flavouring",
    "flavoring",
    "glucose syrup",
    "lemon juice",
    "gelatin",
    "milk powder",
}


def classify_from_match(match: dict, input_text: str) -> dict:
    if not match.get("matched"):
        return {
            "input": input_text,
            "matched_ingredient_id": None,
            "reference_additive_id": None,
            "name_ar": None,
            "name_en": None,
            "e_number": None,
            "safety_status": SafetyAssessment.ProductStatus.UNKNOWN,
            "regulatory_status": "UNKNOWN",
            "db_safety_status": None,
            "risk_level": None,
            "reason": "لا يوجد سجل مطابق في قاعدة البيانات المرجعية أو المحلية",
            "source": None,
            "decision_layer": "unknown",
            "codex_status": None,
            "jecfa_status": None,
            "ocr_confidence": None,
        }

    effective = match["effective"]
    ref = match.get("reference_additive")
    ing = match.get("ingredient")

    name_ar = (ref.name_ar if ref else None) or (ing.name_ar if ing else None)
    name_en = (ref.name_en if ref else None) or (ing.name_en if ing else None)
    e_number = None
    if ref:
        e_number = ref.e_number or (f"INS {ref.ins_number}" if ref.ins_number else None)
    if not e_number and ing:
        e_number = ing.e_number

    return {
        "input": input_text,
        "matched_ingredient_id": str(ing.id) if ing else None,
        "reference_additive_id": str(ref.id) if ref else None,
        "name_ar": name_ar,
        "name_en": name_en,
        "e_number": e_number,
        "safety_status": effective.product_status,
        "regulatory_status": effective.regulatory_status,
        "db_safety_status": effective.regulatory_status,
        "risk_level": getattr(ing, "risk_level", None) if ing else None,
        "reason": effective.reason,
        "source": effective.source_label,
        "decision_layer": effective.decision_layer,
        "jurisdiction": effective.jurisdiction,
        "codex_status": effective.codex_status,
        "jecfa_status": effective.jecfa_status,
        "ocr_confidence": None,
        "match_method": match.get("method"),
    }


def classify_ingredient(ingredient, input_text: str) -> dict:
    """Backward-compatible wrapper when only a local Ingredient is known."""
    if ingredient is None:
        return classify_from_match({"matched": False}, input_text)
    from apps.reference.services import resolve_for_local_ingredient

    match = {
        "matched": True,
        "ingredient": ingredient,
        "reference_additive": ingredient.reference_additive,
        "method": "legacy",
        "effective": resolve_for_local_ingredient(ingredient),
    }
    return classify_from_match(match, input_text)


def aggregate_product_status(results: list[dict]) -> str:
    if not results:
        return SafetyAssessment.ProductStatus.PENDING

    filtered = []
    for r in results:
        key = (r.get("input") or "").strip().lower()
        if (
            r["safety_status"] == SafetyAssessment.ProductStatus.UNKNOWN
            and key in _IGNORE_TOKENS
        ):
            continue
        filtered.append(r)

    if not filtered:
        return SafetyAssessment.ProductStatus.SAFE

    best = max(filtered, key=lambda r: PRIORITY.get(r["safety_status"], 0))
    return best["safety_status"]


def assess_ingredient_texts(texts: list[str], confidence_map: dict[str, float] | None = None) -> dict:
    """
    texts: list of ingredient strings (from DB product or OCR).
    confidence_map: optional OCR confidence per text — NEVER used for safety_status.
    """
    confidence_map = confidence_map or {}
    results = []
    for text in texts:
        text = (text or "").strip()
        if not text:
            continue
        match = match_ingredient(text)
        row = classify_from_match(match, text)
        if text in confidence_map:
            row["ocr_confidence"] = confidence_map[text]
        results.append(row)

    product_status = aggregate_product_status(results)

    reasons = []
    for r in results:
        key = (r.get("input") or "").strip().lower()
        if (
            r["safety_status"] == SafetyAssessment.ProductStatus.UNKNOWN
            and key in _IGNORE_TOKENS
        ):
            continue
        if r["safety_status"] in (
            SafetyAssessment.ProductStatus.UNSAFE,
            SafetyAssessment.ProductStatus.WARNING,
            SafetyAssessment.ProductStatus.UNKNOWN,
        ):
            label = r.get("e_number") or r.get("name_ar") or r["input"]
            layer = r.get("decision_layer") or ""
            reasons.append(f"{label}: {r['reason']} [{layer}]")

    summary = (
        "؛ ".join(reasons[:5])
        if reasons
        else "جميع المكونات المطابقة ضمن الحالة الآمنة وفق القواعد النافذة للاختصاص الحالي"
    )

    return {
        "product_status": product_status,
        "results": results,
        "summary_reason": summary,
    }


def assess_product(product) -> dict:
    texts = []
    for pi in product.product_ingredients.select_related("ingredient").all():
        ing = pi.ingredient
        texts.append(ing.e_number or ing.name_ar or ing.name_en)
    return assess_ingredient_texts(texts)
