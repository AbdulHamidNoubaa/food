from django import forms

from apps.complaints.models import Complaint
from apps.stores.models import Store, find_duplicate_candidates, selectable_stores_qs


class ComplaintForm(forms.ModelForm):
    MODE_EXISTING = "existing"
    MODE_NEW = "new"

    establishment_mode = forms.ChoiceField(
        label="المنشأة الغذائية",
        choices=[
            (MODE_EXISTING, "اختيار منشأة موجودة"),
            (MODE_NEW, "إضافة منشأة جديدة"),
        ],
        initial=MODE_EXISTING,
        widget=forms.RadioSelect,
    )
    new_name = forms.CharField(label="اسم المنشأة", required=False, max_length=200)
    new_type = forms.ChoiceField(
        label="نوع المنشأة",
        required=False,
        choices=[("", "— اختر النوع —")] + list(Store.EstablishmentType.choices),
    )
    new_type_other = forms.CharField(label="نوع آخر", required=False, max_length=100)
    new_city = forms.CharField(label="المدينة", required=False, max_length=100)
    new_district = forms.CharField(label="المنطقة", required=False, max_length=100)
    new_street = forms.CharField(label="الشارع", required=False, max_length=200)
    new_location_description = forms.CharField(
        label="وصف الموقع", required=False, max_length=255
    )
    store_latitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    store_longitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    force_create_store = forms.BooleanField(required=False, widget=forms.HiddenInput())
    location_consent = forms.BooleanField(
        label="استخدم موقعي الحالي (GPS) لتحديد موقع المنشأة",
        required=False,
    )
    attachment = forms.ImageField(label="صورة دليل (اختياري)", required=False)

    class Meta:
        model = Complaint
        fields = ("store", "description", "latitude", "longitude")
        widgets = {
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "description": forms.Textarea(attrs={"rows": 4}),
            "store": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["store"].queryset = selectable_stores_qs()
        self.fields["store"].required = False
        self.fields["store"].label = "المنشأة"
        self.fields["description"].label = "وصف البلاغ"
        self.duplicate_candidates = []

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("establishment_mode") or self.MODE_EXISTING

        if mode == self.MODE_EXISTING:
            if not cleaned.get("store"):
                self.add_error("store", "اختر منشأة من القائمة أو أضف منشأة جديدة.")
            return cleaned

        name = (cleaned.get("new_name") or "").strip()
        etype = cleaned.get("new_type") or ""
        other = (cleaned.get("new_type_other") or "").strip()
        lat = cleaned.get("store_latitude")
        lng = cleaned.get("store_longitude")

        if not name:
            self.add_error("new_name", "أدخل اسم المنشأة.")
        if not etype:
            self.add_error("new_type", "اختر نوع المنشأة.")
        elif etype == Store.EstablishmentType.OTHER and not other:
            self.add_error("new_type_other", "أدخل النوع عند اختيار «أخرى».")
        if lat is None or lng is None:
            self.add_error(
                "store_latitude",
                "حدد موقع المنشأة عبر GPS أو بتحريك العلامة على الخريطة.",
            )

        if name and not cleaned.get("force_create_store"):
            dups = find_duplicate_candidates(name, lat, lng, radius_m=50)
            if dups:
                self.duplicate_candidates = dups
                raise forms.ValidationError(
                    "يبدو أن هذه المنشأة موجودة بالفعل. اختر منشأة من القائمة المقترحة أو أكّد الإنشاء."
                )
        return cleaned


class ComplaintStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Complaint.Status.choices, label="الحالة")
    notes = forms.CharField(label="ملاحظات", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    assigned_inspector = forms.ModelChoiceField(
        label="تعيين مفتش",
        queryset=None,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        inspectors = kwargs.pop("inspectors")
        super().__init__(*args, **kwargs)
        self.fields["assigned_inspector"].queryset = inspectors
