from django.urls import path

from . import views

app_name = "results"

urlpatterns = [
    # --- Template views: students ---
    path("progress/", views.academic_progress_view, name="academic_progress"),
    path("progress/<str:matric_number>/", views.staff_student_progress_view, name="staff_student_progress"),

    # --- Template views: lecturer ---
    path("lecturer/my-courses/", views.lecturer_my_courses_view, name="lecturer_my_courses"),
    path("course/<int:course_id>/submit/", views.lecturer_submit_scores, name="lecturer_submit_scores"),
    path(
        "course/<int:course_id>/submit-for-review/",
        views.submit_results_for_review_view,
        name="submit_results_for_review",
    ),
]