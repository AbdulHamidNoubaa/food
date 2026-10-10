import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.test import Client
from apps.ingredients.models import Ingredient

c = Client()

# visitor cannot manage
assert c.login(username="user", password="user123")
r = c.get("/ingredients/banned/add/")
assert r.status_code == 302
c.logout()

# inspector can add
assert c.login(username="inspector", password="inspector123")
r = c.get("/ingredients/banned/")
assert r.status_code == 200
r = c.get("/ingredients/banned/add/")
assert r.status_code == 200
r = c.post(
    "/ingredients/banned/add/",
    {
        "name_ar": "مادة اختبار محظورة",
        "name_en": "Test Banned Substance",
        "e_number": "E999",
        "category": "اختبار",
        "reason": "محظورة لأغراض الاختبار",
        "source": "مرجع اختبار",
        "notes": "",
        "safety_status": "PROHIBITED",
        "risk_level": "HIGH",
        "image_url": "",
    },
)
assert r.status_code == 302, r.status_code
ing = Ingredient.objects.get(e_number="E999")
assert ing.image.name == "" or ing.image.name is None or not ing.image
assert ing.created_by.username == "inspector"

from apps.audit.models import AuditLog

assert AuditLog.objects.filter(action="ingredient.create", entity_id=str(ing.id)).exists()
print("BANNED_MGMT_PASS")
