from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.products.models import Product


@login_required
def product_list(request):
    if request.user.role == "USER":
        return redirect("scans:search")
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    qs = Product.objects.select_related("brand").annotate(
        ingredient_count=Count("product_ingredients", distinct=True),
        scan_count=Count("scans", distinct=True),
    )
    if q:
        qs = qs.filter(
            Q(name_ar__icontains=q)
            | Q(name_en__icontains=q)
            | Q(barcode__icontains=q)
            | Q(brand__name_ar__icontains=q)
            | Q(manufacturer__icontains=q)
        )
    if category:
        qs = qs.filter(category__icontains=category)
    paginator = Paginator(qs.order_by("name_ar"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "products/list.html",
        {"page_obj": page, "q": q, "category": category},
    )


@login_required
def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related("brand").prefetch_related(
            "product_ingredients__ingredient"
        ),
        id=product_id,
    )
    return render(request, "products/detail.html", {"product": product})
