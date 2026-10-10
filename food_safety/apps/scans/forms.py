from django import forms

from apps.stores.models import selectable_stores_qs


class BarcodeScanForm(forms.Form):
    barcode = forms.CharField(label="الباركود", max_length=50)
    store = forms.ModelChoiceField(
        label="المنشأة (اختياري)", queryset=selectable_stores_qs(), required=False
    )
    location_consent = forms.BooleanField(
        label="أوافق على تسجيل الموقع الجغرافي لهذا الفحص",
        required=False,
    )
    latitude = forms.FloatField(required=False, widget=forms.HiddenInput)
    longitude = forms.FloatField(required=False, widget=forms.HiddenInput)


class ProductSearchForm(forms.Form):
    q = forms.CharField(label="بحث عن منتج / مكوّن / E-number", max_length=200)


class ImageScanForm(forms.Form):
    image = forms.ImageField(label="صورة قائمة المكونات")
    location_consent = forms.BooleanField(
        label="أوافق على تسجيل الموقع الجغرافي",
        required=False,
    )
    latitude = forms.FloatField(required=False, widget=forms.HiddenInput)
    longitude = forms.FloatField(required=False, widget=forms.HiddenInput)
    store = forms.ModelChoiceField(
        label="المنشأة (اختياري)", queryset=selectable_stores_qs(), required=False
    )


class ManualIngredientsForm(forms.Form):
    ingredients_text = forms.CharField(
        label="قائمة المكونات (افصل بفاصلة)",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Sugar, E471, Citric Acid, E330"}),
    )
    product_name = forms.CharField(label="اسم المنتج (اختياري)", required=False, max_length=255)
    location_consent = forms.BooleanField(required=False, label="موافقة الموقع")
    latitude = forms.FloatField(required=False, widget=forms.HiddenInput)
    longitude = forms.FloatField(required=False, widget=forms.HiddenInput)
