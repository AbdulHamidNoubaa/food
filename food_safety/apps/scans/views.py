from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.products.models import Product
from apps.safety.engine import assess_ingredient_texts, assess_product
from apps.scans.forms import BarcodeScanForm, ImageScanForm, ManualIngredientsForm, ProductSearchForm
from apps.scans.models import OCRResult, ProductScan, SafetyAssessment, ScanImage
from apps.scans.ocr import extract_from_image, extract_from_manual_text
from apps.notifications.services import notify


def _save_assessment(scan, assessment_data):
    return SafetyAssessment.objects.create(
        scan=scan,
        product_status=assessment_data["product_status"],
        ingredient_results=assessment_data["results"],
        summary_reason=assessment_data["summary_reason"],
    )


def _notify_scan(user, assessment):
    if user is None or not getattr(user, "is_authenticated", False):
        return
    status_ar = dict(SafetyAssessment.ProductStatus.choices).get(assessment.product_status, "")
    notify(
        user,
        type="scan_result",
        title=f"نتيجة الفحص: {status_ar}",
        body=assessment.summary_reason[:300],
        entity_type="SafetyAssessment",
        entity_id=assessment.id,
    )


def _scan_user(request):
    if request.user.is_authenticated:
        return request.user
    return None


def _remember_guest_scan(request, scan):
    if request.user.is_authenticated:
        return
    ids = request.session.get("guest_scan_ids", [])
    sid = str(scan.id)
    if sid not in ids:
        ids.append(sid)
        request.session["guest_scan_ids"] = ids[-40:]
        request.session.modified = True


def _can_access_scan(request, scan) -> bool:
    if request.user.is_authenticated:
        if scan.user_id == request.user.id:
            return True
        if getattr(request.user, "is_municipal_staff", False):
            return True
    guest_ids = request.session.get("guest_scan_ids", [])
    return str(scan.id) in guest_ids


def scan_hub(request):
    return render(request, "scans/hub.html")


@require_http_methods(["GET", "POST"])
def scan_barcode(request):
    form = BarcodeScanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        barcode = form.cleaned_data["barcode"].strip()
        product = Product.objects.filter(barcode=barcode).prefetch_related(
            "product_ingredients__ingredient", "brand"
        ).first()
        scan = ProductScan.objects.create(
            user=_scan_user(request),
            product=product,
            scan_method=ProductScan.Method.BARCODE,
            store=form.cleaned_data.get("store"),
            latitude=form.cleaned_data.get("latitude") if form.cleaned_data.get("location_consent") else None,
            longitude=form.cleaned_data.get("longitude") if form.cleaned_data.get("location_consent") else None,
            location_consent=bool(form.cleaned_data.get("location_consent")),
            query_text=barcode,
        )
        _remember_guest_scan(request, scan)
        if not product:
            return render(
                request,
                "scans/not_found.html",
                {"barcode": barcode, "scan": scan},
            )
        data = assess_product(product)
        assessment = _save_assessment(scan, data)
        _notify_scan(_scan_user(request), assessment)
        return redirect("scans:result", scan_id=scan.id)
    return render(request, "scans/barcode.html", {"form": form})


@require_http_methods(["GET", "POST"])
def search_product(request):
    form = ProductSearchForm(request.GET or None)
    results = []
    if form.is_valid():
        q = form.cleaned_data["q"].strip()
        results = (
            Product.objects.filter(
                Q(name_ar__icontains=q)
                | Q(name_en__icontains=q)
                | Q(barcode__icontains=q)
                | Q(brand__name_ar__icontains=q)
                | Q(brand__name_en__icontains=q)
                | Q(product_ingredients__ingredient__e_number__icontains=q)
                | Q(product_ingredients__ingredient__name_ar__icontains=q)
                | Q(product_ingredients__ingredient__name_en__icontains=q)
            )
            .select_related("brand")
            .distinct()[:50]
        )
    return render(request, "scans/search.html", {"form": form, "results": results})


def check_product(request, product_id):
    product = get_object_or_404(
        Product.objects.prefetch_related("product_ingredients__ingredient", "brand"),
        id=product_id,
    )
    scan = ProductScan.objects.create(
        user=_scan_user(request),
        product=product,
        scan_method=ProductScan.Method.SEARCH,
        query_text=product.name_ar,
    )
    _remember_guest_scan(request, scan)
    data = assess_product(product)
    assessment = _save_assessment(scan, data)
    _notify_scan(_scan_user(request), assessment)
    return redirect("scans:result", scan_id=scan.id)


@require_http_methods(["GET", "POST"])
def scan_image(request):
    form = ImageScanForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        scan = ProductScan.objects.create(
            user=_scan_user(request),
            scan_method=ProductScan.Method.IMAGE,
            store=form.cleaned_data.get("store"),
            latitude=form.cleaned_data.get("latitude") if form.cleaned_data.get("location_consent") else None,
            longitude=form.cleaned_data.get("longitude") if form.cleaned_data.get("location_consent") else None,
            location_consent=bool(form.cleaned_data.get("location_consent")),
        )
        _remember_guest_scan(request, scan)
        scan_image = ScanImage.objects.create(
            scan=scan,
            image=form.cleaned_data["image"],
            image_type=ScanImage.ImageType.INGREDIENTS,
        )
        ocr_data = extract_from_image(scan_image.image)
        OCRResult.objects.create(
            scan_image=scan_image,
            raw_text=ocr_data["raw_text"],
            extracted_ingredients=ocr_data["extracted_ingredients"],
            overall_confidence=ocr_data["overall_confidence"],
            processing_time_ms=ocr_data["processing_time_ms"],
            engine_note=ocr_data["engine_note"],
        )
        if not ocr_data["extracted_ingredients"]:
            return render(
                request,
                "scans/ocr_failed.html",
                {
                    "scan": scan,
                    "message": ocr_data.get("message"),
                    "engine_note": ocr_data.get("engine_note"),
                    "form": ManualIngredientsForm(),
                },
            )

        needs = [x for x in ocr_data["extracted_ingredients"] if x.get("needs_verification")]
        if needs:
            request.session[f"ocr_pending_{scan.id}"] = ocr_data["extracted_ingredients"]
            return render(
                request,
                "scans/verify_ocr.html",
                {"scan": scan, "items": ocr_data["extracted_ingredients"]},
            )

        texts = [x["text"] for x in ocr_data["extracted_ingredients"] if not x.get("low_confidence")]
        conf_map = {x["text"]: x["confidence"] for x in ocr_data["extracted_ingredients"]}
        data = assess_ingredient_texts(texts, conf_map)
        assessment = _save_assessment(scan, data)
        _notify_scan(_scan_user(request), assessment)
        return redirect("scans:result", scan_id=scan.id)
    return render(request, "scans/image.html", {"form": form})


@require_http_methods(["POST"])
def confirm_ocr(request, scan_id):
    scan = get_object_or_404(ProductScan, id=scan_id)
    if not _can_access_scan(request, scan):
        return redirect("core:home")
    pending = request.session.get(f"ocr_pending_{scan.id}", [])
    accepted = []
    for item in pending:
        key = f"accept_{item['text']}"
        if request.POST.get(key) == "yes":
            accepted.append(item)
    if request.POST.get("action") == "retake":
        return redirect("scans:image")
    texts = [x["text"] for x in accepted]
    conf_map = {x["text"]: x["confidence"] for x in accepted}
    data = assess_ingredient_texts(texts, conf_map)
    assessment = _save_assessment(scan, data)
    _notify_scan(_scan_user(request), assessment)
    request.session.pop(f"ocr_pending_{scan.id}", None)
    return redirect("scans:result", scan_id=scan.id)


@require_http_methods(["GET", "POST"])
def scan_manual(request):
    form = ManualIngredientsForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ocr_data = extract_from_manual_text(form.cleaned_data["ingredients_text"])
        scan = ProductScan.objects.create(
            user=_scan_user(request),
            scan_method=ProductScan.Method.TEXT,
            query_text=form.cleaned_data.get("product_name") or "",
            latitude=form.cleaned_data.get("latitude") if form.cleaned_data.get("location_consent") else None,
            longitude=form.cleaned_data.get("longitude") if form.cleaned_data.get("location_consent") else None,
            location_consent=bool(form.cleaned_data.get("location_consent")),
        )
        _remember_guest_scan(request, scan)
        texts = [x["text"] for x in ocr_data["extracted_ingredients"]]
        data = assess_ingredient_texts(texts, {x["text"]: 1.0 for x in ocr_data["extracted_ingredients"]})
        assessment = _save_assessment(scan, data)
        _notify_scan(_scan_user(request), assessment)
        return redirect("scans:result", scan_id=scan.id)
    return render(request, "scans/manual.html", {"form": form})


def scan_result(request, scan_id):
    scan = get_object_or_404(
        ProductScan.objects.select_related("product", "product__brand", "store", "assessment"),
        id=scan_id,
    )
    if not _can_access_scan(request, scan):
        return redirect("core:home")
    assessment = getattr(scan, "assessment", None)
    ocr = None
    img = scan.images.first()
    if img and hasattr(img, "ocr_result"):
        ocr = img.ocr_result
    report_url = reverse("complaints:create", args=[scan.id])
    login_for_report = f"{reverse('accounts:login')}?next={report_url}"
    return render(
        request,
        "scans/result.html",
        {
            "scan": scan,
            "assessment": assessment,
            "ocr": ocr,
            "report_url": report_url,
            "login_for_report": login_for_report,
        },
    )


@login_required
def my_scans(request):
    scans = (
        ProductScan.objects.filter(user=request.user)
        .select_related("product", "assessment")
        .order_by("-created_at")[:100]
    )
    return render(request, "scans/my_scans.html", {"scans": scans})
