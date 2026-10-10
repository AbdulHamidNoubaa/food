from django import forms

from apps.stores.models import Store


class StoreEditForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = [
            "name",
            "establishment_type",
            "custom_type",
            "city",
            "district",
            "street",
            "location_description",
            "address",
            "latitude",
            "longitude",
            "phone",
            "owner_name",
            "license_number",
            "status",
        ]
        labels = {
            "name": "اسم المنشأة",
            "establishment_type": "نوع المنشأة",
            "custom_type": "نوع مخصص (إذا اخترت أخرى)",
            "city": "المدينة",
            "district": "المنطقة",
            "street": "الشارع",
            "location_description": "وصف الموقع",
            "address": "العنوان الكامل",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "phone": "الهاتف",
            "owner_name": "اسم المالك",
            "license_number": "رقم الترخيص",
            "status": "حالة المنشأة",
        }
        widgets = {
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "location_description": forms.TextInput(),
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        etype = cleaned.get("establishment_type")
        custom = (cleaned.get("custom_type") or "").strip()
        if etype == Store.EstablishmentType.OTHER and not custom:
            self.add_error("custom_type", "أدخل نوع المنشأة عند اختيار «أخرى».")
        if cleaned.get("latitude") is None or cleaned.get("longitude") is None:
            self.add_error("latitude", "حدد موقع المنشأة على الخريطة أو عبر GPS.")
        return cleaned


class StoreMergeForm(forms.Form):
    target = forms.ModelChoiceField(
        label="دمج في المنشأة",
        queryset=Store.objects.none(),
        help_text="ستُنقل البلاغات إلى المنشأة المستهدفة وتُعطَّل المنشأة الحالية.",
    )

    def __init__(self, *args, source: Store, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].queryset = (
            Store.objects.filter(merged_into__isnull=True)
            .exclude(status=Store.Status.INACTIVE)
            .exclude(id=source.id)
            .order_by("name")
        )
