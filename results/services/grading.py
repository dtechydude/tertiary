"""
results.services.grading
=========================

Every score -> grade calculation happens here, and nowhere else. Views,
admin, and the model layer all call into GradingService instead of doing
their own arithmetic — this is the single place that needs to change if an
institution's rules change, and the only place that needs testing for
correctness of grading math.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import (
    Result,
    ResultScore,
    GradingScheme,
    GradingSchemeComponent,
    GradeBoundary,
    ProgrammeGradingScheme,
    CourseGradingScheme,
)


class GradingService:

    @staticmethod
    def resolve_scheme(course) -> GradingScheme:
        """
        Resolution order: Course-level override > Programme default >
        global default scheme. Raises if nothing resolves so a course is
        never silently graded with the wrong rules.
        """
        override = CourseGradingScheme.objects.filter(course=course).select_related("scheme").first()
        if override:
            return override.scheme

        programme_link = ProgrammeGradingScheme.objects.filter(
            programme=course.programme
        ).select_related("scheme").first()
        if programme_link:
            return programme_link.scheme

        default_scheme = GradingScheme.objects.filter(is_default=True, is_active=True).first()
        if not default_scheme:
            raise ValidationError(
                "No grading scheme could be resolved for this course, and no default scheme is configured. "
                "Configure a default GradingScheme, a ProgrammeGradingScheme, or a CourseGradingScheme."
            )
        return default_scheme

    @staticmethod
    @transaction.atomic
    def compute_result(result: Result) -> Result:
        """
        Recalculates total_score, grade, grade_point and remark for a
        Result from its ResultScore rows, weighted according to
        result.scheme. Makes no assumption about how many components
        exist or what they're called.
        """
        links = {
            link.component_id: link
            for link in GradingSchemeComponent.objects.filter(scheme=result.scheme).select_related("component")
        }
        if not links:
            raise ValidationError(f"Grading scheme '{result.scheme}' has no components configured.")

        scores = {s.component_id: s.raw_score for s in result.scores.all()}

        total = Decimal("0.00")
        for component_id, link in links.items():
            raw = Decimal(scores.get(component_id, 0))
            if raw > link.max_raw_score:
                raise ValidationError(
                    f"{link.component.name} score ({raw}) exceeds the maximum of {link.max_raw_score}."
                )
            weighted = (raw / link.max_raw_score) * link.weight_percentage
            total += weighted

        total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result.total_score = total

        boundary = GradeBoundary.objects.filter(
            scheme=result.scheme, min_score__lte=total, max_score__gte=total
        ).first()

        if not boundary:
            raise ValidationError(
                f"No grade boundary configured for a score of {total} under scheme '{result.scheme}'. "
                f"Check the scheme's GradeBoundary coverage for gaps."
            )

        result.grade = boundary.grade
        result.grade_point = boundary.grade_point
        result.remark = boundary.remark
        result.save(update_fields=["total_score", "grade", "grade_point", "remark", "updated_at"])
        return result

    @staticmethod
    @transaction.atomic
    def record_scores(result: Result, component_scores: dict, actor=None) -> Result:
        """
        Upserts one or more ResultScore rows (component_id -> raw_score)
        then recomputes the grade in a single atomic operation, and logs
        the edit for audit purposes.
        """
        for component_id, raw_score in component_scores.items():
            ResultScore.objects.update_or_create(
                result=result, component_id=component_id,
                defaults={"raw_score": raw_score},
            )
        GradingService.compute_result(result)

        from .workflow import ResultWorkflowService
        ResultWorkflowService.log(
            result, actor=actor, action="score_updated",
            remarks="Component scores recorded/updated.",
        )
        return result
