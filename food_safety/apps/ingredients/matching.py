"""Deterministic multi-layer ingredient matching — no AI."""
from __future__ import annotations

import re

from django.conf import settings
from django.db.models import Q
from rapidfuzz import fuzz, process

from apps.ingredients.models import Ingredient, IngredientAlias, UnmatchedQuery, normalize_alias
from apps.reference.models import ReferenceAdditive, ReferenceSynonym
from apps.reference.services import resolve_for_local_ingredient, resolve_for_reference

E_NUMBER_RE = re.compile(r"^E[-\s]?\d{3,4}[a-zA-Z]?$", re.IGNORECASE)
INS_RE = re.compile(r"^(INS[-\s]?)?\d{3,4}[a-zA-Z]?$", re.IGNORECASE)
CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")


def normalize_e_number(text: str) -> str:
    t = text.upper().replace(" ", "").replace("-", "")
    if t.startswith("E"):
        return t
    if t.isdigit() or (len(t) >= 3 and t[0].isdigit()):
        return f"E{t}"
    return t


def normalize_ins(text: str) -> str:
    t = text.upper().replace(" ", "").replace("-", "").replace("INS", "")
    return t


def match_ingredient(raw_text: str) -> dict:
    """
    Search order:
    1) Standard reference database (E/INS/CAS/name/synonym)
    2) Local ingredient database
    Then caller resolves effective Libya-first status.
    """
    text = (raw_text or "").strip()
    if not text:
        return {
            "matched": False,
            "reference_additive": None,
            "ingredient": None,
            "method": "none",
            "input": text,
        }

    # --- Reference layer ---
    ref = _match_reference(text)
    if ref:
        return ref

    # --- Local layer ---
    local = _match_local(text)
    if local:
        return local

    normalized = normalize_alias(text)
    uq, created = UnmatchedQuery.objects.get_or_create(
        query_normalized=normalized,
        defaults={"query_text": text},
    )
    if not created:
        uq.hit_count += 1
        uq.save(update_fields=["hit_count", "updated_at"])

    return {
        "matched": False,
        "reference_additive": None,
        "ingredient": None,
        "method": "none",
        "input": text,
    }


def _match_reference(text: str) -> dict | None:
    cleaned = text.replace(" ", "")
    if E_NUMBER_RE.match(cleaned) or text.upper().startswith("E"):
        e = normalize_e_number(text)
        additive = ReferenceAdditive.objects.filter(is_active=True).filter(
            Q(e_number__iexact=e) | Q(ins_number__iexact=normalize_ins(e))
        ).first()
        if additive:
            return _ref_hit(additive, text, "e_number")

    if text.upper().startswith("INS") or INS_RE.match(cleaned):
        ins = normalize_ins(text)
        additive = ReferenceAdditive.objects.filter(
            is_active=True, ins_number__iexact=ins
        ).first()
        if not additive:
            additive = ReferenceAdditive.objects.filter(
                is_active=True, e_number__iexact=f"E{ins}"
            ).first()
        if additive:
            return _ref_hit(additive, text, "ins_number")

    if CAS_RE.match(text.strip()):
        additive = ReferenceAdditive.objects.filter(
            is_active=True, cas_number__iexact=text.strip()
        ).first()
        if additive:
            return _ref_hit(additive, text, "cas_number")

    normalized = normalize_alias(text)
    syn = (
        ReferenceSynonym.objects.select_related("additive")
        .filter(synonym_normalized=normalized, additive__is_active=True)
        .first()
    )
    if syn:
        return _ref_hit(syn.additive, text, "exact_synonym")

    additive = ReferenceAdditive.objects.filter(is_active=True).filter(
        Q(name_en__iexact=text) | Q(name_ar__iexact=text)
    ).first()
    if additive:
        return _ref_hit(additive, text, "exact_name")

    # Fuzzy synonyms
    synonyms = list(
        ReferenceSynonym.objects.select_related("additive").filter(additive__is_active=True)
    )
    if synonyms:
        choices = {s.id: s.synonym_normalized for s in synonyms}
        result = process.extractOne(
            normalized,
            choices,
            scorer=fuzz.WRatio,
            score_cutoff=getattr(settings, "FUZZY_MATCH_THRESHOLD", 80),
        )
        if result:
            _m, score, sid = result
            syn_obj = next(s for s in synonyms if s.id == sid)
            hit = _ref_hit(syn_obj.additive, text, "fuzzy_synonym")
            hit["score"] = score
            return hit
    return None


def _match_local(text: str) -> dict | None:
    cleaned = text.replace(" ", "")
    if E_NUMBER_RE.match(cleaned) or text.upper().startswith("E"):
        e = normalize_e_number(text)
        ing = Ingredient.objects.filter(e_number__iexact=e).first()
        if ing:
            return _local_hit(ing, text, "e_number")

    if CAS_RE.match(text.strip()):
        ing = Ingredient.objects.filter(cas_number__iexact=text.strip()).first()
        if ing:
            return _local_hit(ing, text, "cas_number")

    normalized = normalize_alias(text)
    alias = (
        IngredientAlias.objects.select_related("ingredient")
        .filter(alias_normalized=normalized)
        .first()
    )
    if alias:
        return _local_hit(alias.ingredient, text, "exact_alias")

    ing = Ingredient.objects.filter(Q(name_ar__iexact=text) | Q(name_en__iexact=text)).first()
    if ing:
        return _local_hit(ing, text, "exact_name")

    aliases = list(IngredientAlias.objects.select_related("ingredient").all())
    if aliases:
        choices = {a.id: a.alias_normalized for a in aliases}
        result = process.extractOne(
            normalized,
            choices,
            scorer=fuzz.WRatio,
            score_cutoff=getattr(settings, "FUZZY_MATCH_THRESHOLD", 80),
        )
        if result:
            _m, score, alias_id = result
            alias_obj = next(a for a in aliases if a.id == alias_id)
            hit = _local_hit(alias_obj.ingredient, text, "fuzzy")
            hit["score"] = score
            return hit
    return None


def _ref_hit(additive: ReferenceAdditive, text: str, method: str) -> dict:
    return {
        "matched": True,
        "reference_additive": additive,
        "ingredient": additive.local_ingredients.first(),
        "method": method,
        "input": text,
        "effective": resolve_for_reference(additive),
    }


def _local_hit(ingredient: Ingredient, text: str, method: str) -> dict:
    return {
        "matched": True,
        "reference_additive": ingredient.reference_additive,
        "ingredient": ingredient,
        "method": method,
        "input": text,
        "effective": resolve_for_local_ingredient(ingredient),
    }


def find_duplicate_candidates(
    *,
    name_ar: str = "",
    name_en: str = "",
    e_number: str = "",
    cas_number: str = "",
    synonyms: list[str] | None = None,
) -> dict:
    """Used before creating local materials — prevent duplicates against reference + local."""
    refs = []
    locals_ = []
    queries = []
    if e_number:
        queries.append(e_number)
    if cas_number:
        queries.append(cas_number)
    if name_en:
        queries.append(name_en)
    if name_ar:
        queries.append(name_ar)
    for s in synonyms or []:
        if s.strip():
            queries.append(s.strip())

    seen_ref = set()
    seen_local = set()
    for q in queries:
        hit = match_ingredient(q)
        if not hit.get("matched"):
            continue
        ref = hit.get("reference_additive")
        ing = hit.get("ingredient")
        if ref and ref.id not in seen_ref:
            seen_ref.add(ref.id)
            refs.append(ref)
        if ing and ing.id not in seen_local:
            seen_local.add(ing.id)
            locals_.append(ing)
    return {"reference": refs, "local": locals_}
