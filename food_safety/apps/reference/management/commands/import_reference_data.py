"""
Seed / import Standard Food Additives reference data.

- Creates Codex / JECFA / Libya sources
- Imports a starter GSFA-style sample set (expandable via JSON)
- Maps existing local PROHIBITED Ingredient rows to Reference + Libya Override
  without deleting local data

Usage:
  python manage.py import_reference_data
  python manage.py import_reference_data --json path/to/file.json
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.ingredients.models import Ingredient, IngredientAlias
from apps.reference.models import (
    LocalRegulatoryOverride,
    ReferenceAdditive,
    ReferenceSource,
    ReferenceStatusRecord,
    ReferenceSyncLog,
    ReferenceSynonym,
    RegulatoryStatus,
)

# Starter reference sample (Codex-style). Expand via --json without wiping locals.
STARTER_REFERENCE = [
    {
        "name_en": "Titanium Dioxide",
        "name_ar": "ثاني أكسيد التيتانيوم",
        "e_number": "E171",
        "ins_number": "171",
        "cas_number": "13463-67-7",
        "functional_class": "Colour",
        "uses": "Whitening / opacity in foods",
        "synonyms": ["TiO2", "Pigment White 6"],
        "codex_status": "PERMITTED",
        "jecfa_status": "PERMITTED",
        "libya_status": "PROHIBITED",
        "libya_reason": "محظور وفق المواصفة القياسية الليبية رقم 15 لسنة 2025",
        "libya_ref": "معيار 15/2025 — إشاري 1581/3",
    },
    {
        "name_en": "Citric Acid",
        "name_ar": "حمض الستريك",
        "e_number": "E330",
        "ins_number": "330",
        "cas_number": "77-92-9",
        "functional_class": "Acidity regulator",
        "uses": "Acidulant / antioxidant synergist",
        "synonyms": ["Citric acid anhydrous"],
        "codex_status": "PERMITTED",
        "jecfa_status": "PERMITTED",
        "libya_status": "PERMITTED",
        "libya_reason": "مسموح وفق قاعدة الاستخدام العامة مع شروط الاستخدام",
        "libya_ref": "مرجع تشغيلي محلي",
    },
    {
        "name_en": "Mono- and Diglycerides of Fatty Acids",
        "name_ar": "أحادي وثنائي الجليسريدات",
        "e_number": "E471",
        "ins_number": "471",
        "functional_class": "Emulsifier",
        "uses": "Emulsification",
        "synonyms": ["Glyceryl monostearate"],
        "codex_status": "PERMITTED",
        "jecfa_status": "PERMITTED",
        "libya_status": "RESTRICTED",
        "libya_reason": "مقيد ويتطلب مراجعة إضافية وفق التصنيف المحلي",
        "libya_ref": "تصنيف محلي",
    },
    {
        "name_en": "Carmines",
        "name_ar": "كارمينات",
        "e_number": "E120",
        "ins_number": "120",
        "cas_number": "1260-17-9",
        "functional_class": "Colour",
        "uses": "Red colouring",
        "synonyms": ["Cochineal", "Carminic acid"],
        "codex_status": "PERMITTED",
        "jecfa_status": "PERMITTED",
        "libya_status": "PROHIBITED",
        "libya_reason": "محظور ضمن قائمة الألوان وفق المعيار الليبي 15/2025",
        "libya_ref": "معيار 15/2025",
    },
    {
        "name_en": "Patent Blue V",
        "name_ar": "أزرق مسجل في",
        "e_number": "E131",
        "ins_number": "131",
        "functional_class": "Colour",
        "uses": "Blue colouring",
        "synonyms": ["Food Blue 5"],
        "codex_status": "PERMITTED",
        "jecfa_status": "PERMITTED",
        "libya_status": "PROHIBITED",
        "libya_reason": "محظور وفق المعيار الليبي 15/2025",
        "libya_ref": "معيار 15/2025",
    },
]


class Command(BaseCommand):
    help = "Import/sync standard reference additives without wiping local overrides"

    def add_arguments(self, parser):
        parser.add_argument("--json", type=str, default="", help="Optional JSON file of additives")

    @transaction.atomic
    def handle(self, *args, **options):
        codex = self._source(
            "CODEX_GSFA",
            "Codex Alimentarius – GSFA",
            "دستور الأغذية — المواصفة العامة للمواد المضافة",
            "https://www.fao.org/fao-who-codexalimentarius/",
        )
        jecfa = self._source(
            "JECFA",
            "FAO/WHO JECFA",
            "لجنة الخبراء المشتركة FAO/WHO للمواد المضافة للأغذية",
            "https://www.fao.org/food/food-safety-quality/scientific-advice/jecfa/",
        )
        libya = self._source(
            "LIBYA_STD_15_2025",
            "Libyan Standard 15/2025",
            "المواصفة القياسية الليبية رقم 15 لسنة 2025",
            "",
        )

        payload = list(STARTER_REFERENCE)
        json_path = options.get("json") or ""
        if json_path:
            data = json.loads(Path(json_path).read_text(encoding="utf-8"))
            payload.extend(data if isinstance(data, list) else data.get("additives", []))

        sync = ReferenceSyncLog.objects.create(
            source=codex,
            action=ReferenceSyncLog.Action.IMPORT,
            records_read=len(payload),
            notes="Starter/import reference load",
        )
        created = updated = skipped = 0

        for row in payload:
            additive, was_created = self._upsert_additive(row, codex)
            if was_created:
                created += 1
            else:
                updated += 1
            self._ensure_synonyms(additive, row)
            self._ensure_status(additive, codex, "GLOBAL", row.get("codex_status"), "GSFA")
            self._ensure_status(additive, jecfa, "GLOBAL", row.get("jecfa_status"), "JECFA evaluation")
            if row.get("libya_status"):
                self._ensure_override(
                    additive,
                    status=row["libya_status"],
                    reason=row.get("libya_reason", ""),
                    source_name=libya.name_en,
                    ref_no=row.get("libya_ref", ""),
                )

        # Bridge existing local prohibited ingredients → reference + override
        bridged = self._bridge_local_prohibited(codex, libya)
        skipped += bridged["skipped"]
        created += bridged["created"]

        sync.records_created = created
        sync.records_updated = updated
        sync.records_skipped = skipped
        sync.finished_at = timezone.now()
        sync.success = True
        sync.save()

        AuditLog.objects.create(
            action="reference.import",
            entity_type="ReferenceSyncLog",
            entity_id=str(sync.id),
            new_value={
                "created": created,
                "updated": updated,
                "bridged": bridged,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Reference import done. created={created} updated={updated} bridged={bridged}"
            )
        )

    def _source(self, code, name_en, name_ar, url):
        obj, _ = ReferenceSource.objects.update_or_create(
            code=code,
            defaults={
                "name_en": name_en,
                "name_ar": name_ar,
                "website_url": url,
                "is_active": True,
            },
        )
        return obj

    def _upsert_additive(self, row, primary_source):
        e = (row.get("e_number") or "").strip().upper() or None
        ins = (row.get("ins_number") or "").strip() or None
        cas = (row.get("cas_number") or "").strip() or None
        qs = ReferenceAdditive.objects.all()
        additive = None
        if e:
            additive = qs.filter(e_number__iexact=e).first()
        if not additive and ins:
            additive = qs.filter(ins_number__iexact=ins).first()
        if not additive and cas:
            additive = qs.filter(cas_number__iexact=cas).first()
        if not additive and row.get("name_en"):
            additive = qs.filter(name_en__iexact=row["name_en"]).first()

        defaults = {
            "name_en": row.get("name_en") or "",
            "name_ar": row.get("name_ar") or "",
            "scientific_name": row.get("scientific_name") or "",
            "e_number": e,
            "ins_number": ins,
            "cas_number": cas,
            "functional_class": row.get("functional_class") or "",
            "uses": row.get("uses") or "",
            "primary_source": primary_source,
            "last_synced_at": timezone.now(),
            "is_active": True,
        }
        if additive:
            for k, v in defaults.items():
                setattr(additive, k, v)
            additive.save()
            return additive, False
        return ReferenceAdditive.objects.create(**defaults), True

    def _ensure_synonyms(self, additive, row):
        names = [row.get("name_en"), row.get("name_ar"), row.get("e_number")]
        names += row.get("synonyms") or []
        for syn in names:
            if not syn:
                continue
            lang = "ar" if syn == row.get("name_ar") else "en"
            ReferenceSynonym.objects.get_or_create(
                additive=additive, synonym=str(syn).strip(), language=lang
            )

    def _ensure_status(self, additive, source, jurisdiction, status, doc):
        if not status:
            return
        ReferenceStatusRecord.objects.update_or_create(
            additive=additive,
            source=source,
            jurisdiction=jurisdiction,
            defaults={
                "status": status,
                "document_reference": doc,
                "is_active": True,
                "effective_date": date(2025, 1, 1),
            },
        )

    def _ensure_override(self, additive, status, reason, source_name, ref_no):
        LocalRegulatoryOverride.objects.update_or_create(
            reference_additive=additive,
            jurisdiction="LY",
            defaults={
                "status": status,
                "reason": reason,
                "regulatory_source": source_name,
                "reference_number": ref_no,
                "is_active": True,
                "effective_date": date(2025, 4, 12),
            },
        )

    def _bridge_local_prohibited(self, codex, libya):
        created = skipped = 0
        for ing in Ingredient.objects.filter(safety_status=Ingredient.SafetyStatus.PROHIBITED):
            additive = None
            if ing.e_number:
                additive = ReferenceAdditive.objects.filter(e_number__iexact=ing.e_number).first()
            if not additive:
                additive = ReferenceAdditive.objects.filter(name_en__iexact=ing.name_en).first()
            if not additive:
                additive = ReferenceAdditive.objects.create(
                    name_en=ing.name_en or ing.name_ar,
                    name_ar=ing.name_ar,
                    e_number=ing.e_number,
                    cas_number=getattr(ing, "cas_number", None),
                    functional_class=ing.category,
                    primary_source=codex,
                    notes="Bridged from existing local prohibited ingredient",
                    last_synced_at=timezone.now(),
                )
                created += 1
                for a in ing.aliases.all():
                    ReferenceSynonym.objects.get_or_create(
                        additive=additive, synonym=a.alias, language=a.language
                    )
            else:
                skipped += 1

            LocalRegulatoryOverride.objects.update_or_create(
                reference_additive=additive,
                jurisdiction="LY",
                defaults={
                    "status": RegulatoryStatus.PROHIBITED,
                    "reason": ing.reason or "محظور وفق البيانات المحلية",
                    "regulatory_source": ing.source or libya.name_en,
                    "reference_number": ing.regulatory_status or "",
                    "notes": ing.notes or "",
                    "is_active": True,
                    "effective_date": ing.last_updated or date(2025, 4, 12),
                    "created_by": ing.created_by,
                    "updated_by": ing.updated_by,
                },
            )
            # Link local ingredient to reference without deleting it
            ing.reference_additive = additive
            ing.data_origin = Ingredient.DataOrigin.REFERENCE
            ing.save(update_fields=["reference_additive", "data_origin", "updated_at"])
        return {"created": created, "skipped": skipped}
