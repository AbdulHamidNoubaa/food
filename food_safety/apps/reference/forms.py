from django import forms

from apps.reference.models import LocalRegulatoryOverride, RegulatoryStatus


class LocalOverrideForm(forms.ModelForm):
    class Meta:
        model = LocalRegulatoryOverride
        fields = [
            "status",
            "reason",
            "regulatory_source",
            "reference_number",
            "notes",
            "effective_date",
            "is_active",
            "image",
        ]
        labels = {
            "status": "الحالة التنظيمية (ليبيا)",
            "reason": "السبب",
            "regulatory_source": "المصدر التنظيمي المحلي",
            "reference_number": "رقم المرجع",
            "notes": "ملاحظات",
            "effective_date": "تاريخ النفاذ",
            "is_active": "نشط",
            "image": "صورة (اختياري)",
        }
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "effective_date": forms.DateInput(attrs={"type": "date"}),
            "regulatory_source": forms.TextInput(
                attrs={"placeholder": "مثال: المواصفة القياسية الليبية 15/2025"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = RegulatoryStatus.choices
        self.fields["image"].required = False
        self.fields["notes"].required = False
        self.fields["reference_number"].required = False
