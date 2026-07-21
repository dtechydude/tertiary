from django.contrib import admin
from .models import StaffPosition,  Lecturer
from import_export.admin import ImportExportModelAdmin


# Tertiary Logic
@admin.register(StaffPosition)
class StaffPositionAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)

@admin.register(Lecturer)
class LecturerAdmin(ImportExportModelAdmin):
    list_display = ("get_full_name", "department", "position", "gender")
    list_filter = ( "position", "is_active")
    search_fields = ("user__first_name", "user__last_name", "middle_name",)
    raw_id_fields = ('user',)
    # autocomplete_fields = ("user")

