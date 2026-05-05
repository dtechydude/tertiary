# curriculum/admin.py
from embed_video.admin import AdminVideoMixin
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django import forms
from django.db import transaction
from import_export.admin import ImportExportModelAdmin
# from payments.models import StudentFeeAssignment, ClassFeeTemplate, PaymentCategory
# from results.models import SessionResultStatus

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
    list_display = ('name',)
    search_fields = ('name',)

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
        'semester',
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
@admin.register(CourseRegistration)
class CourseRegistrationAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "session", "semester")
    list_filter = ("session", "semester", "course__department")
    search_fields = ("student__matric_number", "course__course_code")
    raw_id_fields = ('student', 'course',)


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