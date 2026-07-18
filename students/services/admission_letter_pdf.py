"""
students.services.admission_letter_pdf
========================================

Builds the downloadable Admission Letter PDF. Requires the `qrcode`
package (`pip install "qrcode[pil]"`) in addition to reportlab, which
this project already uses elsewhere (finance receipts, lecturer profile).
"""

import io

import qrcode
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, ListFlowable, ListItem,
)


def _safe_image(field):
    """Returns a usable file path for a Django ImageField, or None if
    it's empty or the file is missing from disk (avoids a hard crash if
    a signature/logo was deleted outside Django)."""
    if not field:
        return None
    try:
        if field.storage.exists(field.name):
            return field.path
    except Exception:
        return None
    return None


def _generate_qr_image(url):
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return ImageReader(buffer)


def build_admission_letter_pdf(student, school_identity, student_full_name, verify_url):
    response = HttpResponse(content_type='application/pdf')
    filename = f"{student.matric_number}_admission_letter.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
    )

    styles = getSampleStyleSheet()
    school_title_style = ParagraphStyle(
        'SchoolTitle', parent=styles['Heading1'],
        fontSize=15, textColor=colors.HexColor('#002366'), spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        'Meta', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#64748b'),
    )
    letter_title_style = ParagraphStyle(
        'LetterTitle', parent=styles['Heading2'],
        alignment=1, textColor=colors.HexColor('#002366'), spaceBefore=16, spaceAfter=16,
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'], fontSize=10.5, leading=16, alignment=4,  # justified
    )
    ref_style = ParagraphStyle(
        'Ref', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#475569'),
    )
    signature_name_style = ParagraphStyle(
        'SigName', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', alignment=1,
    )
    signature_title_style = ParagraphStyle(
        'SigTitle', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#64748b'), alignment=1,
    )

    elements = []

    # --- Letterhead ---
    school_name = school_identity.name if school_identity else "School"
    logo_path = _safe_image(getattr(school_identity, 'logo', None))

    header_cells = []
    if logo_path:
        header_cells.append(Image(logo_path, width=0.7 * inch, height=0.7 * inch))
    else:
        header_cells.append(Paragraph("", meta_style))

    meta_lines = []
    if school_identity:
        if getattr(school_identity, 'address', None):
            meta_lines.append(school_identity.address)
        contact_bits = [b for b in [
            getattr(school_identity, 'phone', None),
            getattr(school_identity, 'email', None),
            getattr(school_identity, 'website', None),
        ] if b]
        if contact_bits:
            meta_lines.append(" &bull; ".join(contact_bits))

    header_text = [Paragraph(school_name, school_title_style)]
    if meta_lines:
        header_text.append(Paragraph("<br/>".join(meta_lines), meta_style))

    header_table = Table([[header_cells[0], header_text]], colWidths=[0.9 * inch, 5.6 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", color=colors.HexColor('#002366'), thickness=2))
    elements.append(Spacer(1, 14))

    # --- Ref / date row ---
    ref_table = Table(
        [[Paragraph(f"Ref: {student.matric_number}/ADM", ref_style),
          Paragraph(f"Date: {student.date_admitted.strftime('%B %d, %Y') if student.date_admitted else '—'}", ref_style)]],
        colWidths=[3.25 * inch, 3.25 * inch],
    )
    ref_table.setStyle(TableStyle([('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    elements.append(ref_table)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(f"<b>{student_full_name}</b>", body_style))
    if getattr(student, 'guardian_address', None):
        elements.append(Paragraph(student.guardian_address, body_style))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("LETTER OF ADMISSION", letter_title_style))

    # --- Body ---
    department = student.department.name if student.department else "—"
    faculty_line = f"Faculty of {student.department.faculty.name}, " if (
        student.department and getattr(student.department, 'faculty', None)
    ) else ""
    programme = str(student.programme) if student.programme else "—"
    qualification = (
        f" leading to the award of <b>{student.programme.qualification_type}</b>"
        if student.programme and getattr(student.programme, 'qualification_type', None) else ""
    )
    level = str(student.level) if student.level else "—"
    student_type = student.get_student_type_display()
    date_admitted = student.date_admitted.strftime('%B %d, %Y') if student.date_admitted else "—"

    elements.append(Paragraph(f"Dear {student.user.first_name or student_full_name},", body_style))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"We are pleased to inform you that you have been offered admission into the "
        f"<b>{department}</b> Department, {faculty_line}to study <b>{programme}</b>"
        f"{qualification} at <b>{level}</b> level, under the <b>{student_type}</b> mode of "
        f"study, with effect from <b>{date_admitted}</b>.",
        body_style,
    ))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Your Matriculation Number has been assigned as:", body_style))

    matric_table = Table([[student.matric_number]], colWidths=[3 * inch])
    matric_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#0d6efd')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eaf2ff')),
    ]))
    elements.append(Spacer(1, 4))
    elements.append(matric_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Conditions of Admission</b>", body_style))
    elements.append(Paragraph("This offer of admission is subject to the following conditions:", body_style))

    conditions = [
        "Presentation of original copies of your credentials for verification during physical registration.",
        "Payment of all prescribed tuition and other fees before the commencement of academic activities.",
        "Full compliance with the rules, regulations, and code of conduct of the institution.",
        "This admission is provisional and may be revoked at any time if any information provided "
        "in your application is found to be false or misleading.",
        "You are required to complete your registration formalities within the period communicated "
        "by the Registry/Admissions Office.",
    ]
    elements.append(ListFlowable(
        [ListItem(Paragraph(c, body_style), spaceAfter=6) for c in conditions],
        bulletType='1', start=1,
    ))

    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        f"We congratulate you on this achievement and look forward to your success at {school_name}.",
        body_style,
    ))
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("Yours faithfully,", body_style))
    elements.append(Spacer(1, 30))

    # --- Signature block: two columns, each optionally with an image ---
    registrar_sig_path = _safe_image(getattr(school_identity, 'registrar_signature', None))
    authorized_sig_path = _safe_image(getattr(school_identity, 'authorized_signature', None))

    def signature_cell(sig_path, name, title):
        cell = []
        if sig_path:
            cell.append(Image(sig_path, width=1.4 * inch, height=0.5 * inch))
            cell.append(Spacer(1, 2))
        cell.append(HRFlowable(width="80%", color=colors.HexColor('#1e293b'), thickness=1))
        cell.append(Spacer(1, 4))
        cell.append(Paragraph(name or "&mdash;", signature_name_style))
        cell.append(Paragraph(title, signature_title_style))
        return cell

    registrar_name = school_identity.registrar_name if school_identity else ""
    authorized_name = school_identity.authorized_signee_name if school_identity else ""
    authorized_title = (
        school_identity.authorized_signee_title if school_identity and school_identity.authorized_signee_title
        else "Vice Chancellor"
    )

    signature_table = Table(
        [[
            signature_cell(registrar_sig_path, registrar_name, "Registrar"),
            signature_cell(authorized_sig_path, authorized_name, authorized_title),
        ]],
        colWidths=[3.1 * inch, 3.1 * inch],
    )
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
    ]))
    elements.append(signature_table)

    # --- QR code ---
    elements.append(Spacer(1, 24))
    qr_image_reader = _generate_qr_image(verify_url)
    qr_flowable = Image(qr_image_reader, width=0.9 * inch, height=0.9 * inch)

    qr_table = Table([[qr_flowable]], colWidths=[6.4 * inch])
    qr_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
    elements.append(qr_table)
    elements.append(Paragraph(
        "Scan to verify authenticity", ParagraphStyle('QRCaption', parent=meta_style, alignment=1),
    ))

    doc.build(elements)
    return response
