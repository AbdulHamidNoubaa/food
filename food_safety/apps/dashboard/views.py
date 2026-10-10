import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.models import Role
from apps.complaints.models import Complaint
from apps.ingredients.models import Ingredient, UnmatchedQuery
from apps.scans.models import ProductScan, SafetyAssessment
from apps.stores.models import Store, selectable_stores_qs


def staff_required(view):
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_municipal_staff:
            return redirect("core:home")
        return view(request, *args, **kwargs)

    return _wrapped


def _assessment_stats():
    qs = SafetyAssessment.objects.all()
    return {
        "total_checks": qs.count(),
        "safe": qs.filter(product_status=SafetyAssessment.ProductStatus.SAFE).count(),
        "warning": qs.filter(product_status=SafetyAssessment.ProductStatus.WARNING).count(),
        "unsafe": qs.filter(product_status=SafetyAssessment.ProductStatus.UNSAFE).count(),
        "unknown": qs.filter(
            product_status__in=[
                SafetyAssessment.ProductStatus.UNKNOWN,
                SafetyAssessment.ProductStatus.PENDING,
            ]
        ).count(),
    }


def _checks_timeline(days=14):
    since = timezone.now() - timedelta(days=days)
    rows = (
        ProductScan.objects.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )
    labels = []
    values = []
    for row in rows:
        labels.append(row["day"].isoformat() if row["day"] else "")
        values.append(row["total"])
    return {"labels": labels, "values": values}


def _top_prohibited(limit=8):
    # Count mentions of prohibited e-numbers inside assessment JSON is heavy;
    # show prohibited ingredients ordered by category as regulatory list highlight,
    # plus appearance count approximated via product_links.
    items = (
        Ingredient.objects.filter(safety_status=Ingredient.SafetyStatus.PROHIBITED)
        .annotate(usage=Count("product_links"))
        .order_by("-usage", "e_number")[:limit]
    )
    return {
        "labels": [i.e_number or i.name_ar for i in items],
        "values": [i.usage for i in items],
        "names": [i.name_ar for i in items],
    }


@staff_required
def municipal_home(request):
    qs = Complaint.objects.all()
    if request.user.role == Role.INSPECTOR:
        qs = qs.filter(Q(assigned_inspector=request.user) | Q(status=Complaint.Status.NEW))

    assess = _assessment_stats()
    stats = {
        **assess,
        "open_reports": qs.exclude(
            status__in=[Complaint.Status.CLOSED, Complaint.Status.REJECTED]
        ).count(),
        "inspections": qs.filter(
            status__in=[
                Complaint.Status.ASSIGNED,
                Complaint.Status.UNDER_INVESTIGATION,
            ]
        ).count(),
        "new": qs.filter(status=Complaint.Status.NEW).count(),
        "high_priority": qs.filter(
            severity_level__in=[Complaint.Severity.HIGH, Complaint.Severity.CRITICAL]
        ).count(),
        "closed": qs.filter(status=Complaint.Status.CLOSED).count(),
    }

    city = request.GET.get("city", "")
    status = request.GET.get("status", "")
    severity = request.GET.get("severity", "")
    filtered = qs.select_related("product", "store", "reporter")
    if city:
        filtered = filtered.filter(
            Q(store__city__icontains=city) | Q(assigned_authority__city__icontains=city)
        )
    if status:
        filtered = filtered.filter(status=status)
    if severity:
        filtered = filtered.filter(severity_level=severity)

    map_points = [
        {
            "id": str(c.id),
            "lat": c.latitude,
            "lng": c.longitude,
            "status": c.status,
            "severity": c.severity_level,
            "product": c.product.name_ar if c.product else "",
            "store": c.store.name if c.store else "",
            "label": (c.product.name_ar if c.product else (c.detected_issue or "")[:40]),
            "created": c.created_at.strftime("%Y-%m-%d"),
            "url": f"/complaints/{c.id}/",
        }
        for c in filtered.exclude(latitude__isnull=True).exclude(longitude__isnull=True)[:500]
    ]

    charts = {
        "status": {
            "labels": ["آمن", "تحذير", "غير آمن", "غير مكتمل"],
            "values": [stats["safe"], stats["warning"], stats["unsafe"], stats["unknown"]],
            "colors": ["#2E7D32", "#F59E0B", "#C62828", "#607D8B"],
        },
        "timeline": _checks_timeline(),
        "prohibited": _top_prohibited(),
        "complaints": {
            "labels": ["جديد", "قيد المعالجة", "موثّق", "مرفوض", "مغلق"],
            "values": [
                qs.filter(status=Complaint.Status.NEW).count(),
                qs.filter(
                    status__in=[
                        Complaint.Status.REVIEWING,
                        Complaint.Status.ASSIGNED,
                        Complaint.Status.UNDER_INVESTIGATION,
                    ]
                ).count(),
                qs.filter(status=Complaint.Status.VERIFIED).count(),
                qs.filter(status=Complaint.Status.REJECTED).count(),
                qs.filter(status=Complaint.Status.CLOSED).count(),
            ],
            "colors": ["#00796B", "#1565C0", "#2E7D32", "#C62828", "#607D8B"],
        },
    }

    return render(
        request,
        "dashboard/municipal.html",
        {
            "stats": stats,
            "complaints": filtered.order_by("-created_at")[:12],
            "map_points_json": json.dumps(map_points, ensure_ascii=False),
            "charts_json": json.dumps(charts, ensure_ascii=False),
            "filters": {"city": city, "status": status, "severity": severity},
            "status_choices": Complaint.Status.choices,
            "severity_choices": Complaint.Severity.choices,
            "unmatched_count": UnmatchedQuery.objects.filter(resolved=False).count(),
            "prohibited_count": Ingredient.objects.filter(
                safety_status=Ingredient.SafetyStatus.PROHIBITED
            ).count(),
            "store_count": selectable_stores_qs().count(),
            "role_title": request.user.get_role_display(),
        },
    )


@staff_required
def map_view(request):
    qs = Complaint.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    if request.user.role == Role.INSPECTOR:
        qs = qs.filter(Q(assigned_inspector=request.user) | Q(status=Complaint.Status.NEW))

    points = [
        {
            "id": str(c.id),
            "lat": c.latitude,
            "lng": c.longitude,
            "status": c.status,
            "severity": c.severity_level,
            "product": c.product.name_ar if c.product else "",
            "store": c.store.name if c.store else "",
            "label": c.store.name if c.store else (c.product.name_ar if c.product else "بلاغ"),
            "created": c.created_at.strftime("%Y-%m-%d"),
            "url": f"/complaints/{c.id}/",
        }
        for c in qs.select_related("product", "store")[:500]
    ]

    store_points = [
        {
            "id": str(s.id),
            "lat": s.latitude,
            "lng": s.longitude,
            "label": s.name,
            "city": s.city,
            "type": s.type_display,
            "url": f"/stores/{s.id}/",
        }
        for s in selectable_stores_qs()
        .exclude(latitude__isnull=True)
        .exclude(longitude__isnull=True)[:200]
    ]

    return render(
        request,
        "dashboard/map.html",
        {
            "map_points_json": json.dumps(points, ensure_ascii=False),
            "store_points_json": json.dumps(store_points, ensure_ascii=False),
        },
    )


@staff_required
def export_complaints_csv(request):
    import csv

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="complaints.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        ["id", "status", "severity", "product", "store", "city", "lat", "lng", "created_at"]
    )
    for c in Complaint.objects.select_related("product", "store").all():
        writer.writerow(
            [
                str(c.id),
                c.status,
                c.severity_level,
                c.product.name_ar if c.product else "",
                c.store.name if c.store else "",
                c.store.city if c.store else "",
                c.latitude,
                c.longitude,
                c.created_at.isoformat(),
            ]
        )
    return response
