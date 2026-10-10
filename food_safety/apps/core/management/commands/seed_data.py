"""
Seed Libyan prohibited additives (Standard 15/2025) + demo users/products/stores.
Source: Food & Drug Control Center — Libya, circular 1581/3, 2026-04-12.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, User
from apps.ingredients.models import Ingredient, IngredientAlias, IngredientSource
from apps.products.models import Brand, Product, ProductIngredient
from apps.safety.models import SafetyRule
from apps.stores.models import MunicipalAuthority

SOURCE = "مركز الرقابة على الأغذية والأدوية - ليبيا"
DOC_REF = "المواصفة القياسية الليبية رقم 15 لسنة 2025 — إشاري 1581/3"
SEED_DATE = date(2026, 4, 12)

# Official prohibited colors from the attached list (design doc §1.7 / §9.4)
PROHIBITED = [
    # Reds / violets
    ("E120", "كارمينات", "Carmines", "ألوان حمراء وبنفسجية"),
    ("E121", "بونيكو إس إكس", "Ponceau SX", "ألوان حمراء وبنفسجية"),
    ("E125", "أحمر الحمضيات 2", "Citrus Red 2", "ألوان حمراء وبنفسجية"),
    ("E126", "بونيكو 6 آر", "Ponceau 6R", "ألوان حمراء وبنفسجية"),
    ("E128", "أحمر 2جي", "Red 2G", "ألوان حمراء وبنفسجية"),
    ("E130", "أنثراكينون أزرق", "Anthraquinone Blue / Indanthrene Blue", "ألوان حمراء وبنفسجية"),
    ("E180", "ليثول روبيني بي كيه", "Lithol Rubine BK", "ألوان حمراء وبنفسجية"),
    ("E182", "أوركيل", "Orchil", "ألوان حمراء وبنفسجية"),
    # Yellows / browns
    ("E103", "ألكانيت", "Alkanet", "ألوان صفراء وبنية"),
    ("E107", "أصفر 2جي", "Yellow 2G", "ألوان صفراء وبنية"),
    ("E154", "بني إف كيه", "Brown FK", "ألوان صفراء وبنية"),
    ("E164", "أصفر جاردينيا", "Gardenia Yellow", "ألوان صفراء وبنية"),
    # Greens / blues
    ("E131", "أزرق مسجل في", "Patent Blue V", "ألوان خضراء وزرقاء"),
    ("E142", "الأخضر إس", "Green S", "ألوان خضراء وزرقاء"),
    ("E165", "أزرق جاردينيا", "Gardenia Blue", "ألوان خضراء وزرقاء"),
    # Metals / bleaching
    ("E171", "ثاني أكسيد التيتانيوم", "Titanium Dioxide", "معادن ومبيضات"),
    ("E173", "ألومنيوم", "Aluminium", "معادن ومبيضات"),
    ("E174", "فضة", "Silver", "معادن ومبيضات"),
    ("E175", "ذهب معدني", "Gold metallic", "معادن ومبيضات"),
    # Carbon / plant
    ("E152", "كربون أسود", "Carbon Black", "كربون ومواد نباتية"),
    ("E153", "كربون نباتي", "Vegetable Carbon", "كربون ومواد نباتية"),
    ("E166", "خشب الصندل", "Sandal Wood", "كربون ومواد نباتية"),
    ("E181", "تانينات", "Tannins", "كربون ومواد نباتية"),
]

APPROVED = [
    ("E330", "حمض الستريك", "Citric Acid", "أحماض ومنظمات حموضة", Ingredient.RiskLevel.LOW),
    ("E322", "ليسيثين", "Lecithins", "مستحلبات", Ingredient.RiskLevel.LOW),
    ("E471", "أحادي وثنائي الجليسريدات", "Mono- and Diglycerides of Fatty Acids", "مستحلبات", Ingredient.RiskLevel.MEDIUM),
    ("", "سكر", "Sugar", "محليات", Ingredient.RiskLevel.LOW),
    ("", "زيت النخيل", "Palm Oil", "زيوت", Ingredient.RiskLevel.LOW),
    ("", "حليب بودرة", "Milk Powder", "ألبان", Ingredient.RiskLevel.LOW),
]


class Command(BaseCommand):
    help = "Load Libyan prohibited additives seed + demo data"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding users...")
        users = self._users()
        self.stdout.write("Seeding ingredients (Libyan Standard 15/2025)...")
        ingredients = self._ingredients()
        self.stdout.write("Seeding authorities (no static store catalog)...")
        self._geo()
        self.stdout.write("Seeding products...")
        self._products(ingredients)
        self.stdout.write("Seeding safety rules...")
        self._rules(users["admin"])
        self.stdout.write("Importing standard reference additives + Libya overrides...")
        from django.core.management import call_command

        call_command("import_reference_data")
        self.stdout.write(self.style.SUCCESS("Seed completed successfully."))
        self.stdout.write("Demo logins:")
        self.stdout.write("  admin / admin123")
        self.stdout.write("  user / user123")
        self.stdout.write("  officer / officer123")
        self.stdout.write("  inspector / inspector123")
        self.stdout.write("  specialist / specialist123")

    def _users(self):
        def ensure(username, role, full_name, password):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "role": role,
                    "full_name": full_name,
                    "email": f"{username}@foodsafety.ly",
                    "is_staff": role == Role.ADMIN,
                    "is_superuser": role == Role.ADMIN,
                },
            )
            if created:
                user.set_password(password)
                user.save()
            return user

        return {
            "admin": ensure("admin", Role.ADMIN, "مدير النظام", "admin123"),
            "user": ensure("user", Role.USER, "مستهلك تجريبي", "user123"),
            "officer": ensure("officer", Role.MUNICIPAL_OFFICER, "ضابط الحرس البلدي", "officer123"),
            "inspector": ensure("inspector", Role.INSPECTOR, "مفتش ميداني", "inspector123"),
            "specialist": ensure(
                "specialist", Role.FOOD_SAFETY_SPECIALIST, "أخصائي سلامة غذاء", "specialist123"
            ),
        }

    def _ingredients(self):
        mapping = {}
        for e, ar, en, cat in PROHIBITED:
            ing, _ = Ingredient.objects.update_or_create(
                e_number=e,
                defaults={
                    "name_ar": ar,
                    "name_en": en,
                    "category": cat,
                    "risk_level": Ingredient.RiskLevel.HIGH,
                    "safety_status": Ingredient.SafetyStatus.PROHIBITED,
                    "reason": f"محظور وفق {DOC_REF}",
                    "regulatory_status": "محظور",
                    "source": SOURCE,
                    "last_updated": SEED_DATE,
                },
            )
            IngredientAlias.objects.get_or_create(
                ingredient=ing, alias=ar, language="ar",
                defaults={},
            )
            IngredientAlias.objects.get_or_create(
                ingredient=ing, alias=en, language="en",
            )
            IngredientAlias.objects.get_or_create(
                ingredient=ing, alias=e, language="en",
            )
            IngredientSource.objects.get_or_create(
                ingredient=ing,
                source_name=SOURCE,
                defaults={"document_reference": DOC_REF},
            )
            mapping[e] = ing

        for e, ar, en, cat, risk in APPROVED:
            status = (
                Ingredient.SafetyStatus.RESTRICTED
                if risk == Ingredient.RiskLevel.MEDIUM
                else Ingredient.SafetyStatus.APPROVED
            )
            defaults = {
                "name_ar": ar,
                "name_en": en,
                "category": cat,
                "risk_level": risk,
                "safety_status": status,
                "reason": "قيد الاستخدام وفق قاعدة البيانات المرجعية" if status != Ingredient.SafetyStatus.APPROVED else "معتمد في قاعدة البيانات",
                "source": "Food Ingredients Database",
                "last_updated": SEED_DATE,
            }
            if e:
                ing, _ = Ingredient.objects.update_or_create(e_number=e, defaults=defaults)
                mapping[e] = ing
            else:
                ing, _ = Ingredient.objects.update_or_create(name_en=en, defaults={**defaults, "e_number": None})
                mapping[en] = ing
            IngredientAlias.objects.get_or_create(ingredient=ing, alias=ar, language="ar")
            IngredientAlias.objects.get_or_create(ingredient=ing, alias=en, language="en")
            if e:
                IngredientAlias.objects.get_or_create(ingredient=ing, alias=e, language="en")
        return mapping

    def _geo(self):
        MunicipalAuthority.objects.get_or_create(
            name="الحرس البلدي — طرابلس",
            defaults={
                "city": "طرابلس",
                "district": "المركز",
                "contact_phone": "021-000000",
                "min_lat": 32.75,
                "max_lat": 32.95,
                "min_lng": 13.05,
                "max_lng": 13.35,
            },
        )
        # المنشآت تُنشأ ديناميكيًا عبر البلاغات — لا قائمة تجريبية ثابتة.

    def _products(self, ingredients):
        brand, _ = Brand.objects.get_or_create(
            name_ar="علامة تجريبية",
            defaults={"name_en": "Demo Brand", "country_of_origin": "ليبيا"},
        )
        p1, _ = Product.objects.update_or_create(
            barcode="6223000000001",
            defaults={
                "name_ar": "بسكويت تجريبي",
                "name_en": "Demo Biscuit",
                "brand": brand,
                "country_of_origin": "ليبيا",
                "manufacturer": "مصنع تجريبي",
                "category": "حلويات",
            },
        )
        links = [
            ("Sugar", 1),
            ("Palm Oil", 2),
            ("E471", 3),
            ("E322", 4),
        ]
        for key, pos in links:
            ing = ingredients[key]
            ProductIngredient.objects.get_or_create(
                product=p1, ingredient=ing, defaults={"position_in_list": pos}
            )

        p2, _ = Product.objects.update_or_create(
            barcode="6223000000002",
            defaults={
                "name_ar": "حلوى ملونة تجريبية",
                "name_en": "Demo Colored Candy",
                "brand": brand,
                "country_of_origin": "غير محدد",
                "category": "حلويات",
            },
        )
        for key, pos in [("Sugar", 1), ("E171", 2), ("E120", 3)]:
            ProductIngredient.objects.get_or_create(
                product=p2, ingredient=ingredients[key], defaults={"position_in_list": pos}
            )

        p3, _ = Product.objects.update_or_create(
            barcode="6223000000003",
            defaults={
                "name_ar": "عصير ليمون طبيعي تجريبي",
                "name_en": "Demo Lemon Drink",
                "brand": brand,
                "category": "مشروبات",
            },
        )
        for key, pos in [("Sugar", 1), ("E330", 2)]:
            ProductIngredient.objects.get_or_create(
                product=p3, ingredient=ingredients[key], defaults={"position_in_list": pos}
            )

    def _rules(self, admin):
        SafetyRule.objects.get_or_create(
            rule_name="Prohibited → UNSAFE",
            defaults={
                "condition_expression": {"safety_status": "PROHIBITED"},
                "resulting_status": SafetyRule.ResultingStatus.UNSAFE,
                "weight": 40,
                "created_by": admin,
            },
        )
        SafetyRule.objects.get_or_create(
            rule_name="Restricted → WARNING",
            defaults={
                "condition_expression": {"safety_status": "RESTRICTED"},
                "resulting_status": SafetyRule.ResultingStatus.WARNING,
                "weight": 15,
                "created_by": admin,
            },
        )
