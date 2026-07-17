# curriculum/admin.py
from embed_video.admin import AdminVideoMixin
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django import forms
from django.db import transaction
from import_export.admin import ImportExportModelAdmin
from django.utils import timezone


from .models import (
    Faculty,
    Department,
    Programme,
    Level,
    Course,
    Session,
    Semester,
    CourseAssignment,
    CourseRegistration,
    AcademicIdentityMapping,
    SchoolIdentity,
    QualificationType,
    RegistrationPolicy,

)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current')
    exclude = ['slug']
    # ADDED: This fixes the autocomplete error.
    search_fields = ['name',]

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'faculty', 'hod')
    list_filter = ('faculty',)
    search_fields = ('name',)

@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ('name', 'qualification_type')
    list_filter = ('qualification_type',)
    search_fields = ('name',)

@admin.register(QualificationType)
class QualificationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_code', 'duration_years', 'is_active')
    search_fields = ('name', 'short_code')
    list_filter = ('is_active',)

@admin.register(RegistrationPolicy)
class RegistrationPolicyAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'programme', 'level', 'min_units_per_semester', 'max_units_per_semester', 'max_carryover_units')
    list_filter = ('programme', 'level')

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'programme')
    list_filter = ('programme',)
    search_fields = ('name',)

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'course_code',
        'title',
        'department',
        'programme',
        'level',
        'session',
        'semester',
        'course_type',
        'credit_unit',
        'lecturer'
    )

    list_filter = (
        'department',
        'programme',
        'level',
        'semester'
    )

    search_fields = (
        'course_code',
        'title'
    )

    raw_id_fields = (
        'lecturer',
    )

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = ('name',)

@admin.register(CourseAssignment)
class CourseAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'course',
        'lecturer',
        'session',
        'semester',
        'is_course_adviser',
        'assigned_date'
    )

    list_filter = (
        'session',
        'semester',
        'is_course_adviser'
    )

    search_fields = (
        'course__course_code',
        'lecturer__user__first_name',
        'lecturer__user__last_name'
    )

    raw_id_fields = (
        'lecturer',
        'course',
    )


# COURSE REGISTRATION
# @admin.register(CourseRegistration)
# class CourseRegistrationAdmin(admin.ModelAdmin):
#     list_display = ("student", "course", "session", "semester")
#     list_filter = ("session", "semester", "course__department")
#     search_fields = ("student__matric_number", "course__course_code")
#     raw_id_fields = ('student', 'course',)

# """
# Drop-in replacement for CourseRegistrationAdmin in curriculum/admin.py.
# Requires `from django.utils import timezone` and `from django.contrib import
# admin, messages` at the top of that file (the latter is almost certainly
# already there).

# The "Income Report" button reuses the collection-report admin view already
# built in the finance app (admin:finance_collection_report) — it shows totals
# by fee category AND by course, so this doesn't duplicate that logic, it just
# surfaces it from where a registrar is already looking.
# """

# @admin.register(CourseRegistration)
# class CourseRegistrationAdmin(admin.ModelAdmin):
#     list_display = (
#         "student", "course", "session", "semester",
#         "is_validated", "validated_by", "registered_at",
#     )
#     list_filter = ("session", "semester", "course__department", "is_validated")
#     search_fields = ("student__matric_number", "course__course_code")
#     raw_id_fields = ('student', 'course',)
#     actions = ["validate_selected", "unvalidate_selected"]
#     change_list_template = "admin/curriculum/courseregistration/change_list.html"

#     @admin.action(description="Validate selected registrations (allow exam eligibility)")
#     def validate_selected(self, request, queryset):
#         if not request.user.has_perm("curriculum.validate_registration"):
#             self.message_user(request, "You do not have permission to validate registrations.", level=messages.ERROR)
#             return
#         updated = queryset.update(
#             is_validated=True, validated_by=request.user, validated_at=timezone.now()
#         )
#         self.message_user(request, f"{updated} registration(s) validated.", level=messages.SUCCESS)

#     @admin.action(description="Revoke validation on selected registrations")
#     def unvalidate_selected(self, request, queryset):
#         if not request.user.has_perm("curriculum.validate_registration"):
#             self.message_user(request, "You do not have permission to modify validation status.", level=messages.ERROR)
#             return
#         updated = queryset.update(is_validated=False, validated_by=None, validated_at=None)
#         self.message_user(request, f"{updated} registration(s) had validation revoked.", level=messages.WARNING)


"""
Drop-in replacement for CourseRegistrationAdmin in curriculum/admin.py.
Supersedes the version from the previous patch — same validate/unvalidate
actions, PLUS a new "Registration Report" page.

Requires at the top of curriculum/admin.py:
    from django.utils import timezone
    from django.urls import path
    from django.template.response import TemplateResponse
    from django.db.models import Count, Q
(and the existing `from django.contrib import admin, messages`)
"""

from django.utils import timezone
from django.urls import path
from django.template.response import TemplateResponse
from django.db.models import Count, Q


@admin.register(CourseRegistration)
class CourseRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "student", "course", "session", "semester",
        "is_validated", "validated_by", "registered_at",
    )
    list_filter = ("session", "semester", "course__department", "is_validated")
    search_fields = ("student__matric_number", "course__course_code")
    raw_id_fields = ('student', 'course',)
    actions = ["validate_selected", "unvalidate_selected"]
    change_list_template = "admin/curriculum/courseregistration/change_list.html"

    @admin.action(description="Validate selected registrations (allow exam eligibility)")
    def validate_selected(self, request, queryset):
        if not request.user.has_perm("curriculum.validate_registration"):
            self.message_user(request, "You do not have permission to validate registrations.", level=messages.ERROR)
            return
        updated = queryset.update(
            is_validated=True, validated_by=request.user, validated_at=timezone.now()
        )
        self.message_user(request, f"{updated} registration(s) validated.", level=messages.SUCCESS)

    @admin.action(description="Revoke validation on selected registrations")
    def unvalidate_selected(self, request, queryset):
        if not request.user.has_perm("curriculum.validate_registration"):
            self.message_user(request, "You do not have permission to modify validation status.", level=messages.ERROR)
            return
        updated = queryset.update(is_validated=False, validated_by=None, validated_at=None)
        self.message_user(request, f"{updated} registration(s) had validation revoked.", level=messages.WARNING)

    # -----------------------------------------------------------------
    # Registration Report — per course: how many registered, how many
    # validated, and (reusing the finance app's existing report service,
    # not duplicating it) how much has been collected for that course.
    # -----------------------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "registration-report/",
                self.admin_site.admin_view(self.registration_report_view),
                name="curriculum_registration_report",
            ),
        ]
        return custom + urls

    def registration_report_view(self, request):
        from finance.services.reports import FinanceReportService

        session_id = request.GET.get("session") or None
        semester_id = request.GET.get("semester") or None

        qs = CourseRegistration.objects.all()
        if session_id:
            qs = qs.filter(session_id=session_id)
        if semester_id:
            qs = qs.filter(semester_id=semester_id)

        course_stats = list(
            qs.values(
                "course_id", "course__course_code", "course__title",
                "course__department__name",
            ).annotate(
                registered_count=Count("id"),
                validated_count=Count("id", filter=Q(is_validated=True)),
            ).order_by("course__course_code")
        )

        # Reuse the finance app's existing per-course income report rather
        # than recomputing fee totals here.
        income_by_course = {
            row["course_code"]: row["total_collected"]
            for row in FinanceReportService.totals_by_course(session=session_id, semester=semester_id)
        }
        for row in course_stats:
            row["total_collected"] = income_by_course.get(row["course__course_code"], 0)
            row["pending_validation_count"] = row["registered_count"] - row["validated_count"]

        context = dict(
            self.admin_site.each_context(request),
            title="Course Registration Report",
            course_stats=course_stats,
            sessions=Session.objects.all().order_by("-start_date"),
            semesters=Semester.objects.select_related("session").order_by("-session__start_date", "name"),
            selected_session=session_id,
            selected_semester=semester_id,
            grand_total_registered=sum(r["registered_count"] for r in course_stats),
            grand_total_validated=sum(r["validated_count"] for r in course_stats),
            grand_total_income=sum(r["total_collected"] for r in course_stats),
        )
        return TemplateResponse(
            request, "admin/curriculum/courseregistration/registration_report.html", context
        )



class AcademicIdentityInline(admin.TabularInline):
    model = AcademicIdentityMapping
    extra = 1

@admin.register(SchoolIdentity)
class SchoolIdentityAdmin(admin.ModelAdmin):

    def has_add_permission(self, request):
        if self.model.objects.count() >= 5:
            return False
        return super().has_add_permission(request)

    list_display = ('identity_label', 'name', 'is_default', 'phone1', 'email')
    list_editable = ('is_default',)
    exclude = ['slug']

    inlines = [AcademicIdentityInline]

@admin.register(AcademicIdentityMapping)
class AcademicIdentityMappingAdmin(admin.ModelAdmin):
    list_display = ('department', 'faculty', 'school_identity')
    list_filter = ('school_identity',)