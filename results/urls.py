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

    # --- Approval queue: HOD / Dean / Registrar / Publish ---
    path("approvals/", views.approval_queue_view, name="approval_queue"),
    path("approvals/action/", views.approval_action_view, name="approval_action"),

    # --- Transcript ---
    path("transcript/", views.my_transcript_view, name="my_transcript"),
    path("transcript/generate/", views.generate_my_transcript_view, name="generate_my_transcript"),
    path("transcript/<str:matric_number>/generate/", views.staff_generate_transcript_view, name="staff_generate_transcript"),
    path("transcript/pdf/<int:transcript_id>/", views.transcript_pdf_view, name="transcript_pdf"),

    # --- API v1 ---
    path(
        "api/v1/lecturer/course/<int:course_id>/results/",
        views.LecturerCourseResultListView.as_view(),
        name="api_lecturer_course_results",
    ),
    path(
        "api/v1/lecturer/scores/bulk/",
        views.BulkScoreEntryView.as_view(),
        name="api_bulk_score_entry",
    ),
    path(
        "api/v1/results/<int:result_id>/workflow/",
        views.ResultWorkflowActionView.as_view(),
        name="api_result_workflow",
    ),
    path(
        "api/v1/student/results/",
        views.StudentResultListView.as_view(),
        name="api_student_results",
    ),
    path(
        "api/v1/student/gpa-summary/",
        views.StudentGPASummaryView.as_view(),
        name="api_student_gpa",
    ),
    path(
        "api/v1/students/<int:student_id>/graduation-evaluation/",
        views.StudentGraduationEvaluationView.as_view(),
        name="api_student_graduation_evaluation",
    ),
]
