from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.audit.middleware import log_action
from apps.ingredients.forms import STATUS_MAP, BannedIngredientForm
from apps.ingredients.image_search import download_image_to_field, search_material_images
from apps.ingredients.matching import find_duplicate_candidates
from apps.ingredients.models import Ingredient, IngredientAlias, IngredientSource, UnmatchedQuery
from apps.reference.models import LocalRegulatoryOverride
from apps.reference.services import resolve_for_local_ingredient


def _can_manage(user) -> bool:
    return user.is_authenticated and user.can_manage_ingredients


def _manager_required(view):
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not _can_manage(request.user):
            messages.error(request, "ليس لديك صلاحية لإدارة المواد المحظورة.")
            return redirect("ingredients:banned")
        return view(request, *args, **kwargs)

    return _wrapped


def _snapshot(ingredient: Ingredient) -> dict:
    return {
        "name_ar": ingredient.name_ar,
        "name_en": ingredient.name_en,
        "e_number": ingredient.e_number,
        "cas_number": ingredient.cas_number,
        "category": ingredient.category,
        "reason": ingredient.reason,
        "source": ingredient.source,
        "notes": ingredient.notes,
        "safety_status": ingredient.safety_status,
        "risk_level": ingredient.risk_level,
        "data_origin": ingredient.data_origin,
        "has_image": bool(ingredient.image),
    }


def _apply_image(form: BannedIngredientForm, ingredient: Ingredient):
    if form.cleaned_data.get("clear_image") and ingredient.image:
        ingredient.image.delete(save=False)
        ingredient.image = None
    uploaded = form.cleaned_data.get("image")
    if uploaded:
        ingredient.image = uploaded
        return
    image_url = (form.cleaned_data.get("image_url") or "").strip()
    if image_url:
        hint = ingredient.e_number or ingredient.name_en or ingredient.name_ar or "material"
        content = download_image_to_field(image_url, filename_hint=hint)
        if content:
            ingredient.image.save(content.name, content, save=False)


def _ensure_aliases(ingredient: Ingredient, extra_synonyms: str = ""):
    pairs = []
    if ingredient.name_ar:
        pairs.append((ingredient.name_ar, "ar"))
    if ingredient.name_en:
        pairs.append((ingredient.name_en, "en"))
    if ingredient.e_number:
        pairs.append((ingredient.e_number, "en"))
    for part in (extra_synonyms or "").split(","):
        syn = part.strip()
        if syn:
            pairs.append((syn, "en"))
    for alias, lang in pairs:
        IngredientAlias.objects.get_or_create(
            ingredient=ingredient, alias=alias, language=lang
        )


def _create_override_from_form(request, form, reference_additive):
    status = STATUS_MAP.get(
        form.cleaned_data.get("safety_status"),
        form.cleaned_data.get("safety_status") or "PROHIBITED",
    )
    override, created = LocalRegulatoryOverride.objects.update_or_create(
        reference_additive=reference_additive,
        jurisdiction="LY",
        defaults={
            "status": status,
            "reason": form.cleaned_data.get("reason") or "",
            "regulatory_source": form.cleaned_data.get("source") or "",
            "reference_number": form.cleaned_data.get("regulatory_status") or "",
            "notes": form.cleaned_data.get("notes") or "",
            "is_active": True,
            "effective_date": date.today(),
            "updated_by": request.user,
        },
    )
    if created:
        override.created_by = request.user
        override.save(update_fields=["created_by"])
    # Keep a linked local Ingredient row for product FKs / legacy UI, no duplicate identity
    linked = reference_additive.local_ingredients.first()
    if linked is None:
        linked = Ingredient(
            name_ar=form.cleaned_data.get("name_ar") or reference_additive.name_ar,
            name_en=form.cleaned_data.get("name_en") or reference_additive.name_en,
            e_number=form.cleaned_data.get("e_number") or reference_additive.e_number,
            cas_number=form.cleaned_data.get("cas_number") or reference_additive.cas_number,
            category=form.cleaned_data.get("category") or reference_additive.functional_class,
            reason=form.cleaned_data.get("reason") or "",
            source=form.cleaned_data.get("source") or "",
            notes=form.cleaned_data.get("notes") or "",
            safety_status=form.cleaned_data.get("safety_status"),
            risk_level=form.cleaned_data.get("risk_level"),
            regulatory_status=form.cleaned_data.get("regulatory_status") or "",
            data_origin=Ingredient.DataOrigin.REFERENCE,
            reference_additive=reference_additive,
            created_by=request.user,
            updated_by=request.user,
            last_updated=date.today(),
        )
        _apply_image(form, linked)
        linked.save()
        _ensure_aliases(linked, form.cleaned_data.get("synonyms") or "")
    else:
        linked.reference_additive = reference_additive
        linked.data_origin = Ingredient.DataOrigin.REFERENCE
        linked.safety_status = form.cleaned_data.get("safety_status")
        linked.reason = form.cleaned_data.get("reason") or linked.reason
        linked.source = form.cleaned_data.get("source") or linked.source
        linked.updated_by = request.user
        linked.last_updated = date.today()
        _apply_image(form, linked)
        linked.save()

    log_action(
        request,
        action="override.create" if created else "override.update",
        entity_type="LocalRegulatoryOverride",
        entity_id=override.id,
        new_value={
            "status": override.status,
            "reference_additive_id": str(reference_additive.id),
            "e_number": reference_additive.e_number,
        },
    )
    return override, linked


@login_required
def ingredient_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    qs = Ingredient.objects.select_related("reference_additive").all()
    if q:
        qs = qs.filter(
            Q(name_ar__icontains=q)
            | Q(name_en__icontains=q)
            | Q(e_number__icontains=q)
            | Q(cas_number__icontains=q)
            | Q(aliases__alias__icontains=q)
        ).distinct()
    if status:
        qs = qs.filter(safety_status=status)
    page = Paginator(qs.order_by("e_number", "name_ar"), 25).get_page(request.GET.get("page"))
    return render(
        request,
        "ingredients/list.html",
        {
            "page_obj": page,
            "q": q,
            "status": status,
            "status_choices": Ingredient.SafetyStatus.choices,
            "page_heading": "قاعدة المكونات والمضافات",
            "can_manage": _can_manage(request.user),
        },
    )


@login_required
def banned_list(request):
    q = request.GET.get("q", "").strip()
    qs = Ingredient.objects.filter(
        safety_status__in=[
            Ingredient.SafetyStatus.PROHIBITED,
            Ingredient.SafetyStatus.UNDER_REVIEW,
            Ingredient.SafetyStatus.INACTIVE,
        ]
    ).select_related("created_by", "updated_by", "reference_additive")
    show = request.GET.get("show", "active")
    if show == "active":
        qs = qs.filter(safety_status=Ingredient.SafetyStatus.PROHIBITED)
    if q:
        qs = qs.filter(
            Q(name_ar__icontains=q)
            | Q(name_en__icontains=q)
            | Q(e_number__icontains=q)
            | Q(cas_number__icontains=q)
        )
    page = Paginator(qs.order_by("e_number"), 20).get_page(request.GET.get("page"))
    return render(
        request,
        "ingredients/banned.html",
        {
            "page_obj": page,
            "q": q,
            "show": show,
            "can_manage": _can_manage(request.user),
        },
    )


@login_required
def ingredient_detail(request, ingredient_id):
    ingredient = get_object_or_404(
        Ingredient.objects.select_related(
            "created_by", "updated_by", "reference_additive"
        ).prefetch_related("aliases", "sources", "reference_additive__status_records__source",
                           "reference_additive__local_overrides"),
        id=ingredient_id,
    )
    effective = resolve_for_local_ingredient(ingredient)
    return render(
        request,
        "ingredients/detail.html",
        {
            "ingredient": ingredient,
            "effective": effective,
            "can_manage": _can_manage(request.user),
        },
    )


@_manager_required
@require_http_methods(["GET", "POST"])
def banned_create(request):
    form = BannedIngredientForm(request.POST or None, request.FILES or None)
    duplicates = None
    if request.method == "POST" and form.is_valid():
        synonyms_raw = form.cleaned_data.get("synonyms") or ""
        synonym_list = [s.strip() for s in synonyms_raw.split(",") if s.strip()]
        duplicates = find_duplicate_candidates(
            name_ar=form.cleaned_data.get("name_ar") or "",
            name_en=form.cleaned_data.get("name_en") or "",
            e_number=form.cleaned_data.get("e_number") or "",
            cas_number=form.cleaned_data.get("cas_number") or "",
            synonyms=synonym_list,
        )
        ref_hits = duplicates.get("reference") or []
        local_hits = duplicates.get("local") or []

        if ref_hits and not form.cleaned_data.get("force_local_create"):
            if form.cleaned_data.get("create_as_override"):
                ref = ref_hits[0]
                _create_override_from_form(request, form, ref)
                messages.success(
                    request,
                    "هذه المادة موجودة في القاعدة المرجعية — تم إنشاء/تحديث تصنيف محلي (Local Override) بدل سجل مكرر.",
                )
                return redirect("reference:detail", additive_id=ref.id)
            messages.warning(
                request,
                "هذه المادة موجودة بالفعل في قاعدة البيانات المرجعية. راجع بياناتها وأنشئ تصنيفًا محليًا بدل سجل مكرر.",
            )
            return render(
                request,
                "ingredients/banned_form.html",
                {
                    "form": form,
                    "mode": "create",
                    "page_title": "إضافة مادة محظورة",
                    "duplicates": duplicates,
                    "require_override_confirm": True,
                },
            )

        if local_hits and not form.cleaned_data.get("force_local_create"):
            messages.warning(
                request,
                "توجد مادة محلية مطابقة. عدّل السجل الحالي بدل إنشاء تكرار.",
            )
            return render(
                request,
                "ingredients/banned_form.html",
                {
                    "form": form,
                    "mode": "create",
                    "page_title": "إضافة مادة محظورة",
                    "duplicates": duplicates,
                },
            )

        ingredient = form.save(commit=False)
        if not ingredient.safety_status:
            ingredient.safety_status = Ingredient.SafetyStatus.PROHIBITED
        if not ingredient.risk_level:
            ingredient.risk_level = Ingredient.RiskLevel.HIGH
        ingredient.data_origin = Ingredient.DataOrigin.LOCAL
        ingredient.created_by = request.user
        ingredient.updated_by = request.user
        ingredient.last_updated = date.today()
        _apply_image(form, ingredient)
        ingredient.save()
        _ensure_aliases(ingredient, synonyms_raw)
        if ingredient.source:
            IngredientSource.objects.get_or_create(
                ingredient=ingredient,
                source_name=ingredient.source,
                defaults={"document_reference": ingredient.regulatory_status or ingredient.source},
            )
        log_action(
            request,
            action="ingredient.create",
            entity_type="Ingredient",
            entity_id=ingredient.id,
            new_value=_snapshot(ingredient),
        )
        messages.success(request, "تمت إضافة المادة المحلية بنجاح.")
        return redirect("ingredients:detail", ingredient_id=ingredient.id)

    return render(
        request,
        "ingredients/banned_form.html",
        {"form": form, "mode": "create", "page_title": "إضافة مادة محظورة"},
    )


@_manager_required
@require_http_methods(["GET", "POST"])
def banned_edit(request, ingredient_id):
    ingredient = get_object_or_404(Ingredient, id=ingredient_id)
    old = _snapshot(ingredient)
    form = BannedIngredientForm(
        request.POST or None, request.FILES or None, instance=ingredient
    )
    if request.method == "POST" and form.is_valid():
        ingredient = form.save(commit=False)
        ingredient.updated_by = request.user
        ingredient.last_updated = date.today()
        _apply_image(form, ingredient)
        ingredient.save()
        _ensure_aliases(ingredient, form.cleaned_data.get("synonyms") or "")
        # Sync local override if linked to reference
        if ingredient.reference_additive_id:
            LocalRegulatoryOverride.objects.update_or_create(
                reference_additive=ingredient.reference_additive,
                jurisdiction="LY",
                defaults={
                    "status": STATUS_MAP.get(
                        ingredient.safety_status, ingredient.safety_status
                    ),
                    "reason": ingredient.reason,
                    "regulatory_source": ingredient.source,
                    "reference_number": ingredient.regulatory_status,
                    "notes": ingredient.notes,
                    "is_active": True,
                    "updated_by": request.user,
                },
            )
            log_action(
                request,
                action="override.update",
                entity_type="LocalRegulatoryOverride",
                entity_id=str(ingredient.reference_additive_id),
                old_value=old,
                new_value=_snapshot(ingredient),
            )
        log_action(
            request,
            action="ingredient.update",
            entity_type="Ingredient",
            entity_id=ingredient.id,
            old_value=old,
            new_value=_snapshot(ingredient),
        )
        messages.success(request, "تم تحديث بيانات المادة.")
        return redirect("ingredients:detail", ingredient_id=ingredient.id)
    return render(
        request,
        "ingredients/banned_form.html",
        {
            "form": form,
            "mode": "edit",
            "ingredient": ingredient,
            "page_title": f"تعديل: {ingredient.name_ar}",
        },
    )


@_manager_required
@require_GET
def image_search_api(request):
    q = request.GET.get("q", "").strip()
    results = search_material_images(q, limit=8)
    return JsonResponse({"query": q, "results": results})


@_manager_required
@require_GET
def duplicate_check_api(request):
    dups = find_duplicate_candidates(
        name_ar=request.GET.get("name_ar", ""),
        name_en=request.GET.get("name_en", ""),
        e_number=request.GET.get("e_number", ""),
        cas_number=request.GET.get("cas_number", ""),
        synonyms=[s for s in (request.GET.get("synonyms") or "").split(",") if s.strip()],
    )
    return JsonResponse(
        {
            "reference": [
                {
                    "id": str(a.id),
                    "e_number": a.e_number,
                    "name_en": a.name_en,
                    "name_ar": a.name_ar,
                    "url": f"/reference/{a.id}/",
                }
                for a in dups["reference"]
            ],
            "local": [
                {
                    "id": str(i.id),
                    "e_number": i.e_number,
                    "name_en": i.name_en,
                    "name_ar": i.name_ar,
                    "url": f"/ingredients/{i.id}/",
                }
                for i in dups["local"]
            ],
        }
    )


@login_required
def unmatched_list(request):
    if not request.user.can_manage_ingredients:
        return redirect("core:home")
    items = UnmatchedQuery.objects.filter(resolved=False).order_by("-hit_count")[:200]
    return render(request, "ingredients/unmatched.html", {"items": items})
