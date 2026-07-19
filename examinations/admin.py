from django.contrib import admin

from .models import ExamSchedule, ExamVenue


@admin.register(ExamVenue)
class ExamVenueAdmin(admin.ModelAdmin):
    list_display = ("name", "capacity", "location", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "location")


@admin.register(ExamSchedule)
class ExamScheduleAdmin(admin.ModelAdmin):
    list_display = ("course", "session", "semester", "exam_date", "start_time", "end_time", "venue")
    list_filter = ("session", "semester", "venue")
    search_fields = ("course__course_code", "course__title")
    filter_horizontal = ("invigilators",)
    date_hierarchy = "exam_date"
