from django.urls import path

from apps.scans import views

app_name = "scans"

urlpatterns = [
    path("", views.scan_hub, name="hub"),
    path("barcode/", views.scan_barcode, name="barcode"),
    path("search/", views.search_product, name="search"),
    path("image/", views.scan_image, name="image"),
    path("manual/", views.scan_manual, name="manual"),
    path("product/<uuid:product_id>/check/", views.check_product, name="check_product"),
    path("<uuid:scan_id>/result/", views.scan_result, name="result"),
    path("<uuid:scan_id>/confirm-ocr/", views.confirm_ocr, name="confirm_ocr"),
    path("mine/", views.my_scans, name="my_scans"),
]
