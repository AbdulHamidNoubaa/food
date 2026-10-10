import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from apps.products.models import Product
from apps.safety.engine import assess_product

expected = {
    "6223000000001": "WARNING",
    "6223000000002": "UNSAFE",
    "6223000000003": "SAFE",
}
ok = True
for code, want in expected.items():
    got = assess_product(Product.objects.get(barcode=code))["product_status"]
    print(f"{code} => {got} (expected {want})")
    if got != want:
        ok = False
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
