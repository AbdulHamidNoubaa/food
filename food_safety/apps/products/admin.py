from django.contrib import admin

from apps.products.models import Brand, Product, ProductIngredient


class ProductIngredientInline(admin.TabularInline):
    model = ProductIngredient
    extra = 1


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "name_en", "country_of_origin")
    search_fields = ("name_ar", "name_en")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "barcode", "brand", "category", "country_of_origin")
    search_fields = ("name_ar", "name_en", "barcode")
    list_filter = ("category", "country_of_origin")
    inlines = [ProductIngredientInline]


@admin.register(ProductIngredient)
class ProductIngredientAdmin(admin.ModelAdmin):
    list_display = ("product", "ingredient", "position_in_list", "source")
