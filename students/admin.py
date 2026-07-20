from django.contrib import admin, messages
from .models import Student, GraduationRecord, Hostel, Room
from .resources import StudentResource
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
class StudentsAdmin(ImportExportModelAdmin):
    resource_class = StudentResource
    list_display = ("matric_number", "get_full_name", "department", "programme", "level", "student_status")
    list_filter = ("department", "programme", "level", "student_status")
    search_fields = ("matric_number", "user__first_name", "user__last_name", "middle_name")
    raw_id_fields = ('user',)

    # autocomplete_fields = ("user", "department", "programme", "level")

@admin.register(GraduationRecord)
class GraduationRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "programme", "department", "level_completed", "session", "date_graduated")
    list_filter = ("programme", "department", "level_completed", "session")
    search_fields = ("student__matric_number", "student__user__first_name", "student__user__last_name")
    # autocomplete_fields = ("student", "programme", "department", "level_completed", "session")


# TERTIARY LOGIC FOR HOSTE ==========================
from django.contrib import admin
from .models import Hostel, Room

class RoomInline(admin.TabularInline):
    """Allows adding/editing rooms directly inside the Hostel page."""
    model = Room
    extra = 1  # Number of empty room slots to show by default
    fields = ('room_number', 'max_occupancy', 'is_available')

@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    # What shows up in the main list view
    list_display = ('name', 'gender_type', 'hostel_master', 'capacity', 'occupied_spaces_display', 'vacancy_status')
    list_filter = ('gender_type',)
    search_fields = ('name', 'hostel_master__first_name', 'hostel_master__last_name')
    prepopulated_fields = {"slug": ("name",)}
    
    # Organize the form into logical sections
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'gender_type')
        }),
        ('Management & Capacity', {
            'fields': ('hostel_master', 'capacity')
        }),
        ('Additional Info', {
            'fields': ('description',),
            'classes': ('collapse',) # Hide this by default to keep page clean
        }),
    )
    
    inlines = [RoomInline]

    # Custom Column for list_display
    @admin.display(description='Students Resident')
    def occupied_spaces_display(self, obj):
        return obj.occupied_spaces

    # Visual indicator of vacancy
    @admin.display(description='Status')
    def vacancy_status(self, obj):
        occupied = obj.occupied_spaces
        if occupied >= obj.capacity:
            return "Full"
        return f"{obj.capacity - occupied} Spaces Left"

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'hostel', 'max_occupancy', 'is_available')
    list_filter = ('hostel', 'is_available')
    search_fields = ('room_number', 'hostel__name')