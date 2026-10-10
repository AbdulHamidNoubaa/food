from django.contrib import admin

from apps.ingredients.models import (
    Ingredient,
    IngredientAlias,
    IngredientClassification,
    IngredientSource,
    UnmatchedQuery,
)


class AliasInline(admin.TabularInline):
    model = IngredientAlias
    extra = 1


class SourceInline(admin.TabularInline):
    model = IngredientSource
    extra = 1


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        "e_number",
        "name_ar",
        "name_en",
        "safety_status",
        "risk_level",
        "category",
        "created_by",
        "updated_at",
    )
    list_filter = ("safety_status", "risk_level", "category")
    search_fields = ("e_number", "name_ar", "name_en")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    inlines = [AliasInline, SourceInline]


@admin.register(UnmatchedQuery)
class UnmatchedQueryAdmin(admin.ModelAdmin):
    list_display = ("query_text", "hit_count", "resolved", "updated_at")
    list_filter = ("resolved",)


admin.site.register(IngredientAlias)
admin.site.register(IngredientSource)
admin.site.register(IngredientClassification)
