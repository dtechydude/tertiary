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

from .models import Faculty, Department, Programme, Level, Course, Session, Semester, CourseAssignment



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
