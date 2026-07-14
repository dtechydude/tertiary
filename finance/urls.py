from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    # --- API v1 ---
    path(
        "api/v1/student/<int:session_id>/<int:semester_id>/clearance/",
        views.StudentSemesterClearanceView.as_view(),
        name="api_student_clearance",
    ),
    path(
        "api/v1/exam-eligibility/<int:student_id>/<int:course_id>/<int:session_id>/<int:semester_id>/",
        views.CourseExamEligibilityView.as_view(),
        name="api_exam_eligibility",
    ),
    path(
        "api/v1/payments/record/",
        views.RecordPaymentView.as_view(),
        name="api_record_payment",
    ),
    path(
        "api/v1/reports/category-totals/",
        views.FinanceCategoryReportView.as_view(),
        name="api_category_report",
    ),

    # --- Printable documents (PDF) ---
    path(
        "documents/registration-slip/<int:student_id>/<int:session_id>/<int:semester_id>/",
        views.RegistrationSlipPDFView.as_view(),
        name="registration_slip_pdf",
    ),
    path(
        "documents/receipt/<int:payment_id>/",
        views.PaymentReceiptPDFView.as_view(),
        name="payment_receipt_pdf",
    ),

    # --- Printable documents (HTML) ---
    path(
        "documents/registration-slip/<int:student_id>/<int:session_id>/<int:semester_id>/html/",
        views.registration_slip_html,
        name="registration_slip_html",
    ),
    path(
        "documents/receipt/<int:payment_id>/html/",
        views.payment_receipt_html,
        name="payment_receipt_html",
    ),
    path(
        "documents/exam-attendance/<int:course_id>/<int:session_id>/<int:semester_id>/",
        views.exam_attendance_list_html,
        name="exam_attendance_list_html",
    ),
]
