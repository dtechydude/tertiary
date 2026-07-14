"""
finance.services.documents
============================

Generates printable PDFs (course registration slip, payment receipt)
using ReportLab, per the project's specified stack. Each function
returns raw PDF bytes; views wrap these in an HttpResponse with
content_type="application/pdf".
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .exam_eligibility import ExamEligibilityService

HEADER_COLOR = colors.HexColor("#1f2937")
ZEBRA_COLOR = colors.HexColor("#f3f4f6")


def _base_table_style():
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA_COLOR]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])


def build_registration_slip_pdf(student, session, semester, registrations) -> bytes:
    """
    `registrations`: an iterable of CourseRegistration rows for this
    student/session/semester (fetch these from wherever your
    registration app exposes them — this function doesn't query for
    them itself, to avoid coupling to that app's exact query shape).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph("Course Registration Slip", styles["Title"]),
        Spacer(1, 0.5 * cm),
        Paragraph(f"Student: {student.get_full_name()} ({student.matric_number})", styles["Normal"]),
        Paragraph(f"Programme: {student.programme} — Level: {student.level}", styles["Normal"]),
        Paragraph(f"Session: {session} — Semester: {semester}", styles["Normal"]),
        Spacer(1, 0.5 * cm),
    ]

    data = [["Course Code", "Course Title", "Units", "Exam Eligible"]]
    for reg in registrations:
        eligible = ExamEligibilityService.is_course_exam_eligible(student, reg.course, session, semester)
        data.append([reg.course.course_code, reg.course.title, str(reg.course.credit_unit), "Yes" if eligible else "No"])

    total_units = sum(reg.course.credit_unit for reg in registrations)
    data.append(["", "Total Units", str(total_units), ""])

    table = Table(data, colWidths=[3 * cm, 8 * cm, 2.5 * cm, 3 * cm])
    table.setStyle(_base_table_style())
    elements.append(table)

    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(
        "Courses marked 'No' under Exam Eligible have outstanding mandatory fees. "
        "Clear them before the examination period to be admitted to sit the paper.",
        styles["Italic"],
    ))

    doc.build(elements)
    return buffer.getvalue()


def build_payment_receipt_pdf(payment) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()

    paid_at = payment.paid_at or payment.created_at
    elements = [
        Paragraph("Payment Receipt", styles["Title"]),
        Spacer(1, 0.5 * cm),
        Paragraph(f"Receipt No: {payment.reference}", styles["Normal"]),
        Paragraph(f"Student: {payment.student.get_full_name()} ({payment.student.matric_number})", styles["Normal"]),
        Paragraph(f"Amount Paid: {payment.amount}", styles["Normal"]),
        Paragraph(f"Method: {payment.get_method_display()}", styles["Normal"]),
        Paragraph(f"Status: {payment.get_status_display()}", styles["Normal"]),
        Paragraph(f"Date: {paid_at:%Y-%m-%d %H:%M}", styles["Normal"]),
        Spacer(1, 0.5 * cm),
    ]

    data = [["Item", "Amount Allocated"]]
    allocations = payment.allocations.select_related(
        "payment_item__fee_assignment__category",
        "payment_item__course_registration__course",
    )
    for allocation in allocations:
        item = allocation.payment_item
        label = (
            item.fee_assignment.category.name
            if item.fee_assignment_id else item.course_registration.course.course_code
        )
        data.append([label, str(allocation.amount)])

    table = Table(data, colWidths=[10 * cm, 4 * cm])
    table.setStyle(_base_table_style())
    elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
