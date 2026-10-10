from django.contrib import admin

from apps.stores.models import MunicipalAuthority, Store


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "establishment_type",
        "city",
        "status",
        "latitude",
        "longitude",
        "created_at",
    )
    list_filter = ("status", "establishment_type", "city")
    search_fields = ("name", "license_number", "city", "district", "street")
    raw_id_fields = ("merged_into", "created_by", "updated_by")


@admin.register(MunicipalAuthority)
class MunicipalAuthorityAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "district", "contact_phone")
