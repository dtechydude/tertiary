from django.contrib import admin, messages
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
    GraduationPolicy,
    ClassificationScheme,
    ClassificationBand,
    ProgrammeClassificationScheme,
    Transcript,
)


@admin.register(Transcript)
class TranscriptAdmin(admin.ModelAdmin):
    list_display = ("student", "verification_code", "is_official", "generated_by", "generated_at")
    list_filter = ("is_official",)
    search_fields = ("student__matric_number", "verification_code")
    readonly_fields = ("verification_code", "generated_at")


@admin.register(AssessmentComponent)
class AssessmentComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_exam_component", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active", "is_exam_component")


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
    # status/is_published are intentionally read-only here: editing them
    # directly skips ResultWorkflowService entirely — no permission check
    # for the specific stage, no ResultAuditLog entry, and results can
    # jump straight to "published" without ever passing through HOD/Dean/
    # Registrar review. Use the actions below (or the front-end approval
    # queue at /results/approvals/) instead — both go through the same
    # service, so every transition is checked and logged the same way.
    readonly_fields = (
        "total_score", "grade", "grade_point", "remark", "status", "is_published",
        "created_at", "updated_at",
    )
    inlines = [ResultScoreInline, ResultAuditLogInline]
    actions = [
        "recompute_selected", "submit_selected", "approve_hod_selected",
        "approve_dean_selected", "approve_registrar_selected", "publish_selected", "return_selected",
    ]
    list_select_related = ("student", "course", "session", "semester")

    @admin.action(description="Recompute grade from current component scores")
    def recompute_selected(self, request, queryset):
        from .services.grading import GradingService
        for result in queryset:
            GradingService.compute_result(result)

    def _run_bulk_transition(self, request, queryset, action):
        from django.core.exceptions import PermissionDenied, ValidationError
        from .services.workflow import ResultWorkflowService

        succeeded, failed = 0, 0
        for result in queryset:
            try:
                ResultWorkflowService.transition(result, action, actor=request.user)
                succeeded += 1
            except (PermissionDenied, ValidationError):
                failed += 1

        if succeeded:
            self.message_user(request, f"{succeeded} result(s) updated.", level=messages.SUCCESS)
        if failed:
            self.message_user(
                request,
                f"{failed} result(s) could not be updated — either not a valid transition from their "
                f"current status, or you're missing the permission for this stage.",
                level=messages.ERROR,
            )

    @admin.action(description="Submit selected (Draft → Submitted)")
    def submit_selected(self, request, queryset):
        self._run_bulk_transition(request, queryset, "submit")

    @admin.action(description="Approve as HOD (Submitted → HOD Approved)")
    def approve_hod_selected(self, request, queryset):
        self._run_bulk_transition(request, queryset, "approve_hod")

    @admin.action(description="Approve as Dean (HOD Approved → Dean Approved)")
    def approve_dean_selected(self, request, queryset):
        self._run_bulk_transition(request, queryset, "approve_dean")

    @admin.action(description="Approve as Registrar (Dean Approved → Registrar Approved)")
    def approve_registrar_selected(self, request, queryset):
        self._run_bulk_transition(request, queryset, "approve_registrar")

    @admin.action(description="Publish selected (Registrar Approved → Published)")
    def publish_selected(self, request, queryset):
        self._run_bulk_transition(request, queryset, "publish")

    @admin.action(description="Return selected for correction")
    def return_selected(self, request, queryset):
        self._run_bulk_transition(request, queryset, "return")


@admin.register(GraduationPolicy)
class GraduationPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "programme", "minimum_cgpa_to_graduate",
        "minimum_credit_units_to_graduate", "max_sessions_to_complete",
    )
    search_fields = ("programme__name",)


class ClassificationBandInline(admin.TabularInline):
    model = ClassificationBand
    extra = 1


@admin.register(ClassificationScheme)
class ClassificationSchemeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_default", "is_active")
    list_filter = ("is_default", "is_active")
    inlines = [ClassificationBandInline]


@admin.register(ProgrammeClassificationScheme)
class ProgrammeClassificationSchemeAdmin(admin.ModelAdmin):
    list_display = ("programme", "scheme")
    list_filter = ("scheme",)
