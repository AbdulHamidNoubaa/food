import uuid

from django.db import models


class Brand(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150, blank=True)
    country_of_origin = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name_ar"]

    def __str__(self):
        return self.name_ar or self.name_en


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    barcode = models.CharField(max_length=50, unique=True, db_index=True)
    name_ar = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255, blank=True)
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    country_of_origin = models.CharField(max_length=100, blank=True)
    manufacturer = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    expiry_date = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name_ar"]

    def __str__(self):
        return f"{self.name_ar} ({self.barcode})"


class ProductIngredient(models.Model):
    class Source(models.TextChoices):
        MANUAL = "MANUAL", "يدوي"
        OCR = "OCR", "OCR"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_ingredients")
    ingredient = models.ForeignKey(
        "ingredients.Ingredient", on_delete=models.CASCADE, related_name="product_links"
    )
    position_in_list = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)

    class Meta:
        ordering = ["position_in_list"]
        unique_together = [("product", "ingredient")]
