from django.contrib import admin

from apps.scans.models import OCRResult, ProductScan, SafetyAssessment, ScanImage


class ScanImageInline(admin.TabularInline):
    model = ScanImage
    extra = 0


@admin.register(ProductScan)
class ProductScanAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "scan_method", "product", "created_at")
    list_filter = ("scan_method",)
    inlines = [ScanImageInline]


admin.site.register(ScanImage)
admin.site.register(OCRResult)
admin.site.register(SafetyAssessment)
