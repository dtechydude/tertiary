"""
results.services.gpa
======================

GPA/CGPA are always derived from Result rows at query time — never
hardcoded, never cached in a way that can drift from the underlying data.

Quality Point = Credit Unit x Grade Point (per project spec).

Aggregation happens in the database (Sum + F expressions) rather than in
a Python loop, so this scales to a student with hundreds of results and to
CGPA reports run across an entire cohort.
"""

from decimal import Decimal

from django.db.models import Sum, F, DecimalField, ExpressionWrapper

from ..models import Result


class GPAService:

    _quality_points = ExpressionWrapper(
        F("credit_unit") * F("grade_point"),
        output_field=DecimalField(max_digits=8, decimal_places=2),
    )

    @classmethod
    def _base_queryset(cls, published_only: bool = True):
        qs = Result.objects.filter(grade_point__isnull=False, count_in_cgpa=True)
        if published_only:
            qs = qs.filter(is_published=True)
        return qs

    @classmethod
    def calculate_gpa(cls, student, session, semester, published_only: bool = True) -> Decimal:
        """Semester GPA. Set published_only=False for a staff-facing
        provisional preview before results are officially published."""
        totals = cls._base_queryset(published_only).filter(
            student=student, session=session, semester=semester
        ).annotate(quality_points=cls._quality_points).aggregate(
            points=Sum("quality_points"), units=Sum("credit_unit")
        )
        units = totals["units"] or 0
        if not units:
            return Decimal("0.00")
        return (totals["points"] / units).quantize(Decimal("0.01"))

    @classmethod
    def calculate_cgpa(cls, student, published_only: bool = True) -> Decimal:
        """Cumulative GPA across every published, counted result.
        Excludes any Result with count_in_cgpa=False (e.g. a superseded
        carry-over attempt a registrar has chosen to drop from the
        cumulative figure)."""
        totals = cls._base_queryset(published_only).filter(
            student=student
        ).annotate(quality_points=cls._quality_points).aggregate(
            points=Sum("quality_points"), units=Sum("credit_unit")
        )
        units = totals["units"] or 0
        if not units:
            return Decimal("0.00")
        return (totals["points"] / units).quantize(Decimal("0.01"))
