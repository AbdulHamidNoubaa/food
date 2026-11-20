"""
Import named products from products-barcodes.xlsx and attach a category-typical
food composition so the safety rules engine can classify them.

Sheets «بدون اسم» and «مستبعدة» are not inserted: a barcode that is not in the
product table cannot be classified.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.ingredients.models import Ingredient, IngredientAlias
from apps.products.models import Brand, Product, ProductIngredient

SOURCE = "تركيبة غذائية تقديرية حسب فئة المنتج — ليست قراءة ملصق"
BASIC_REASON = "مكوّن غذائي أساسي ضمن التركيبة المعتادة للفئة، وليس مادة مضافة محظورة."

# Categories that are recorded for reference but have no food composition.
NON_FOOD_CATEGORIES = {
    "منتجات غير غذائية",
    "تبغ وسجائر",
    "مكملات غذائية",
    "أخرى",
}

# key -> (name_ar, name_en, category)
COMPONENTS = {
    "water": ("ماء", "Water", "مكونات أساسية"),
    "salt": ("ملح", "Salt", "مكونات أساسية"),
    "sugar": ("سكر", "Sugar", "محليات"),
    "flour": ("دقيق القمح", "Wheat Flour", "حبوب"),
    "palm": ("زيت النخيل", "Palm Oil", "زيوت"),
    "milk": ("حليب", "Milk", "ألبان"),
    "milk_powder": ("حليب بودرة", "Milk Powder", "ألبان"),
    "yogurt": ("بادئ الزبادي", "Yogurt Culture", "ألبان"),
    "cream": ("قشدة", "Cream", "ألبان"),
    "butter": ("زبدة", "Butter", "دهون"),
    "oil": ("زيت نباتي", "Vegetable Oil", "زيوت"),
    "cocoa": ("كاكاو", "Cocoa", "كاكاو"),
    "fruit": ("مركز فواكه", "Fruit Concentrate", "فواكه"),
    "tomato": ("طماطم", "Tomato", "خضار"),
    "potato": ("بطاطس", "Potato", "خضار"),
    "corn": ("ذرة", "Corn", "حبوب"),
    "coffee": ("قهوة", "Coffee", "مشروبات ساخنة"),
    "tea": ("شاي", "Tea", "مشروبات ساخنة"),
    "honey": ("عسل", "Honey", "محليات"),
    "rice": ("أرز", "Rice", "حبوب"),
    "durum": ("سميد القمح الصلب", "Durum Wheat Semolina", "حبوب"),
    "spices": ("بهارات", "Spices", "توابل"),
    "yeast": ("خميرة", "Yeast", "مخبوزات"),
    "oats": ("شوفان", "Oats", "حبوب"),
    "dates": ("تمر", "Dates", "فواكه"),
    "meat": ("لحم", "Meat", "لحوم"),
    "chicken": ("دجاج", "Chicken", "لحوم"),
    "fish": ("سمك", "Fish", "أسماك"),
    "starch": ("نشا", "Starch", "حبوب"),
    "glucose": ("شراب الجلوكوز", "Glucose Syrup", "محليات"),
    "legumes": ("بقوليات", "Legumes", "حبوب"),
    "egg": ("بيض", "Egg", "مكونات أساسية"),
    "caffeine": ("كافيين", "Caffeine", "منبهات"),
}

# Existing regulated additives reused as-is. Missing ones are created once.
ADDITIVES = {
    "E330": ("حمض الستريك", "Citric Acid", "أحماض ومنظمات حموضة", Ingredient.RiskLevel.LOW, Ingredient.SafetyStatus.APPROVED),
    "E322": ("ليسيثين", "Lecithins", "مستحلبات", Ingredient.RiskLevel.LOW, Ingredient.SafetyStatus.APPROVED),
    "E471": (
        "أحادي وثنائي الجليسريدات",
        "Mono- and Diglycerides of Fatty Acids",
        "مستحلبات",
        Ingredient.RiskLevel.MEDIUM,
        Ingredient.SafetyStatus.RESTRICTED,
    ),
}

CATEGORY_PROFILES = {
    "مياه": ["water"],
    "عصائر ومشروبات فواكه": ["water", "fruit", "sugar", "E330"],
    "مشروبات غازية": ["water", "sugar", "E330"],
    "مشروبات أخرى": ["water", "sugar"],
    "مشروبات طاقة": ["water", "sugar", "caffeine", "E330"],
    "حليب": ["milk"],
    "ألبان وزبادي": ["milk", "yogurt"],
    "أجبان": ["milk", "salt"],
    "بسكويت وكيك وويفر": ["flour", "sugar", "palm", "E471", "E322"],
    "شوكولاتة": ["sugar", "cocoa", "milk", "E322", "E471"],
    "شيبس ومقرمشات": ["potato", "palm", "salt"],
    "صلصات وكاتشب ومايونيز": ["tomato", "oil", "salt", "sugar", "E330", "E471"],
    "مربى وعسل وأطعمة للدهن": ["fruit", "sugar", "E330"],
    "معلبات": ["tomato", "water", "salt"],
    "حلويات وعلكة": ["sugar", "glucose", "E330"],
    "حلويات ومستلزمات تحلية": ["sugar", "starch"],
    "معكرونة وكسكسي ونودلز": ["durum", "water"],
    "قهوة وشاي ومشروبات ساخنة": ["coffee", "sugar"],
    "مستلزمات الخبز والحلويات": ["flour", "sugar", "yeast"],
    "أغذية وحليب أطفال": ["milk_powder"],
    "مثلجات ومجمدات": ["milk", "sugar", "cream", "E471", "E322"],
    "زيوت وسمن وزبدة": ["oil"],
    "خبز وتوست ومخبوزات": ["flour", "water", "yeast", "salt"],
    "حبوب الإفطار والشوفان": ["oats", "sugar"],
    "بهارات وملح ومرق": ["spices", "salt"],
    "لحوم ودواجن وأسماك": ["meat", "salt"],
    "دقيق وحبوب وبقوليات": ["flour", "legumes"],
    "تمور وفواكه ومكسرات": ["dates"],
    "سكر ومحليات": ["sugar"],
    "وجبات خفيفة": ["flour", "palm", "salt"],
    "أرز": ["rice"],
}


def _text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "nan"}:
        return ""
    return text


def _barcode(value) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int):
        return str(value)
    text = _text(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _clip(value: str, limit: int) -> str:
    return (value or "")[:limit]


class Command(BaseCommand):
    help = "Import products-barcodes.xlsx and attach category food composition"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="",
            help="Path to products-barcodes.xlsx (defaults to the project file)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["file"]) if options["file"] else Path(settings.BASE_DIR) / "products-barcodes.xlsx"
        if not path.exists():
            raise CommandError(f"ملف المنتجات غير موجود: {path}")

        try:
            import openpyxl
        except ImportError as exc:
            raise CommandError("openpyxl غير مثبّت") from exc

        workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
        popular = self._read_popular(workbook["الأكثر شهرة"])
        named = self._read_named(workbook["المنتجات"])
        workbook.close()

        ingredients = self._ingredients()
        created = updated = linked = skipped = 0

        for barcode in sorted(set(popular) | set(named)):
            row = self._merge(barcode, popular.get(barcode), named.get(barcode))
            if not row:
                skipped += 1
                continue
            product, was_created = self._upsert(row)
            created += int(was_created)
            updated += int(not was_created)
            keys = self._composition_keys(row)
            linked += self._link(product, keys, ingredients)

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalog import done. created={created} updated={updated} "
                f"ingredient_links={linked} skipped={skipped}"
            )
        )

    def _read_popular(self, worksheet):
        rows = {}
        for index, row in enumerate(worksheet.iter_rows(values_only=True)):
            if index == 0:
                continue
            barcode = _barcode(row[1] if len(row) > 1 else None)
            if not barcode:
                continue
            rows[barcode] = {
                "name_en": _text(row[2] if len(row) > 2 else None),
                "name_ar": _text(row[3] if len(row) > 3 else None),
                "brand": _text(row[4] if len(row) > 4 else None),
                "size": _text(row[5] if len(row) > 5 else None),
                "category": _text(row[6] if len(row) > 6 else None),
                "country": _text(row[7] if len(row) > 7 else None),
                "barcode_type": "",
            }
        return rows

    def _read_named(self, worksheet):
        rows = {}
        for index, row in enumerate(worksheet.iter_rows(values_only=True)):
            if index == 0:
                continue
            barcode = _barcode(row[1] if len(row) > 1 else None)
            if not barcode:
                continue
            rows[barcode] = {
                "name_ar": _text(row[2] if len(row) > 2 else None),
                "name_en": _text(row[3] if len(row) > 3 else None),
                "brand": _text(row[4] if len(row) > 4 else None),
                "size": _text(row[5] if len(row) > 5 else None),
                "category": _text(row[6] if len(row) > 6 else None),
                "country": _text(row[7] if len(row) > 7 else None),
                "barcode_type": _text(row[8] if len(row) > 8 else None),
            }
        return rows

    def _merge(self, barcode, popular, named):
        popular = popular or {}
        named = named or {}
        name_ar = popular.get("name_ar") or named.get("name_ar") or popular.get("name_en") or named.get("name_en")
        name_en = popular.get("name_en") or named.get("name_en") or ""
        if not name_ar:
            return None
        if name_en == name_ar:
            name_en = named.get("name_en") or ""
            if name_en == name_ar:
                name_en = ""
        return {
            "barcode": barcode,
            "name_ar": _clip(name_ar, 255),
            "name_en": _clip(name_en, 255),
            "brand": _clip(popular.get("brand") or named.get("brand") or "", 150),
            "size": _clip(popular.get("size") or named.get("size") or "", 80),
            "category": _clip(popular.get("category") or named.get("category") or "", 100),
            "country": _clip(popular.get("country") or named.get("country") or "", 100),
            "barcode_type": _clip(named.get("barcode_type") or popular.get("barcode_type") or "", 20),
        }

    def _upsert(self, row):
        brand = None
        if row["brand"]:
            brand, _ = Brand.objects.get_or_create(
                name_ar=row["brand"],
                defaults={"country_of_origin": row["country"]},
            )
        product, created = Product.objects.update_or_create(
            barcode=row["barcode"],
            defaults={
                "name_ar": row["name_ar"],
                "name_en": row["name_en"],
                "brand": brand,
                "country_of_origin": row["country"],
                "manufacturer": row["brand"],
                "category": row["category"],
                "net_content": row["size"],
                "barcode_type": row["barcode_type"],
            },
        )
        return product, created

    def _ingredients(self):
        mapping = {}
        for key, (ar, en, cat, risk, status) in ADDITIVES.items():
            reason = (
                "قيد الاستخدام وفق قاعدة البيانات المرجعية"
                if status != Ingredient.SafetyStatus.APPROVED
                else "معتمد في قاعدة البيانات"
            )
            ingredient = Ingredient.objects.filter(e_number=key).first()
            if ingredient is None:
                ingredient = Ingredient.objects.create(
                    e_number=key,
                    name_ar=ar,
                    name_en=en,
                    category=cat,
                    risk_level=risk,
                    safety_status=status,
                    reason=reason,
                    regulatory_status="معتمد" if status == Ingredient.SafetyStatus.APPROVED else "مقيد",
                    source="Food Ingredients Database",
                )
            self._alias(ingredient, ar, en, key)
            mapping[key] = ingredient

        for key, (ar, en, cat) in COMPONENTS.items():
            ingredient = Ingredient.objects.filter(name_en__iexact=en).first()
            if ingredient is None:
                ingredient = Ingredient.objects.filter(name_ar=ar, e_number__isnull=True).first()
            if ingredient is None:
                status = Ingredient.SafetyStatus.UNDER_REVIEW if key == "caffeine" else Ingredient.SafetyStatus.APPROVED
                risk = Ingredient.RiskLevel.MEDIUM if key == "caffeine" else Ingredient.RiskLevel.LOW
                reason = (
                    "الكافيين في مشروبات الطاقة يحتاج مراجعة الكمية، ولا يُعد محظورًا تلقائيًا."
                    if key == "caffeine"
                    else BASIC_REASON
                )
                ingredient = Ingredient.objects.create(
                    name_ar=ar,
                    name_en=en,
                    e_number=None,
                    category=cat,
                    risk_level=risk,
                    safety_status=status,
                    reason=reason,
                    regulatory_status="قيد المراجعة" if key == "caffeine" else "مكوّن أساسي",
                    source=SOURCE,
                )
            self._alias(ingredient, ar, en, "")
            mapping[key] = ingredient
        return mapping

    def _alias(self, ingredient, name_ar, name_en, e_number):
        if name_ar:
            IngredientAlias.objects.get_or_create(ingredient=ingredient, alias=name_ar, language="ar")
        if name_en:
            IngredientAlias.objects.get_or_create(ingredient=ingredient, alias=name_en, language="en")
        if e_number:
            IngredientAlias.objects.get_or_create(ingredient=ingredient, alias=e_number, language="en")

    def _composition_keys(self, row):
        category = row["category"]
        if category in NON_FOOD_CATEGORIES:
            return []
        blob = f"{row['name_ar']} {row['name_en']}"
        blob_l = blob.lower()

        if category == "قهوة وشاي ومشروبات ساخنة":
            if "شاي" in blob or "tea" in blob_l:
                return ["tea"]
            if any(token in blob_l for token in ("coffee", "nescafe", "نسكاف")) or "قهوة" in blob:
                return ["coffee"]
            return ["coffee", "sugar"]
        if category == "لحوم ودواجن وأسماك":
            if "دجاج" in blob or "chicken" in blob_l:
                return ["chicken", "salt"]
            if any(token in blob for token in ("سمك", "تونة")) or any(token in blob_l for token in ("fish", "tuna")):
                return ["fish", "water", "salt"]
            return ["meat", "salt"]
        if category == "زيوت وسمن وزبدة":
            if "زبد" in blob or "butter" in blob_l:
                return ["butter"]
            return ["oil"]
        if category == "مربى وعسل وأطعمة للدهن":
            if "عسل" in blob or "honey" in blob_l:
                return ["honey"]
            return ["fruit", "sugar", "E330"]
        if category == "شيبس ومقرمشات" and ("ذرة" in blob or "corn" in blob_l):
            return ["corn", "palm", "salt"]
        if category == "معلبات" and (
            any(token in blob for token in ("تونة", "سمك")) or any(token in blob_l for token in ("tuna", "fish"))
        ):
            return ["fish", "water", "salt"]
        if category == "أغذية وحليب أطفال" and "حليب" not in blob and "milk" not in blob_l:
            return ["milk_powder", "oats"]
        if category == "صلصات وكاتشب ومايونيز" and ("مايونيز" in blob or "mayo" in blob_l):
            return ["egg", "oil", "salt", "E471"]
        return list(CATEGORY_PROFILES.get(category, []))

    def _link(self, product, keys, ingredients):
        product.product_ingredients.all().delete()
        seen = set()
        position = 0
        for key in keys:
            ingredient = ingredients.get(key)
            if ingredient is None or ingredient.id in seen:
                continue
            seen.add(ingredient.id)
            position += 1
            ProductIngredient.objects.create(
                product=product,
                ingredient=ingredient,
                position_in_list=position,
                source=ProductIngredient.Source.MANUAL,
            )
        return position
