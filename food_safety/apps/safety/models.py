import uuid

from django.conf import settings
from django.db import models


class SafetyRule(models.Model):
    class ResultingStatus(models.TextChoices):
        SAFE = "SAFE", "آمن"
        WARNING = "WARNING", "تحذير"
        UNSAFE = "UNSAFE", "غير آمن"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule_name = models.CharField(max_length=150)
    condition_expression = models.JSONField(default=dict)
    resulting_status = models.CharField(max_length=20, choices=ResultingStatus.choices)
    weight = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.rule_name
