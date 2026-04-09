# from django.urls import path
# from . import views



# app_name ='attendance'

# urlpatterns = [
#     path('take-attendance/', views.take_daily_attendance, name='take_daily_attendance'),
#     path('attendance-report/', views.attendance_report, name='attendance_report'),

#     # path('student-attendance-report/', views.student_attendance_summary, name='self_attendance_report'),
#     # # NEW URL for calendar detail
#     # path('student-attendance-calendar/', views.student_attendance_detail, name='student-attendance-detail'),

#       # This is the new, simple entry point for teachers/staff to see their roster.
#     path('attendance/list/', views.student_list_view, name='attendance-student-list'),
    
#     # These views accept the student_id passed from the list page.
#     path('summary/<int:student_id>/', views.student_attendance_summary, name='student-attendance-summary'),
#     path('detail/<int:student_id>/', views.student_attendance_detail, name='student-attendance-detail'),
#     # Student's personal attendance summary (e.g., /attendance/my/summary/)
#     path('my/summary/', views.self_attendance_summary, name='self-attendance-summary'),

#     # Student's personal attendance detail (e.g., /attendance/my/detail/)
#     path('my/detail/', views.self_attendance_detail, name='self-attendance-detail'),

#     # path('attendance-success/', views.attendance_success, name='attendance_success'), # If you still want a separate success page

#   # ATTENDANCE SCANNING
#     path('scanner/', views.attendance_scanner_view, name='attendance_scanner'),
#     path('scan/<str:usn>/', views.scan_attendance_ajax, name='scan_attendance_ajax'),


# ]


# # =====================================================
# # NEW URLS LOGIC
# #===============================================

from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    
    # --- Lecturer/Staff Actions ---
    # Updated: Now includes course_id to handle specific subject attendance
    path('take-attendance/<int:course_id>/', views.take_course_attendance, name='take_course_attendance'),
    
    # Global report for admins/lecturers
    path('attendance-report/', views.attendance_report, name='attendance_report'),

    # List of students (Roster) for staff
    path('attendance/list/', views.student_list_view, name='attendance-student-list'),
    
    # Summary and Detail views for specific students (used by Staff/Lecturers)
    path('summary/<int:student_id>/', views.student_attendance_summary, name='student-attendance-summary'),
    path('detail/<int:student_id>/', views.student_attendance_detail, name='student-attendance-detail'),

    # --- Student Self-Service ---
    # Personal dashboard for the logged-in student
    path('my/summary/', views.self_attendance_summary, name='self-attendance-summary'),
    path('my/detail/', views.self_attendance_detail, name='self-attendance-detail'),

    # --- QR Scanning Logic ---
    # Updated: Scanner now opens for a specific course session
    path('scanner/<int:course_id>/', views.attendance_scanner_view, name='attendance_scanner'),
    
    # AJAX endpoint for the QR scanner to send the Matric Number (usn)
    path('scan/<str:usn>/', views.scan_attendance_ajax, name='scan_attendance_ajax'),
]