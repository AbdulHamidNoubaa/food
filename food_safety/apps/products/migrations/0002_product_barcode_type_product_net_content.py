from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="barcode_type",
            field=models.CharField(blank=True, max_length=20, verbose_name="نوع الباركود"),
        ),
        migrations.AddField(
            model_name="product",
            name="net_content",
            field=models.CharField(blank=True, max_length=80, verbose_name="الحجم / الوزن"),
        ),
    ]
