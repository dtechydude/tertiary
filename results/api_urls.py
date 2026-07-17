from django.urls import path

from . import views

app_name = "results-api"

urlpatterns = [
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