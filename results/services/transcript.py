"""
results.services.transcript
=============================

Compiles a student's full academic statement — every published result,
grouped by session/semester, with each semester's GPA and the overall
CGPA — and handles deliberate transcript generation (audit trail +
verification code, via the Transcript model).

Nothing here invents grading rules; GPA/CGPA come from GPAService,
graduation status from GraduationService — this only assembles them into
the shape a transcript document needs.
"""

from collections import OrderedDict

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import Result, Transcript
from .gpa import GPAService
from .graduation import GraduationService


class TranscriptService:

    @staticmethod
    def build_statement(student) -> dict:
        results = Result.objects.filter(
            student=student, is_published=True
        ).select_related("course", "session", "semester").order_by(
            "session__start_date", "semester__name"
        )

        grouped = OrderedDict()
        for result in results:
            key = (result.session_id, result.semester_id)
            grouped.setdefault(key, {
                "session": result.session, "semester": result.semester, "results": [],
            })
            grouped[key]["results"].append(result)

        semesters = []
        for group in grouped.values():
            gpa = GPAService.calculate_gpa(student, group["session"], group["semester"])
            units = sum(r.credit_unit for r in group["results"])
            semesters.append({**group, "gpa": gpa, "units": units})

        cgpa = GPAService.calculate_cgpa(student)

        try:
            evaluation = GraduationService.evaluate(student)
        except ValidationError:
            evaluation = None

        return {
            "semesters": semesters,
            "cgpa": cgpa,
            "evaluation": evaluation,
            "total_units": sum(s["units"] for s in semesters),
        }

    @staticmethod
    @transaction.atomic
    def generate_transcript(student, generated_by, is_official: bool = True) -> Transcript:
        return Transcript.objects.create(
            student=student, generated_by=generated_by, is_official=is_official,
        )
