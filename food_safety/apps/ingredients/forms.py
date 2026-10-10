from django import forms

from apps.ingredients.models import Ingredient
from apps.reference.models import RegulatoryStatus


class BannedIngredientForm(forms.ModelForm):
    """إدارة مادة محلية / محظورة — الصورة اختيارية ولا تؤثر على قرار الحظر."""

    synonyms = forms.CharField(
        required=False,
        label="المرادفات",
        help_text="افصل المرادفات بفاصلة",
        widget=forms.TextInput(attrs={"placeholder": "TiO2, Pigment White 6"}),
    )
    image_url = forms.URLField(
        required=False,
        widget=forms.HiddenInput(),
        help_text="رابط صورة مختارة من البحث على الإنترنت (اختياري)",
    )
    clear_image = forms.BooleanField(
        required=False,
        label="إزالة الصورة الحالية",
    )
    # When reference duplicate found: create Local Override instead of new Ingredient
    create_as_override = forms.BooleanField(required=False, widget=forms.HiddenInput())
    force_local_create = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Ingredient
        fields = [
            "name_ar",
            "name_en",
            "e_number",
            "cas_number",
            "category",
            "reason",
            "source",
            "regulatory_status",
            "notes",
            "safety_status",
            "risk_level",
            "image",
        ]
        labels = {
            "name_ar": "اسم المادة",
            "name_en": "الاسم بالإنجليزية",
            "e_number": "رقم E / INS",
            "cas_number": "CAS Number",
            "category": "نوع المادة / Functional Class",
            "reason": "سبب التصنيف / الحظر",
            "source": "المصدر التنظيمي",
            "regulatory_status": "رقم المرجع",
            "notes": "ملاحظات",
            "safety_status": "حالة المادة",
            "risk_level": "مستوى الخطورة",
            "image": "رفع صورة من الجهاز",
        }
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "name_ar": forms.TextInput(attrs={"placeholder": "مثال: ثاني أكسيد التيتانيوم"}),
            "name_en": forms.TextInput(attrs={"placeholder": "Titanium Dioxide"}),
            "e_number": forms.TextInput(attrs={"placeholder": "E171 أو INS 171"}),
            "cas_number": forms.TextInput(attrs={"placeholder": "13463-67-7"}),
            "category": forms.TextInput(attrs={"placeholder": "مثال: Colour / معادن ومبيضات"}),
            "source": forms.TextInput(attrs={"placeholder": "مثال: المواصفة القياسية الليبية 15/2025"}),
            "regulatory_status": forms.TextInput(attrs={"placeholder": "مثال: معيار 15/2025 — 1581/3"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].required = False
        self.fields["e_number"].required = False
        self.fields["cas_number"].required = False
        self.fields["notes"].required = False
        self.fields["regulatory_status"].required = False
        if not self.instance.pk:
            self.fields["safety_status"].initial = Ingredient.SafetyStatus.PROHIBITED
            self.fields["risk_level"].initial = Ingredient.RiskLevel.HIGH
        if not (self.instance.pk and self.instance.image):
            self.fields["clear_image"].widget = forms.HiddenInput()
        if self.instance.pk:
            syns = list(self.instance.aliases.exclude(alias__in=[
                self.instance.name_ar, self.instance.name_en, self.instance.e_number or ""
            ]).values_list("alias", flat=True))
            self.fields["synonyms"].initial = ", ".join(syns)


STATUS_MAP = {
    Ingredient.SafetyStatus.PROHIBITED: RegulatoryStatus.PROHIBITED,
    Ingredient.SafetyStatus.RESTRICTED: RegulatoryStatus.RESTRICTED,
    Ingredient.SafetyStatus.UNDER_REVIEW: RegulatoryStatus.UNDER_REVIEW,
    Ingredient.SafetyStatus.APPROVED: RegulatoryStatus.PERMITTED,
    Ingredient.SafetyStatus.INACTIVE: RegulatoryStatus.UNKNOWN,
}
