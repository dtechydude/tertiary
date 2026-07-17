from django.urls import path

from students import views as students_views
from students.views import (
    StudentDetailView,
    StudentUpdateView,
    StudentDeleteView,
    StudentSelfDetailView,
    MyTeacherDetailView,
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
]
