import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "ADMIN", "مدير النظام"
    USER = "USER", "زائر"
    INSPECTOR = "INSPECTOR", "مفتش"
    MUNICIPAL_OFFICER = "MUNICIPAL_OFFICER", "ضابط حرس بلدي"
    FOOD_SAFETY_SPECIALIST = "FOOD_SAFETY_SPECIALIST", "أخصائي سلامة غذاء"


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField("الاسم الكامل", max_length=150, blank=True)
    phone = models.CharField("الهاتف", max_length=20, blank=True, null=True, unique=True)
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.USER,
        db_index=True,
    )
    preferred_language = models.CharField(
        max_length=2,
        choices=[("ar", "العربية"), ("en", "English")],
        default="ar",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "مستخدم"
        verbose_name_plural = "المستخدمون"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.full_name or self.username

    @property
    def is_municipal_staff(self):
        return self.role in {
            Role.ADMIN,
            Role.INSPECTOR,
            Role.MUNICIPAL_OFFICER,
            Role.FOOD_SAFETY_SPECIALIST,
        }

    @property
    def can_manage_ingredients(self):
        """إدارة المواد المحظورة: مدير النظام أو المفتش."""
        return self.role in {Role.ADMIN, Role.INSPECTOR}

    @property
    def can_manage_complaints(self):
        return self.role in {
            Role.ADMIN,
            Role.MUNICIPAL_OFFICER,
            Role.INSPECTOR,
        }

    @property
    def can_manage_stores(self):
        """تعديل/دمج/تعطيل المنشآت: مدير النظام أو المفتش."""
        return self.role in {Role.ADMIN, Role.INSPECTOR}
