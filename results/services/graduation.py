"""
results.services.graduation
=============================

Determines whether a student is eligible to graduate and, if so, which
named classification band they fall into. Every threshold and band name
comes from GraduationPolicy / ClassificationScheme / ClassificationBand —
nothing here hardcodes a CGPA cutoff or a classification label, so the
same code serves a diploma, a degree, or a certificate programme.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db.models import Sum

from ..models import ClassificationScheme, GraduationPolicy, Result
from .gpa import GPAService


@dataclass
class GraduationEvaluation:
    cgpa: Decimal
    total_credit_units: int
    minimum_cgpa_required: Decimal
    minimum_credit_units_required: Optional[int]
    meets_cgpa_requirement: bool
    meets_credit_requirement: bool
    is_eligible_to_graduate: bool
    classification: Optional[str]


class GraduationService:

    @staticmethod
    def resolve_classification_scheme(programme) -> ClassificationScheme:
        """Programme-assigned scheme first, then the global default."""
        link = getattr(programme, "classification_scheme_link", None)
        if link:
            return link.scheme
        default_scheme = ClassificationScheme.objects.filter(is_default=True, is_active=True).first()
        if not default_scheme:
            raise ValidationError(
                "No classification scheme could be resolved for this programme, and no default scheme "
                "is configured. Configure a default ClassificationScheme or a ProgrammeClassificationScheme."
            )
        return default_scheme

    @staticmethod
    def total_credit_units_earned(student) -> int:
        """
        Sums credit units of every published, counted result with a
        positive grade point. 'Passed' is inferred from grade_point > 0
        rather than a hardcoded grade letter, since grade letters (and
        which of them count as a pass) are institution-defined via
        GradeBoundary.is_pass — not assumed here.
        """
        total = Result.objects.filter(
            student=student, is_published=True, count_in_cgpa=True, grade_point__gt=0,
        ).aggregate(units=Sum("credit_unit"))["units"]
        return total or 0

    @classmethod
    def evaluate(cls, student) -> GraduationEvaluation:
        programme = student.programme
        try:
            policy = programme.graduation_policy
        except GraduationPolicy.DoesNotExist:
            raise ValidationError(f"No GraduationPolicy configured for programme '{programme}'.")

        cgpa = GPAService.calculate_cgpa(student)
        total_units = cls.total_credit_units_earned(student)

        meets_cgpa = cgpa >= policy.minimum_cgpa_to_graduate
        meets_units = (
            policy.minimum_credit_units_to_graduate is None
            or total_units >= policy.minimum_credit_units_to_graduate
        )
        eligible = meets_cgpa and meets_units

        classification = None
        if eligible:
            scheme = cls.resolve_classification_scheme(programme)
            band = scheme.bands.filter(
                min_cgpa__lte=cgpa, max_cgpa__gte=cgpa, is_graduating_class=True
            ).first()
            classification = band.name if band else None

        return GraduationEvaluation(
            cgpa=cgpa,
            total_credit_units=total_units,
            minimum_cgpa_required=policy.minimum_cgpa_to_graduate,
            minimum_credit_units_required=policy.minimum_credit_units_to_graduate,
            meets_cgpa_requirement=meets_cgpa,
            meets_credit_requirement=meets_units,
            is_eligible_to_graduate=eligible,
            classification=classification,
        )
