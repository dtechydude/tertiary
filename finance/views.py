"""
finance.views
=============

Views stay thin: they resolve "who is asking, for what" and delegate to
the services layer for every calculation, ledger write, or PDF build.
"""

from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from curriculum.models import Course, CourseAssignment, CourseRegistration, Session, Semester

from .models import Payment
from .permissions import CanViewFinanceReports, IsFinanceStaff
from .serializers import PaymentSerializer, RecordPaymentSerializer
from .services.documents import build_payment_receipt_pdf, build_registration_slip_pdf
from .services.exam_eligibility import ExamEligibilityService
from .services.payments import FinanceService
from .services.reports import FinanceReportService


# ---------------------------------------------------------------------------
# Student-facing
# ---------------------------------------------------------------------------

class StudentSemesterClearanceView(APIView):
    """A student's own 'my fees' screen: every billable item this
    semester, cleared or not, and whether they're fully cleared to sit
    exams overall."""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id, semester_id):
        student = getattr(request.user, "student", None)
        if not student:
            return Response({"error": "User is not a student"}, status=status.HTTP_403_FORBIDDEN)

        session = get_object_or_404(Session, pk=session_id)
        semester = get_object_or_404(Semester, pk=semester_id)

        FinanceService.ensure_semester_fee_items(student, session, semester)
        summary = ExamEligibilityService.semester_clearance_summary(student, session, semester)
        return Response(summary)


class CourseExamEligibilityView(APIView):
    """Can this student sit the exam for this specific course? Useful for
    a lecturer/invigilator checking a single student, or the student
    checking before an exam."""
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id, course_id, session_id, semester_id):
        from students.models import Student
        student = get_object_or_404(Student, pk=student_id)
        course = get_object_or_404(Course, pk=course_id)
        session = get_object_or_404(Session, pk=session_id)
        semester = get_object_or_404(Semester, pk=semester_id)

        is_owner = getattr(request.user, "student", None) and request.user.student.id == student.id
        if not is_owner and not (
            request.user.has_perm("finance.record_payment") or request.user.has_perm("finance.view_finance_reports")
        ):
            return Response({"error": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)

        result = ExamEligibilityService.check(student, course, session, semester)
        return Response({
            "is_eligible": result.is_eligible,
            "outstanding_items": [
                {
                    "label": (
                        item.fee_assignment.category.name
                        if item.fee_assignment_id else item.course_registration.course.course_code
                    ),
                    "balance": item.balance,
                }
                for item in result.outstanding_items
            ],
        })


# ---------------------------------------------------------------------------
# Bursary / registrar-facing
# ---------------------------------------------------------------------------

class RecordPaymentView(APIView):
    """Bursary staff records a payment (online gateway confirmation or a
    manual/offline payment) and allocates it across one or more bills."""
    permission_classes = [IsAuthenticated, IsFinanceStaff]

    def post(self, request):
        from students.models import Student

        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = get_object_or_404(Student, pk=data["student_id"])
        try:
            payment = FinanceService.record_payment(
                student=student,
                reference=data["reference"],
                amount=data["amount"],
                method=data["method"],
                allocations=data["allocations"],
                recorded_by=request.user,
                mark_successful=data["mark_successful"],
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class FinanceCategoryReportView(APIView):
    """How much has been collected per fee category (and course fees as
    their own line), optionally filtered by session/semester/programme —
    the 'school interface to see how much is generated from each payment
    category' requirement."""
    permission_classes = [IsAuthenticated, CanViewFinanceReports]

    def get(self, request):
        session_id = request.query_params.get("session")
        semester_id = request.query_params.get("semester")
        programme_id = request.query_params.get("programme")

        return Response({
            "by_category": list(FinanceReportService.totals_by_category(session_id, semester_id, programme_id)),
            "by_course": list(FinanceReportService.totals_by_course(session_id, semester_id, programme_id)),
            "grand_total": FinanceReportService.grand_total(session_id, semester_id, programme_id),
        })


# ---------------------------------------------------------------------------
# Printable documents
# ---------------------------------------------------------------------------

class RegistrationSlipPDFView(APIView):
    """Course registration printout for a student, for a given
    session/semester, showing each course and its exam eligibility."""
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id, session_id, semester_id):
        from students.models import Student
        student = get_object_or_404(Student, pk=student_id)
        session = get_object_or_404(Session, pk=session_id)
        semester = get_object_or_404(Semester, pk=semester_id)

        is_owner = getattr(request.user, "student", None) and request.user.student.id == student.id
        if not is_owner and not request.user.has_perm("finance.view_finance_reports"):
            return Response({"error": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)

        registrations = CourseRegistration.objects.filter(
            student=student, session=session, semester=semester
        ).select_related("course")

        pdf_bytes = build_registration_slip_pdf(student, session, semester, registrations)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="registration_slip_{student.matric_number}.pdf"'
        return response


class PaymentReceiptPDFView(APIView):
    """Printable receipt for a single payment."""
    permission_classes = [IsAuthenticated]

    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, pk=payment_id)

        is_owner = getattr(request.user, "student", None) and request.user.student.id == payment.student_id
        if not is_owner and not request.user.has_perm("finance.view_finance_reports"):
            return Response({"error": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)

        pdf_bytes = build_payment_receipt_pdf(payment)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="receipt_{payment.reference}.pdf"'
        return response


# ---------------------------------------------------------------------------
# HTML equivalents — same data, viewable directly in the browser
# ---------------------------------------------------------------------------

def registration_slip_html(request, student_id, session_id, semester_id):
    from students.models import Student
    student = get_object_or_404(Student, pk=student_id)
    session = get_object_or_404(Session, pk=session_id)
    semester = get_object_or_404(Semester, pk=semester_id)

    is_owner = getattr(request.user, "student", None) and request.user.student.id == student.id
    if not is_owner and not request.user.has_perm("finance.view_finance_reports"):
        return render(request, "errors/403.html", {"message": "Not permitted."}, status=403)

    registrations = CourseRegistration.objects.filter(
        student=student, session=session, semester=semester
    ).select_related("course")

    rows = []
    for reg in registrations:
        result = ExamEligibilityService.check(student, reg.course, session, semester)
        rows.append({
            "course": reg.course,
            "is_eligible": result.is_eligible,
            "reasons": result.reasons,
        })
    total_units = sum(reg.course.credit_unit for reg in registrations)

    return render(request, "finance/registration_slip.html", {
        "student": student, "session": session, "semester": semester,
        "rows": rows, "total_units": total_units,
    })


def payment_receipt_html(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)

    is_owner = getattr(request.user, "student", None) and request.user.student.id == payment.student_id
    if not is_owner and not request.user.has_perm("finance.view_finance_reports"):
        return render(request, "errors/403.html", {"message": "Not permitted."}, status=403)

    allocations = payment.allocations.select_related(
        "payment_item__fee_assignment__category",
        "payment_item__course_registration__course",
    )
    rows = [
        {
            "label": (
                a.payment_item.fee_assignment.category.name
                if a.payment_item.fee_assignment_id else a.payment_item.course_registration.course.course_code
            ),
            "amount": a.amount,
        }
        for a in allocations
    ]

    return render(request, "finance/payment_receipt.html", {"payment": payment, "rows": rows})


def exam_attendance_list_html(request, course_id, session_id, semester_id):
    """
    Printable attendance list for a course's exam — the artifact an
    invigilator/HOD uses to see exactly who is (and isn't) cleared to
    sit the paper. Viewable by finance/registrar staff, or the lecturer
    actually assigned to this course for this session/semester.
    """
    course = get_object_or_404(Course, pk=course_id)
    session = get_object_or_404(Session, pk=session_id)
    semester = get_object_or_404(Semester, pk=semester_id)

    is_assigned_lecturer = (
        hasattr(request.user, "lecturer")
        and CourseAssignment.objects.filter(
            lecturer=request.user.lecturer, course=course, session=session, semester=semester
        ).exists()
    )
    if not is_assigned_lecturer and not request.user.has_perm("finance.view_finance_reports"):
        return render(request, "errors/403.html", {"message": "Not permitted."}, status=403)

    rows = ExamEligibilityService.course_attendance_list(course, session, semester)
    eligible_count = sum(1 for row in rows if row["is_eligible"])

    return render(request, "finance/exam_attendance_list.html", {
        "course": course, "session": session, "semester": semester,
        "rows": rows, "eligible_count": eligible_count, "total_count": len(rows),
    })


# ---------------------------------------------------------------------------
# Staff review screen — approve/reject student-submitted payment claims
# ---------------------------------------------------------------------------

@login_required
@permission_required("finance.record_payment", raise_exception=True)
def pending_payments_view(request):
    """
    Everything a bursary officer needs on one page: every PENDING payment
    claim a student has submitted, what it's meant to cover, and one-click
    Approve/Reject. No API calls required — this is a plain HTML form.
    """
    pending_payments = Payment.objects.filter(
        status=Payment.Status.PENDING
    ).select_related("student").prefetch_related(
        "allocations__payment_item__fee_assignment__category",
        "allocations__payment_item__course_registration__course",
    ).order_by("-created_at")

    return render(request, "finance/pending_payments.html", {
        "pending_payments": pending_payments,
    })


@login_required
@permission_required("finance.record_payment", raise_exception=True)
@require_POST
def approve_payment_view(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id, status=Payment.Status.PENDING)
    FinanceService.confirm_payment(payment)
    messages.success(
        request,
        f"Payment {payment.reference} approved. {payment.student.get_full_name()}'s exam "
        f"eligibility has been updated automatically wherever this payment applies."
    )
    return redirect("finance:pending_payments")


@login_required
@permission_required("finance.record_payment", raise_exception=True)
@require_POST
def reject_payment_view(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id, status=Payment.Status.PENDING)
    reason = request.POST.get("reason", "")
    FinanceService.reject_payment(payment)
    messages.warning(request, f"Payment {payment.reference} was rejected.{(' Reason: ' + reason) if reason else ''}")
    return redirect("finance:pending_payments")
