from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.models import Role, User
from apps.audit.middleware import log_action
from apps.complaints.forms import ComplaintForm, ComplaintStatusForm
from apps.complaints.models import Complaint, ComplaintAttachment, ComplaintStatusHistory
from apps.complaints.severity import compute_severity
from apps.notifications.services import notify
from apps.scans.models import ProductScan, SafetyAssessment
from apps.stores.models import MunicipalAuthority, Store


def _find_authority(lat, lng, city=""):
    if lat is not None and lng is not None:
        for auth in MunicipalAuthority.objects.all():
            if auth.covers(lat, lng):
                return auth
    if city:
        return MunicipalAuthority.objects.filter(city__iexact=city).first()
    return MunicipalAuthority.objects.first()


def _create_store_from_complaint(form, user) -> Store:
    cd = form.cleaned_data
    store = Store(
        name=cd["new_name"].strip(),
        establishment_type=cd["new_type"],
        custom_type=(cd.get("new_type_other") or "").strip(),
        city=(cd.get("new_city") or "").strip(),
        district=(cd.get("new_district") or "").strip(),
        street=(cd.get("new_street") or "").strip(),
        location_description=(cd.get("new_location_description") or "").strip(),
        latitude=cd.get("store_latitude"),
        longitude=cd.get("store_longitude"),
        status=Store.Status.NEW,
        created_by=user,
        updated_by=user,
    )
    store.save()
    return store


@login_required
@require_http_methods(["GET", "POST"])
def create_complaint(request, scan_id):
    """الإبلاغ يتطلب تسجيل دخول. المنشأة تُختار أو تُنشأ ديناميكيًا مع البلاغ."""
    scan = get_object_or_404(
        ProductScan.objects.select_related("assessment", "product", "store"), id=scan_id
    )
    guest_ids = request.session.get("guest_scan_ids", [])
    owns_scan = scan.user_id == request.user.id
    guest_scan = scan.user_id is None and str(scan.id) in guest_ids
    if not owns_scan and not guest_scan and not request.user.is_municipal_staff:
        return redirect("core:home")
    if guest_scan and scan.user_id is None:
        scan.user = request.user
        scan.save(update_fields=["user"])
    assessment = getattr(scan, "assessment", None)

    initial = {
        "store": scan.store_id,
        "establishment_mode": (
            ComplaintForm.MODE_EXISTING if scan.store_id else ComplaintForm.MODE_NEW
        ),
        "latitude": scan.latitude,
        "longitude": scan.longitude,
        "store_latitude": scan.latitude,
        "store_longitude": scan.longitude,
    }
    form = ComplaintForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        complaint = form.save(commit=False)
        complaint.reporter = request.user
        complaint.product = scan.product
        complaint.scan = scan
        complaint.detected_issue = assessment.summary_reason if assessment else ""
        complaint.safety_result = {
            "product_status": assessment.product_status if assessment else None,
            "results": assessment.ingredient_results if assessment else [],
        }

        created_store = None
        if form.cleaned_data["establishment_mode"] == ComplaintForm.MODE_NEW:
            created_store = _create_store_from_complaint(form, request.user)
            complaint.store = created_store
            log_action(
                request,
                action="store.create",
                entity_type="Store",
                entity_id=created_store.id,
                new_value={
                    "name": created_store.name,
                    "type": created_store.type_display,
                    "status": created_store.status,
                    "via": "complaint",
                },
            )
        else:
            complaint.store = form.cleaned_data["store"]

        store_lat = form.cleaned_data.get("store_latitude")
        store_lng = form.cleaned_data.get("store_longitude")
        if complaint.store and complaint.store.latitude is not None:
            complaint.latitude = complaint.store.latitude
            complaint.longitude = complaint.store.longitude
        elif store_lat is not None:
            complaint.latitude = store_lat
            complaint.longitude = store_lng
        elif form.cleaned_data.get("location_consent") and complaint.latitude is None:
            complaint.latitude = scan.latitude
            complaint.longitude = scan.longitude

        if complaint.store_id and not scan.store_id:
            scan.store = complaint.store
            scan.save(update_fields=["store"])

        prohibited = 0
        if assessment:
            prohibited = sum(
                1
                for r in assessment.ingredient_results
                if r.get("safety_status") == SafetyAssessment.ProductStatus.UNSAFE
            )
        prior = Complaint.objects.filter(product=scan.product).count() if scan.product_id else 0
        status = assessment.product_status if assessment else SafetyAssessment.ProductStatus.UNKNOWN
        score, level = compute_severity(status, prohibited, False, prior)
        complaint.severity_score = score
        complaint.severity_level = level

        city = complaint.store.city if complaint.store else ""
        complaint.assigned_authority = _find_authority(
            complaint.latitude, complaint.longitude, city
        )
        complaint.save()

        ComplaintStatusHistory.objects.create(
            complaint=complaint,
            old_status="",
            new_status=Complaint.Status.NEW,
            changed_by=request.user,
            notes="إنشاء البلاغ" + (" مع منشأة جديدة" if created_store else ""),
        )

        attachment = form.cleaned_data.get("attachment")
        if attachment:
            ComplaintAttachment.objects.create(
                complaint=complaint,
                file=attachment,
                file_type=ComplaintAttachment.FileType.IMAGE,
            )

        officers = User.objects.filter(
            role__in=[Role.MUNICIPAL_OFFICER, Role.ADMIN, Role.INSPECTOR],
            is_active=True,
        )
        for officer in officers:
            notify(
                officer,
                type="complaint_new",
                title=f"بلاغ جديد ({complaint.severity_level})",
                body=complaint.detected_issue[:200],
                entity_type="Complaint",
                entity_id=complaint.id,
            )

        log_action(
            request,
            action="complaint.create",
            entity_type="Complaint",
            entity_id=complaint.id,
            new_value={
                "severity": level,
                "status": complaint.status,
                "store_id": str(complaint.store_id) if complaint.store_id else None,
            },
        )
        notify(
            request.user,
            type="complaint_submitted",
            title="تم استلام بلاغك",
            body="سيتم مراجعته من الجهة الرقابية.",
            entity_type="Complaint",
            entity_id=complaint.id,
        )
        return redirect("complaints:detail", complaint_id=complaint.id)

    return render(
        request,
        "complaints/create.html",
        {
            "form": form,
            "scan": scan,
            "assessment": assessment,
            "duplicate_candidates": getattr(form, "duplicate_candidates", []),
            "type_choices": Store.EstablishmentType.choices,
        },
    )


@login_required
def my_complaints(request):
    items = Complaint.objects.filter(reporter=request.user).select_related("product", "store")
    return render(request, "complaints/mine.html", {"complaints": items})


@login_required
def all_complaints(request):
    if not request.user.can_manage_complaints and request.user.role not in {
        Role.ADMIN,
        Role.FOOD_SAFETY_SPECIALIST,
        Role.MUNICIPAL_OFFICER,
        Role.INSPECTOR,
    }:
        return redirect("complaints:mine")

    qs = Complaint.objects.select_related(
        "product", "store", "reporter", "assigned_inspector"
    )
    if request.user.role == Role.INSPECTOR:
        qs = qs.filter(Q(assigned_inspector=request.user) | Q(status=Complaint.Status.NEW))

    status = request.GET.get("status", "").strip()
    severity = request.GET.get("severity", "").strip()
    q = request.GET.get("q", "").strip()
    if status:
        qs = qs.filter(status=status)
    if severity:
        qs = qs.filter(severity_level=severity)
    if q:
        qs = qs.filter(
            Q(product__name_ar__icontains=q)
            | Q(store__name__icontains=q)
            | Q(detected_issue__icontains=q)
            | Q(description__icontains=q)
        )

    page = Paginator(qs.order_by("-created_at"), 20).get_page(request.GET.get("page"))
    return render(
        request,
        "complaints/all.html",
        {
            "page_obj": page,
            "filters": {"status": status, "severity": severity, "q": q},
            "status_choices": Complaint.Status.choices,
            "severity_choices": Complaint.Severity.choices,
        },
    )


@login_required
def complaint_detail(request, complaint_id):
    complaint = get_object_or_404(
        Complaint.objects.select_related(
            "product", "store", "reporter", "assigned_inspector", "assigned_authority", "scan"
        ).prefetch_related("attachments", "history"),
        id=complaint_id,
    )
    is_owner = complaint.reporter_id == request.user.id
    if not is_owner and not request.user.can_manage_complaints:
        return redirect("core:home")

    status_form = None
    if request.user.can_manage_complaints:
        inspectors = User.objects.filter(role=Role.INSPECTOR, is_active=True)
        status_form = ComplaintStatusForm(
            inspectors=inspectors,
            initial={
                "status": complaint.status,
                "assigned_inspector": complaint.assigned_inspector_id,
            },
        )

    return render(
        request,
        "complaints/detail.html",
        {"complaint": complaint, "status_form": status_form, "is_owner": is_owner},
    )


@login_required
@require_http_methods(["POST"])
def update_complaint_status(request, complaint_id):
    if not request.user.can_manage_complaints:
        return redirect("core:home")
    complaint = get_object_or_404(Complaint, id=complaint_id)
    inspectors = User.objects.filter(role=Role.INSPECTOR, is_active=True)
    form = ComplaintStatusForm(request.POST, inspectors=inspectors)
    if form.is_valid():
        old = complaint.status
        new = form.cleaned_data["status"]
        complaint.status = new
        inspector = form.cleaned_data.get("assigned_inspector")
        if inspector:
            complaint.assigned_inspector = inspector
            if new == Complaint.Status.NEW:
                complaint.status = Complaint.Status.ASSIGNED
                new = complaint.status
        complaint.save()
        ComplaintStatusHistory.objects.create(
            complaint=complaint,
            old_status=old,
            new_status=new,
            changed_by=request.user,
            notes=form.cleaned_data.get("notes") or "",
        )
        log_action(
            request,
            action="complaint.status_change",
            entity_type="Complaint",
            entity_id=complaint.id,
            old_value={"status": old},
            new_value={"status": new},
        )
        notify(
            complaint.reporter,
            type="complaint_update",
            title=f"تحديث بلاغك: {complaint.get_status_display()}",
            body=form.cleaned_data.get("notes") or "",
            entity_type="Complaint",
            entity_id=complaint.id,
        )
        if inspector:
            notify(
                inspector,
                type="complaint_assigned",
                title="تم تعيين بلاغ لك",
                body=str(complaint.id),
                entity_type="Complaint",
                entity_id=complaint.id,
            )
    return redirect("complaints:detail", complaint_id=complaint.id)
