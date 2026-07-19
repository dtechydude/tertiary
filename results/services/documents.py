"""
results.services.documents
============================

Generates the transcript PDF using ReportLab, per the project's
specified stack. Returns raw PDF bytes; the view wraps this in an
HttpResponse with content_type="application/pdf".
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HEADER_COLOR = colors.HexColor("#1f2937")
ZEBRA_COLOR = colors.HexColor("#f3f4f6")


def _table_style():
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA_COLOR]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])


def build_transcript_pdf(student, transcript, statement) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    watermark_style = ParagraphStyle(
        "watermark", parent=styles["Normal"], textColor=colors.red,
        fontSize=11, alignment=1, spaceAfter=10,
    )

    elements = []

    if not transcript.is_official:
        elements.append(Paragraph(
            "UNOFFICIAL — PROVISIONAL COPY, NOT VALID FOR EXTERNAL SUBMISSION", watermark_style
        ))

    elements += [
        Paragraph("Academic Transcript", styles["Title"]),
        Spacer(1, 0.3 * cm),
        Paragraph(f"Student: {student.get_full_name()} ({student.matric_number})", styles["Normal"]),
        Paragraph(f"Programme: {student.programme} — Department: {student.department}", styles["Normal"]),
        Paragraph(f"Verification Code: {transcript.verification_code}", styles["Normal"]),
        Paragraph(f"Generated: {transcript.generated_at:%Y-%m-%d %H:%M} "
                   f"({'Official' if transcript.is_official else 'Unofficial'})", styles["Normal"]),
        Spacer(1, 0.5 * cm),
    ]

    for group in statement["semesters"]:
        elements.append(Paragraph(
            f"{group['session']} — {group['semester']} (Semester GPA: {group['gpa']})", styles["Heading4"]
        ))
        data = [["Code", "Title", "Units", "Score", "Grade", "Grade Pt"]]
        for result in group["results"]:
            data.append([
                result.course.course_code, result.course.title, str(result.credit_unit),
                str(result.total_score), result.grade, str(result.grade_point or "-"),
            ])
        table = Table(data, colWidths=[2 * cm, 6.5 * cm, 1.5 * cm, 1.8 * cm, 1.8 * cm, 2 * cm])
        table.setStyle(_table_style())
        elements.append(table)
        elements.append(Spacer(1, 0.4 * cm))

    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(f"Total Units Completed: {statement['total_units']}", styles["Normal"]))
    elements.append(Paragraph(f"Cumulative GPA (CGPA): {statement['cgpa']}", styles["Heading3"]))

    evaluation = statement.get("evaluation")
    if evaluation and evaluation.is_eligible_to_graduate:
        elements.append(Paragraph(f"Classification: {evaluation.classification or 'N/A'}", styles["Heading3"]))

    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(
        "This document's authenticity can be verified using the verification code above.",
        styles["Italic"],
    ))

    doc.build(elements)
    return buffer.getvalue()
