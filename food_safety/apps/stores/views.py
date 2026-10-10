import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.audit.middleware import log_action
from apps.complaints.models import Complaint
from apps.stores.forms import StoreEditForm, StoreMergeForm
from apps.stores.models import (
    Store,
    find_duplicate_candidates,
    find_nearby_stores,
    selectable_stores_qs,
)


def _can_manage(user) -> bool:
    return user.is_authenticated and user.can_manage_stores


def _manager_required(view):
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not _can_manage(request.user):
            messages.error(request, "ليس لديك صلاحية لإدارة المنشآت.")
            return redirect("stores:list")
        return view(request, *args, **kwargs)

    return _wrapped


def _store_json(store: Store, distance_m=None) -> dict:
    data = {
        "id": str(store.id),
        "name": store.name,
        "type": store.type_display,
        "establishment_type": store.establishment_type,
        "city": store.city,
        "district": store.district,
        "lat": store.latitude,
        "lng": store.longitude,
        "status": store.status,
        "status_display": store.get_status_display(),
        "url": reverse("stores:detail", args=[store.id]),
    }
    if distance_m is not None:
        data["distance_m"] = round(distance_m)
    return data


@login_required
@require_GET
def store_list(request):
    q = request.GET.get("q", "").strip()
    etype = request.GET.get("type", "").strip()
    status = request.GET.get("status", "").strip()
    qs = (
        selectable_stores_qs()
        .annotate(complaint_count=Count("complaints", distinct=True))
        .order_by("-updated_at", "name")
    )
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(city__icontains=q)
            | Q(district__icontains=q)
            | Q(street__icontains=q)
            | Q(business_type__icontains=q)
            | Q(custom_type__icontains=q)
        )
    if etype:
        qs = qs.filter(establishment_type=etype)
    if status:
        qs = qs.filter(status=status)

    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "stores/list.html",
        {
            "page_obj": page,
            "q": q,
            "etype": etype,
            "status": status,
            "type_choices": Store.EstablishmentType.choices,
            "status_choices": Store.Status.choices,
            "can_manage": _can_manage(request.user),
        },
    )


@login_required
@require_GET
def store_detail(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    complaints = (
        Complaint.objects.filter(store=store)
        .select_related("product", "reporter")
        .order_by("-created_at")
    )
    last = complaints.first()
    products = []
    seen = set()
    for c in complaints:
        if c.product_id and c.product_id not in seen:
            seen.add(c.product_id)
            products.append(c.product)
    last_status = None
    if last and last.safety_result:
        last_status = last.safety_result.get("product_status")
    return render(
        request,
        "stores/detail.html",
        {
            "store": store,
            "complaints": complaints[:50],
            "complaint_count": complaints.count(),
            "last_complaint": last,
            "last_safety_status": last_status,
            "products": products[:20],
            "can_manage": _can_manage(request.user),
        },
    )


@login_required
@require_GET
def store_map(request):
    etype = request.GET.get("type", "").strip()
    qs = selectable_stores_qs().filter(latitude__isnull=False, longitude__isnull=False)
    if etype:
        qs = qs.filter(establishment_type=etype)
    qs = qs.annotate(complaint_count=Count("complaints", distinct=True))
    points = [{**_store_json(s), "complaint_count": s.complaint_count} for s in qs]
    return render(
        request,
        "stores/map.html",
        {
            "points_json": json.dumps(points, ensure_ascii=False),
            "etype": etype,
            "type_choices": Store.EstablishmentType.choices,
            "can_manage": _can_manage(request.user),
        },
    )


@_manager_required
@require_http_methods(["GET", "POST"])
def store_edit(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    old = {
        "name": store.name,
        "status": store.status,
        "latitude": store.latitude,
        "longitude": store.longitude,
        "establishment_type": store.establishment_type,
    }
    form = StoreEditForm(request.POST or None, instance=store)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        log_action(
            request,
            action="store.update",
            entity_type="Store",
            entity_id=obj.id,
            old_value=old,
            new_value={
                "name": obj.name,
                "status": obj.status,
                "latitude": obj.latitude,
                "longitude": obj.longitude,
                "establishment_type": obj.establishment_type,
            },
        )
        messages.success(request, "تم تحديث بيانات المنشأة.")
        return redirect("stores:detail", store_id=obj.id)
    return render(
        request,
        "stores/edit.html",
        {"form": form, "store": store, "page_title": f"تعديل: {store.name}"},
    )


@_manager_required
@require_http_methods(["GET", "POST"])
def store_merge(request, store_id):
    source = get_object_or_404(Store, id=store_id)
    form = StoreMergeForm(request.POST or None, source=source)
    if request.method == "POST" and form.is_valid():
        target = form.cleaned_data["target"]
        moved = Complaint.objects.filter(store=source).update(store=target)
        source.merged_into = target
        source.status = Store.Status.INACTIVE
        source.updated_by = request.user
        source.save()
        log_action(
            request,
            action="store.merge",
            entity_type="Store",
            entity_id=source.id,
            old_value={"source": str(source.id)},
            new_value={"target": str(target.id), "complaints_moved": moved},
        )
        messages.success(
            request,
            f"تم دمج المنشأة ونقل {moved} بلاغًا إلى «{target.name}».",
        )
        return redirect("stores:detail", store_id=target.id)
    return render(request, "stores/merge.html", {"form": form, "store": source})


@_manager_required
@require_POST
def store_deactivate(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    old = store.status
    store.status = Store.Status.INACTIVE
    store.updated_by = request.user
    store.save(update_fields=["status", "updated_by", "updated_at"])
    log_action(
        request,
        action="store.deactivate",
        entity_type="Store",
        entity_id=store.id,
        old_value={"status": old},
        new_value={"status": store.status},
    )
    messages.success(request, "تم تعطيل المنشأة.")
    return redirect("stores:detail", store_id=store.id)


@login_required
@require_GET
def api_search(request):
    q = request.GET.get("q", "").strip()
    qs = selectable_stores_qs()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(city__icontains=q)
            | Q(district__icontains=q)
            | Q(business_type__icontains=q)
        )
    results = [_store_json(s) for s in qs.order_by("name")[:25]]
    return JsonResponse({"results": results})


@login_required
@require_GET
def api_nearby(request):
    try:
        lat = float(request.GET.get("lat"))
        lng = float(request.GET.get("lng"))
    except (TypeError, ValueError):
        return JsonResponse({"results": [], "error": "lat/lng required"}, status=400)
    radius = float(request.GET.get("radius_m") or 2000)
    scored = find_nearby_stores(lat, lng, radius_m=radius, limit=15)
    return JsonResponse({"results": [_store_json(s, d) for s, d in scored]})


@login_required
@require_GET
def api_duplicates(request):
    name = request.GET.get("name", "").strip()
    lat = request.GET.get("lat")
    lng = request.GET.get("lng")
    try:
        lat_f = float(lat) if lat not in (None, "") else None
        lng_f = float(lng) if lng not in (None, "") else None
    except ValueError:
        lat_f = lng_f = None
    radius = float(request.GET.get("radius_m") or 50)
    hits = find_duplicate_candidates(name, lat_f, lng_f, radius_m=radius)
    return JsonResponse(
        {
            "results": [
                {
                    **_store_json(h["store"]),
                    "distance_m": h["distance_m"],
                    "name_score": h["name_score"],
                }
                for h in hits
            ]
        }
    )
