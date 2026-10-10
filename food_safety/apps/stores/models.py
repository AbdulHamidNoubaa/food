import math
import re
import uuid

from django.conf import settings
from django.db import models


def normalize_store_name(name: str) -> str:
    if not name:
        return ""
    text = name.strip().lower()
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه")
    text = re.sub(r"\s+", " ", text)
    return text


class Store(models.Model):
    """
    Food establishment — created dynamically via user complaints.
    Not a static curated catalog.
    """

    class Status(models.TextChoices):
        NEW = "NEW", "جديد"
        ACTIVE = "ACTIVE", "نشط"
        UNDER_REVIEW = "UNDER_REVIEW", "قيد المراجعة"
        VERIFIED = "VERIFIED", "معتمد"
        INACTIVE = "INACTIVE", "غير نشط"

    class EstablishmentType(models.TextChoices):
        GROCERY = "GROCERY", "بقالة"
        SUPERMARKET = "SUPERMARKET", "سوبر ماركت"
        BAKERY = "BAKERY", "مخبز"
        RESTAURANT = "RESTAURANT", "مطعم"
        CAFE = "CAFE", "مقهى"
        SWEETS = "SWEETS", "محل حلويات"
        BUTCHER = "BUTCHER", "جزارة"
        FOOD_SHOP = "FOOD_SHOP", "محل مواد غذائية"
        FACTORY = "FACTORY", "مصنع أغذية"
        WAREHOUSE = "WAREHOUSE", "مستودع مواد غذائية"
        FAST_FOOD = "FAST_FOOD", "مطعم وجبات سريعة"
        JUICE = "JUICE", "محل عصائر"
        OTHER = "OTHER", "أخرى"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("اسم المنشأة", max_length=200, db_index=True)
    name_normalized = models.CharField(max_length=200, blank=True, db_index=True)
    owner_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField("العنوان", blank=True)
    city = models.CharField("المدينة", max_length=100, blank=True, db_index=True)
    district = models.CharField("المنطقة", max_length=100, blank=True)
    street = models.CharField("الشارع", max_length=200, blank=True)
    location_description = models.CharField("وصف الموقع", max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    establishment_type = models.CharField(
        "نوع المنشأة",
        max_length=32,
        choices=EstablishmentType.choices,
        blank=True,
        db_index=True,
    )
    custom_type = models.CharField(
        "نوع مخصص",
        max_length=100,
        blank=True,
        help_text="يُستخدم عند اختيار «أخرى»",
    )
    # Legacy display field kept in sync for older templates/seeds
    business_type = models.CharField(max_length=100, blank=True)
    license_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    merged_into = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_from",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stores_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stores_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["status", "establishment_type"]),
        ]

    def __str__(self):
        return self.name

    @property
    def type_display(self) -> str:
        if self.establishment_type == self.EstablishmentType.OTHER and self.custom_type:
            return self.custom_type
        if self.establishment_type:
            return self.get_establishment_type_display()
        return self.business_type or "—"

    @property
    def is_selectable(self) -> bool:
        return self.status != self.Status.INACTIVE and self.merged_into_id is None

    def save(self, *args, **kwargs):
        self.name_normalized = normalize_store_name(self.name)
        if self.establishment_type:
            if self.establishment_type == self.EstablishmentType.OTHER and self.custom_type:
                self.business_type = self.custom_type
            else:
                self.business_type = self.get_establishment_type_display()
        elif self.business_type and not self.establishment_type:
            # Map legacy free-text types when possible
            for code, label in self.EstablishmentType.choices:
                if self.business_type.strip() == label or self.business_type.lower() in label.lower():
                    self.establishment_type = code
                    break
        parts = [p for p in [self.street, self.district, self.city] if p]
        if parts and not self.address:
            self.address = "، ".join(parts)
        super().save(*args, **kwargs)


class MunicipalAuthority(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)
    min_lat = models.FloatField(null=True, blank=True)
    max_lat = models.FloatField(null=True, blank=True)
    min_lng = models.FloatField(null=True, blank=True)
    max_lng = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name

    def covers(self, lat: float, lng: float) -> bool:
        if None in (self.min_lat, self.max_lat, self.min_lng, self.max_lng, lat, lng):
            return self.city != ""
        return self.min_lat <= lat <= self.max_lat and self.min_lng <= lng <= self.max_lng


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in meters between two WGS84 points."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def selectable_stores_qs():
    return Store.objects.filter(
        merged_into__isnull=True,
    ).exclude(status=Store.Status.INACTIVE)


def find_nearby_stores(lat: float, lng: float, radius_m: float = 2000, limit: int = 20):
    """Return list of (store, distance_m) sorted by distance. SQLite-friendly."""
    # Rough bbox (~111km per degree) to narrow candidates
    deg = radius_m / 111_000.0
    qs = selectable_stores_qs().filter(
        latitude__isnull=False,
        longitude__isnull=False,
        latitude__gte=lat - deg,
        latitude__lte=lat + deg,
        longitude__gte=lng - deg,
        longitude__lte=lng + deg,
    )
    scored = []
    for store in qs:
        d = haversine_m(lat, lng, store.latitude, store.longitude)
        if d <= radius_m:
            scored.append((store, d))
    scored.sort(key=lambda x: x[1])
    return scored[:limit]


def find_duplicate_candidates(
    name: str,
    lat: float | None,
    lng: float | None,
    *,
    radius_m: float = 50,
    limit: int = 10,
):
    """Name similarity + proximity for duplicate prevention."""
    from difflib import SequenceMatcher

    norm = normalize_store_name(name)
    results = []
    qs = selectable_stores_qs()
    for store in qs[:500]:
        name_score = SequenceMatcher(None, norm, store.name_normalized or "").ratio()
        distance = None
        if (
            lat is not None
            and lng is not None
            and store.latitude is not None
            and store.longitude is not None
        ):
            distance = haversine_m(lat, lng, store.latitude, store.longitude)
        # Hit if similar name AND (close OR no coords to compare)
        close = distance is not None and distance <= radius_m
        similar = name_score >= 0.72
        if similar and (close or distance is None):
            results.append(
                {
                    "store": store,
                    "name_score": round(name_score, 3),
                    "distance_m": round(distance, 1) if distance is not None else None,
                }
            )
        elif close and name_score >= 0.45:
            results.append(
                {
                    "store": store,
                    "name_score": round(name_score, 3),
                    "distance_m": round(distance, 1),
                }
            )
    results.sort(key=lambda r: (r["distance_m"] is None, r["distance_m"] or 0, -r["name_score"]))
    return results[:limit]
