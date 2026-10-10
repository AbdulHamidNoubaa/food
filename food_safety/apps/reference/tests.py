from django.test import TestCase

from apps.ingredients.matching import match_ingredient
from apps.reference.models import (
    LocalRegulatoryOverride,
    ReferenceAdditive,
    ReferenceSource,
    ReferenceStatusRecord,
    RegulatoryStatus,
)
from apps.reference.services import resolve_for_reference
from apps.safety.engine import classify_from_match
from apps.scans.models import SafetyAssessment


class LibyaFirstRulesTests(TestCase):
    def setUp(self):
        codex = ReferenceSource.objects.create(code="CODEX_GSFA", name_en="Codex GSFA")
        jecfa = ReferenceSource.objects.create(code="JECFA", name_en="JECFA")
        self.additive = ReferenceAdditive.objects.create(
            name_en="Titanium Dioxide",
            name_ar="ثاني أكسيد التيتانيوم",
            e_number="E171",
            ins_number="171",
            primary_source=codex,
        )
        ReferenceStatusRecord.objects.create(
            additive=self.additive,
            source=codex,
            jurisdiction="GLOBAL",
            status=RegulatoryStatus.PERMITTED,
        )
        ReferenceStatusRecord.objects.create(
            additive=self.additive,
            source=jecfa,
            jurisdiction="GLOBAL",
            status=RegulatoryStatus.PERMITTED,
        )
        LocalRegulatoryOverride.objects.create(
            reference_additive=self.additive,
            jurisdiction="LY",
            status=RegulatoryStatus.PROHIBITED,
            reason="محظور وفق المعيار الليبي",
            regulatory_source="Libyan Standard 15/2025",
        )

    def test_codex_permitted_does_not_auto_allow_in_libya(self):
        eff = resolve_for_reference(self.additive)
        self.assertEqual(eff.regulatory_status, RegulatoryStatus.PROHIBITED)
        self.assertEqual(eff.decision_layer, "override")
        self.assertEqual(eff.codex_status, RegulatoryStatus.PERMITTED)
        self.assertEqual(eff.product_status, SafetyAssessment.ProductStatus.UNSAFE)

    def test_search_e171_and_name_same_material(self):
        a = match_ingredient("E171")
        b = match_ingredient("Titanium Dioxide")
        self.assertTrue(a["matched"] and b["matched"])
        self.assertEqual(a["reference_additive"].id, b["reference_additive"].id)
        ra = classify_from_match(a, "E171")
        self.assertEqual(ra["safety_status"], SafetyAssessment.ProductStatus.UNSAFE)

    def test_reference_info_without_override_is_unknown(self):
        LocalRegulatoryOverride.objects.all().delete()
        other = ReferenceAdditive.objects.create(
            name_en="Some Additive", e_number="E999", primary_source=self.additive.primary_source
        )
        ReferenceStatusRecord.objects.create(
            additive=other,
            source=self.additive.primary_source,
            jurisdiction="GLOBAL",
            status=RegulatoryStatus.PERMITTED,
        )
        eff = resolve_for_reference(other)
        self.assertEqual(eff.regulatory_status, RegulatoryStatus.UNKNOWN)
        self.assertEqual(eff.decision_layer, "reference_info")
        self.assertEqual(eff.product_status, SafetyAssessment.ProductStatus.UNKNOWN)
