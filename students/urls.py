from django.urls import path

from students import views as students_views
from students.views import (
    StudentDetailView,
    StudentUpdateView,
    StudentSelfDetailView,
    AdmissionLetterSelfView,
    AdmissionLetterView,
)

app_name = 'students'

urlpatterns = [
    path('student_list/', students_views.student_list, name='student-list'),
    path('boarder_list/', students_views.student_boarder_list, name='boarder-list'),
    path('student_in_class/', students_views.student_distribution_view, name='student-in-class'),
    path('distribution/export/', students_views.student_distribution_csv_export, name='student-distribution-csv'),
    path('graduate-students/', students_views.graduate_students_view, name='graduate_students'),

    path('hostel_list/', students_views.hostel_list, name='hostel_list'),
    path('hostel/dashboard/', students_views.hostel_dashboard, name='hostel-dashboard'),
    path('hostel/assign-room/', students_views.assign_room, name='assign-room'),

    path('students/archive/', students_views.student_archive, name='student_archive'),

    # Graduates / Alumni
    path('alumni/', students_views.alumni_list_view, name='alumni_list'),
    path('alumni/readmit/<int:student_id>/', students_views.readmit_student, name='readmit_student'),

    # ID Cards
    path('student/id-card/<str:matric_number>/', students_views.StudentIDCardView.as_view(), name='student_id_card'),
    path('students/id-cards/bulk/', students_views.BulkStudentIDCardView.as_view(), name='bulk_student_id_cards'),

    # Level promotion
    path('promote-students/', students_views.promote_students_view, name='promote_students'),

    path('search/', students_views.student_search_list, name='student-search'),

    # Course registration
    path('course-registration/', students_views.course_registration_view, name='course-registration'),

    # General detail view (Admins/Teachers), by matric number
    path('profile/<str:matric_number>/', StudentDetailView.as_view(), name='student-detail'),

    # Self-view (logged-in student's own profile — courses, fees, results)
    path('my-profile/', StudentSelfDetailView.as_view(), name='student-self-detail'),

    path('student/edit/<str:matric_number>/', StudentUpdateView.as_view(), name='student-update'),

    #Admission Letter
    #  --- New (this round): staff list + bulk print ---
#     path('admission-letters/', students_views.admission_letter_list_view, name='admission-letter-list'),
#     path('admission-letters/bulk-print/', students_views.admission_letter_bulk_print_view, name='admission-letter-bulk-print'),

#    # Add these to students/urls.py (inside urlpatterns, app_name = "students")
# # --- Existing (from the first round) ---
#     path('admission-letter/', students_views.AdmissionLetterSelfView.as_view(), name='admission-letter-self'),
#     path('admission-letter/<str:matric_number>/', students_views.AdmissionLetterView.as_view(), name='admission-letter'),
#     path('admission-letter/<str:matric_number>/pdf/', students_views.admission_letter_pdf, name='admission-letter-pdf'),
#     path('admission-letter/self/pdf/', students_views.admission_letter_self_pdf, name='admission-letter-self-pdf'),

    path('admission-letter/', students_views.AdmissionLetterSelfView.as_view(), name='admission-letter-self'),
    path('admission-letter/<str:matric_number>/', students_views.AdmissionLetterView.as_view(), name='admission-letter'),
    path('admission-letter/<str:matric_number>/pdf/', students_views.admission_letter_pdf, name='admission-letter-pdf'),
    path('admission-letter/self/pdf/', students_views.admission_letter_self_pdf, name='admission-letter-self-pdf'),

    # Public — no login required, this is the QR code's target
    path('verify/admission/<str:matric_number>/', students_views.verify_admission_letter, name='verify-admission'),

# --- New (this round): staff list + bulk print ---
    path('admission-letters/', students_views.admission_letter_list_view, name='admission-letter-list'),
    path('admission-letters/bulk-print/', students_views.admission_letter_bulk_print_view, name='admission-letter-bulk-print'),


    # Public — no login required, this is the QR code's target
    # path('verify/admission/<str:matric_number>/', students_views.verify_admission_letter, name='verify-admission'),


]
