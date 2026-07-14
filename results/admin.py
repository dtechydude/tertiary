from django.contrib import admin
from django.db.models import Sum

from .models import (
    AssessmentComponent,
    GradingScheme,
    GradingSchemeComponent,
    GradeBoundary,
    ProgrammeGradingScheme,
    CourseGradingScheme,
    Result,
    ResultScore,
    ResultAuditLog,
)


@admin.register(AssessmentComponent)
class AssessmentComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


class GradingSchemeComponentInline(admin.TabularInline):
    model = GradingSchemeComponent
    extra = 1


class GradeBoundaryInline(admin.TabularInline):
    model = GradeBoundary
    extra = 1


@admin.register(GradingScheme)
class GradingSchemeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_default", "is_active", "component_weight_total")
    list_filter = ("is_default", "is_active")
    inlines = [GradingSchemeComponentInline, GradeBoundaryInline]

    @admin.display(description="Total Weight")
    def component_weight_total(self, obj):
        total = obj.schemecomponents.aggregate(total=Sum("weight_percentage"))["total"]
        return f"{total or 0}%"


@admin.register(ProgrammeGradingScheme)
class ProgrammeGradingSchemeAdmin(admin.ModelAdmin):
    list_display = ("programme", "scheme")
    list_filter = ("scheme",)


@admin.register(CourseGradingScheme)
class CourseGradingSchemeAdmin(admin.ModelAdmin):
    list_display = ("course", "scheme")
    search_fields = ("course__course_code", "course__title")
    list_filter = ("scheme",)


class ResultScoreInline(admin.TabularInline):
    model = ResultScore
    extra = 0


class ResultAuditLogInline(admin.TabularInline):
    model = ResultAuditLog
    extra = 0
    readonly_fields = ("actor", "action", "from_status", "to_status", "remarks", "timestamp")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        # Audit rows are only ever created by the workflow service.
        return False


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = (
        "student", "course", "session", "semester",
        "total_score", "grade", "status", "is_published",
    )
    list_filter = ("session", "semester", "status", "is_published", "grade", "course")
    search_fields = (
        "student__matric_number",
        "student__user__first_name",
        "student__user__last_name",
        "course__course_code",
        "course__title",
    )
    readonly_fields = ("total_score", "grade", "grade_point", "remark", "created_at", "updated_at")
    inlines = [ResultScoreInline, ResultAuditLogInline]
    actions = ["recompute_selected"]
    list_select_related = ("student", "course", "session", "semester")

    @admin.action(description="Recompute grade from current component scores")
    def recompute_selected(self, request, queryset):
        from .services.grading import GradingService
        for result in queryset:
            GradingService.compute_result(result)
