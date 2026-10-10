"""
Fetch reference images for prohibited ingredients.
Tries Openverse/Wikipedia first; falls back to a clean regulatory label card.
Usage: python manage.py fetch_banned_images [--force]
"""
from __future__ import annotations

import time
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from apps.audit.models import AuditLog
from apps.ingredients.image_search import download_image_to_field, search_material_images
from apps.ingredients.models import Ingredient

CURATED_QUERIES = {
    "E103": ["Alkanet", "Alkanna tinctoria"],
    "E107": ["Yellow 2G food dye", "Acid yellow 17"],
    "E120": ["Carmine cochineal", "Carminic acid"],
    "E121": ["Citrus Red 2", "Ponceau SX dye"],
    "E125": ["Ponceau SX", "Scarlet GN"],
    "E126": ["Ponceau 6R dye"],
    "E128": ["Red 2G dye", "Azogeranine"],
    "E130": ["Indanthrene blue RS"],
    "E131": ["Patent Blue V dye"],
    "E142": ["Green S food colour"],
    "E152": ["Carbon black pigment"],
    "E153": ["Vegetable carbon food"],
    "E154": ["Brown FK dye"],
    "E164": ["Gardenia yellow pigment", "Crocin"],
    "E165": ["Gardenia blue pigment"],
    "E166": ["Sandalwood powder"],
    "E171": ["Titanium dioxide powder", "Titanium(IV) oxide"],
    "E173": ["Aluminium powder metal"],
    "E174": ["Edible silver leaf"],
    "E175": ["Edible gold leaf"],
    "E180": ["Lithol Rubine BK"],
    "E181": ["Tannic acid", "Tannins"],
    "E182": ["Orcein orchil dye"],
}


def _queries_for(ingredient: Ingredient) -> list[str]:
    queries = []
    e = (ingredient.e_number or "").upper()
    queries.extend(CURATED_QUERIES.get(e, []))
    if ingredient.name_en:
        queries.append(ingredient.name_en)
        queries.append(f"{ingredient.name_en} food additive")
    if e:
        queries.append(e)
    seen = set()
    out = []
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(q.strip())
    return out


def _make_label_card(ingredient: Ingredient) -> ContentFile:
    """بطاقة رقابية نظيفة عند تعذر جلب صورة من الإنترنت."""
    w, h = 640, 420
    img = Image.new("RGB", (w, h), "#F8FAF9")
    draw = ImageDraw.Draw(img)
    # إطار مؤسسي
    draw.rectangle([16, 16, w - 17, h - 17], outline="#17324D", width=3)
    draw.rectangle([16, 16, w - 17, 88], fill="#17324D")
    draw.rectangle([16, h - 70, w - 17, h - 17], fill="#C62828")

    font_lg = ImageFont.load_default()
    font_md = ImageFont.load_default()

    e = ingredient.e_number or "—"
    name_en = (ingredient.name_en or "")[:42]
    name_ar = (ingredient.name_ar or "")[:42]
    category = (ingredient.category or "مادة مضافة محظورة")[:40]

    draw.text((36, 40), f"{e}  |  PROHIBITED", fill="#FFFFFF", font=font_lg)
    draw.text((36, 130), name_en or name_ar, fill="#17324D", font=font_lg)
    draw.text((36, 170), name_ar, fill="#5F6F68", font=font_md)
    draw.text((36, 220), category, fill="#00796B", font=font_md)
    draw.text((36, 270), "Food Safety Verification System", fill="#5F6F68", font=font_md)
    draw.text((36, h - 48), "مادة محظورة — مرجع رقابي", fill="#FFFFFF", font=font_md)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    hint = (ingredient.e_number or "material").replace("/", "_")
    return ContentFile(buf.read(), name=f"{hint}_label.png")


class Command(BaseCommand):
    help = "Search the internet and attach images to prohibited ingredients"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument(
            "--labels-only",
            action="store_true",
            help="Skip internet download and only generate label cards",
        )

    def handle(self, *args, **options):
        force = options["force"]
        limit = options["limit"]
        labels_only = options["labels_only"]
        qs = Ingredient.objects.filter(
            safety_status=Ingredient.SafetyStatus.PROHIBITED
        ).order_by("e_number", "name_en")
        items = [i for i in qs if force or not bool(i.image)]
        if limit:
            items = items[:limit]

        self.stdout.write(f"Processing {len(items)} prohibited ingredient(s)...")
        ok_net = 0
        ok_label = 0

        for ingredient in items:
            label = f"{ingredient.e_number or '-'} {ingredient.name_en or ingredient.name_ar}"
            attached = False
            source = "label_card"
            query_used = ""

            if not labels_only:
                for query in _queries_for(ingredient):
                    results = search_material_images(query, limit=6)
                    for result in results:
                        url = result.get("full_url") or result.get("thumb_url")
                        if not url:
                            continue
                        hint = ingredient.e_number or ingredient.name_en or "material"
                        content = download_image_to_field(url, filename_hint=str(hint))
                        if not content:
                            continue
                        if ingredient.image:
                            ingredient.image.delete(save=False)
                        ingredient.image.save(content.name, content, save=True)
                        source = result.get("source") or "internet"
                        query_used = query
                        ok_net += 1
                        attached = True
                        self.stdout.write(
                            self.style.SUCCESS(f"OK-NET  {label}  <-  {query} [{source}]")
                        )
                        break
                    if attached:
                        break
                    time.sleep(0.2)

            if not attached:
                content = _make_label_card(ingredient)
                if ingredient.image:
                    ingredient.image.delete(save=False)
                ingredient.image.save(content.name, content, save=True)
                ok_label += 1
                attached = True
                self.stdout.write(self.style.WARNING(f"OK-LABEL {label}"))

            AuditLog.objects.create(
                user=None,
                action="ingredient.image_fetch",
                entity_type="Ingredient",
                entity_id=str(ingredient.id),
                new_value={
                    "query": query_used,
                    "source": source,
                    "image": ingredient.image.name if ingredient.image else None,
                },
            )
            time.sleep(0.15)

        self.stdout.write(
            self.style.SUCCESS(f"Done. from_internet={ok_net} label_cards={ok_label}")
        )
