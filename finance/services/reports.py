"""
finance.services.reports
==========================

Collection reporting for registrar/bursary staff: how much has been
generated per fee category (and per course), for a given session,
semester, and/or programme. Pure aggregation — no business rules live
here; that's what fee_resolution.py and exam_eligibility.py are for.
"""

from django.db.models import Case, CharField, F, Sum, Value, When

from ..models import PaymentAllocation


class FinanceReportService:

    @staticmethod
    def _successful_allocations(session=None, semester=None, programme=None):
        qs = PaymentAllocation.objects.filter(payment__status="successful")
        if session:
            qs = qs.filter(payment_item__session=session)
        if semester:
            qs = qs.filter(payment_item__semester=semester)
        if programme:
            qs = qs.filter(payment_item__student__programme=programme)
        return qs

    @classmethod
    def totals_by_category(cls, session=None, semester=None, programme=None):
        """Course fees are grouped together under the label 'Course Fees'
        alongside each named FeeCategory, so registrars see the full
        collection picture in one table."""
        qs = cls._successful_allocations(session, semester, programme).annotate(
            category_label=Case(
                When(payment_item__fee_assignment__isnull=False,
                     then=F("payment_item__fee_assignment__category__name")),
                default=Value("Course Fees"),
                output_field=CharField(),
            )
        )
        return qs.values("category_label").annotate(total_collected=Sum("amount")).order_by("-total_collected")

    @classmethod
    def totals_by_course(cls, session=None, semester=None, programme=None):
        qs = cls._successful_allocations(session, semester, programme).filter(
            payment_item__course_registration__isnull=False
        )
        return (
            qs.values(
                course_code=F("payment_item__course_registration__course__course_code"),
                course_title=F("payment_item__course_registration__course__title"),
            )
            .annotate(total_collected=Sum("amount"))
            .order_by("-total_collected")
        )

    @classmethod
    def grand_total(cls, session=None, semester=None, programme=None) -> float:
        return cls._successful_allocations(session, semester, programme).aggregate(
            total=Sum("amount")
        )["total"] or 0
