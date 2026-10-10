from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.audit.middleware import log_action
from apps.reference.forms import LocalOverrideForm
from apps.reference.models import (
    LocalRegulatoryOverride,
    ReferenceAdditive,
    ReferenceSyncLog,
    RegulatoryStatus,
)
from apps.reference.services import resolve_for_reference


def _can_manage(user) -> bool:
    return user.is_authenticated and user.can_manage_ingredients


def _manager_required(view):
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not _can_manage(request.user):
            messages.error(request, "ليس لديك صلاحية لإدارة القاعدة المرجعية.")
            return redirect("reference:catalog")
        return view(request, *args, **kwargs)

    return _wrapped


@login_required
@require_GET
def catalog(request):
    q = request.GET.get("q", "").strip()
    qs = (
        ReferenceAdditive.objects.filter(is_active=True)
        .select_related("primary_source")
        .prefetch_related("synonyms", "status_records__source", "local_overrides")
    )
    if q:
        qs = qs.filter(
            Q(name_ar__icontains=q)
            | Q(name_en__icontains=q)
            | Q(e_number__icontains=q)
            | Q(ins_number__icontains=q)
            | Q(cas_number__icontains=q)
            | Q(synonyms__synonym__icontains=q)
        ).distinct()
    page = Paginator(qs.order_by("e_number", "name_en"), 25).get_page(request.GET.get("page"))
    return render(
        request,
        "reference/catalog.html",
        {
            "page_obj": page,
            "q": q,
            "can_manage": _can_manage(request.user),
            "page_heading": "قاعدة البيانات المرجعية للمضافات",
        },
    )


@login_required
@require_GET
def additive_detail(request, additive_id):
    additive = get_object_or_404(
        ReferenceAdditive.objects.select_related("primary_source").prefetch_related(
            "synonyms", "status_records__source", "local_overrides"
        ),
        id=additive_id,
    )
    effective = resolve_for_reference(additive)
    override = additive.local_overrides.filter(jurisdiction="LY", is_active=True).first()
    return render(
        request,
        "reference/detail.html",
        {
            "additive": additive,
            "effective": effective,
            "override": override,
            "can_manage": _can_manage(request.user),
            "status_choices": RegulatoryStatus.choices,
        },
    )


@_manager_required
@require_http_methods(["GET", "POST"])
def override_edit(request, additive_id):
    additive = get_object_or_404(ReferenceAdditive, id=additive_id)
    override = LocalRegulatoryOverride.objects.filter(
        reference_additive=additive, jurisdiction="LY"
    ).first()
    old = None
    if override:
        old = {
            "status": override.status,
            "reason": override.reason,
            "regulatory_source": override.regulatory_source,
            "reference_number": override.reference_number,
            "is_active": override.is_active,
        }

    form = LocalOverrideForm(request.POST or None, request.FILES or None, instance=override)
    if request.method == "GET" and override is None:
        form.initial = {
            "status": RegulatoryStatus.PROHIBITED,
            "effective_date": date.today(),
            "regulatory_source": "المواصفة القياسية الليبية",
        }

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.reference_additive = additive
        obj.jurisdiction = "LY"
        if override is None:
            obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()
        new = {
            "status": obj.status,
            "reason": obj.reason,
            "regulatory_source": obj.regulatory_source,
            "reference_number": obj.reference_number,
            "is_active": obj.is_active,
        }
        log_action(
            request,
            action="override.create" if old is None else "override.update",
            entity_type="LocalRegulatoryOverride",
            entity_id=obj.id,
            old_value=old,
            new_value=new,
        )
        messages.success(
            request,
            "تم حفظ التصنيف المحلي (Local Override) دون تكرار السجل المرجعي.",
        )
        return redirect("reference:detail", additive_id=additive.id)

    return render(
        request,
        "reference/override_form.html",
        {
            "form": form,
            "additive": additive,
            "override": override,
            "page_title": f"تصنيف ليبي: {additive}",
        },
    )


@_manager_required
@require_POST
def sync_reference(request):
    call_command("import_reference_data")
    log_action(
        request,
        action="reference.sync",
        entity_type="ReferenceSyncLog",
        entity_id="",
        new_value={"triggered_by": request.user.username},
    )
    messages.success(
        request,
        "تمت مزامنة/استيراد القاعدة المرجعية مع الحفاظ على التصنيفات المحلية.",
    )
    return redirect("reference:catalog")


@login_required
@require_GET
def sync_logs(request):
    if not _can_manage(request.user):
        return redirect("reference:catalog")
    logs = ReferenceSyncLog.objects.select_related("source", "performed_by")[:50]
    return render(request, "reference/sync_logs.html", {"logs": logs})
