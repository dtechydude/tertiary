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


    # School Bank Details
    path('bank-detail/', views.bank_details_view, name='bank-detail'),


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

    # --- Staff: review and approve/reject student-submitted payments ---
    path("payments/pending/", views.pending_payments_view, name="pending_payments"),
    path("payments/<int:payment_id>/approve/", views.approve_payment_view, name="approve_payment"),
    path("payments/<int:payment_id>/reject/", views.reject_payment_view, name="reject_payment"),

    # =============================================================================
# ADDITIONS to finance/urls.py — append these entries inside the existing
# `urlpatterns = [ ... ]` list (e.g. right before the closing `]`).
# Every existing path stays exactly as it is.
# =============================================================================

    # --- Registrar/Bursary: Accounting Report + Debtors List (portal) ---
    path("reports/", views.finance_reports_dashboard_view, name="reports_dashboard"),
    path("reports/export/collection.csv", views.finance_collection_csv_view, name="collection_report_csv"),
    path("reports/export/debtors.csv", views.debtors_csv_view, name="debtors_csv"),

    # --- Wallet: student-facing ---
    path("wallet/", views.wallet_dashboard_view, name="wallet_dashboard"),
    path("wallet/fund/", views.fund_wallet_view, name="fund_wallet"),
    path("wallet/apply/", views.apply_wallet_view, name="apply_wallet"),

    # --- Wallet funding: staff approve/reject (shown on the existing
    #     pending_payments.html page, alongside the existing payment claims) ---
    path("wallet/funding/<int:request_id>/approve/", views.approve_wallet_funding_view, name="approve_wallet_funding"),
    path("wallet/funding/<int:request_id>/reject/", views.reject_wallet_funding_view, name="reject_wallet_funding"),

]
