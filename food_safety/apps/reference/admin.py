from django.contrib import admin

from apps.reference.models import (
    LocalRegulatoryOverride,
    ReferenceAdditive,
    ReferenceSource,
    ReferenceStatusRecord,
    ReferenceSyncLog,
    ReferenceSynonym,
)


class SynonymInline(admin.TabularInline):
    model = ReferenceSynonym
    extra = 1


class StatusInline(admin.TabularInline):
    model = ReferenceStatusRecord
    extra = 0


class OverrideInline(admin.TabularInline):
    model = LocalRegulatoryOverride
    extra = 0
    fk_name = "reference_additive"


@admin.register(ReferenceSource)
class ReferenceSourceAdmin(admin.ModelAdmin):
    list_display = ("code", "name_en", "name_ar", "is_active")
    search_fields = ("code", "name_en", "name_ar")


@admin.register(ReferenceAdditive)
class ReferenceAdditiveAdmin(admin.ModelAdmin):
    list_display = ("e_number", "ins_number", "name_en", "name_ar", "cas_number", "functional_class", "is_active")
    search_fields = ("e_number", "ins_number", "cas_number", "name_en", "name_ar")
    list_filter = ("functional_class", "is_active", "primary_source")
    inlines = [SynonymInline, StatusInline, OverrideInline]


@admin.register(LocalRegulatoryOverride)
class LocalRegulatoryOverrideAdmin(admin.ModelAdmin):
    list_display = ("reference_additive", "jurisdiction", "status", "is_active", "updated_at")
    list_filter = ("jurisdiction", "status", "is_active")


@admin.register(ReferenceSyncLog)
class ReferenceSyncLogAdmin(admin.ModelAdmin):
    list_display = ("action", "source", "started_at", "records_created", "records_updated", "success")
    readonly_fields = [f.name for f in ReferenceSyncLog._meta.fields]


admin.site.register(ReferenceSynonym)
admin.site.register(ReferenceStatusRecord)
