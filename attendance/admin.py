# from datetime import timedelta, datetime
# from django.contrib import admin
# from .models import Attendance
# from import_export.admin import ImportExportModelAdmin

# @admin.register(Attendance)
# class AttendanceAdmin(ImportExportModelAdmin):   
 
#     list_display = ('student', 'date',  'present')
#     list_filter = ['student__programme']
#     search_fields = ('student__user__first_name', 'student__user__last_name', 'student__user__username', 'student__matric_number')
#     raw_id_fields = ['student',]

  
# # admin.py (inside your AttendanceAdmin class or as a standalone admin view)
# from django.contrib import admin, messages
# from django.shortcuts import redirect
# from django.urls import path
# from .models import Attendance

# class AttendanceAdmin(admin.ModelAdmin):
#     change_list_template = "admin/attendance/attendance_change_list.html"

#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             path('reset-attd/', self.admin_site.admin_view(self.reset_attd), name='reset_attd'),
#         ]
#         return custom_urls + urls

#     def reset_attd(self, request):
#         if request.method == "POST":
#             course_id = request.POST.get('course_id')
#             start = request.POST.get('startdate')
#             end = request.POST.get('enddate')

#             deleted_count, _ = Attendance.objects.filter(
#                 course_id=course_id,
#                 date__range=[start, end]
#             ).delete()

#             self.message_user(request, f"Successfully deleted {deleted_count} records.", messages.SUCCESS)
#         return redirect("..")


from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django.utils import timezone
from .models import Attendance
from curriculum.models import Course
from import_export.admin import ImportExportModelAdmin

@admin.register(Attendance)
class AttendanceAdmin(ImportExportModelAdmin):
    # Updated to include Course and Status
    list_display = ('student', 'course', 'date', 'status', 'marked_by')
    
    # Allows you to change status directly from the list view without clicking into the record
    list_editable = ('status',)
    
    # Filter by Date, Course, and Programme
    list_filter = ('date', 'course', 'student__programme', 'status')
    
    # Search by Matric Number or Name
    search_fields = (
        'student__user__first_name', 
        'student__user__last_name', 
        'student__matric_number',
        'course__course_code'
    )
    
    raw_id_fields = ['student', 'course', 'marked_by']
    
    # Tells Django Admin to use your custom template for the list view
    change_list_template = "admin/attendance/attendance_change_list.html"

    # --- 1. Provide Course List to the Template ---
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        # This provides the dropdown data for your 'reset-attd' form
        extra_context['all_courses'] = Course.objects.all().order_by('course_code')
        return super().changelist_view(request, extra_context=extra_context)

    # --- 2. Custom URL for Bulk Reset ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reset-attd/', self.admin_site.admin_view(self.reset_attd), name='reset_attd'),
        ]
        return custom_urls + urls

    # --- 3. Logic for the Bulk Reset Action ---
    def reset_attd(self, request):
        if request.method == "POST":
            course_id = request.POST.get('course_id')
            start = request.POST.get('startdate')
            end = request.POST.get('enddate')

            if not course_id or not start or not end:
                self.message_user(request, "Missing required fields for reset.", messages.ERROR)
                return redirect("..")

            # Perform deletion
            deleted_count, _ = Attendance.objects.filter(
                course_id=course_id,
                date__range=[start, end]
            ).delete()

            if deleted_count > 0:
                self.message_user(
                    request, 
                    f"Successfully deleted {deleted_count} attendance records for the selected range.", 
                    messages.SUCCESS
                )
            else:
                self.message_user(request, "No records found to delete for the selected criteria.", messages.WARNING)
        
        return redirect("..")