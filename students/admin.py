from django.contrib import admin, messages
from .models import Student, GraduationRecord
from import_export.admin import ImportExportModelAdmin
from django.shortcuts import render, redirect
from django import forms
from django.db import transaction
from django.http import HttpResponseRedirect # New import for the fix
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME # Import this!
from curriculum.models import Session
# Import models from the payments app
# from payments.models import StudentFeeAssignment, PaymentCategory, Term, Session



# Tertiary Logic

@admin.register(Student)
class StudentsAdmin(admin.ModelAdmin):
    list_display = ("matric_number", "get_full_name", "department", "programme", "level", "student_status")
    list_filter = ("department", "programme", "level", "student_status")
    search_fields = ("matric_number", "user__first_name", "user__last_name", "middle_name")
    # autocomplete_fields = ("user", "department", "programme", "level")

@admin.register(GraduationRecord)
class GraduationRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "programme", "department", "level_completed", "session", "date_graduated")
    list_filter = ("programme", "department", "level_completed", "session")
    search_fields = ("student__matric_number", "student__user__first_name", "student__user__last_name")
    # autocomplete_fields = ("student", "programme", "department", "level_completed", "session")

