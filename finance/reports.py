"""
finance.services.reports
==========================

Collection reporting for registrar/bursary staff: how much has been
generated per fee category (and per course, and per payment method), for
a given session, semester, programme, and/or department. Also surfaces
the debtors list — students with an outstanding balance — for the same
set of filters. Pure aggregation — no business rules live here; that's
what fee_resolution.py and exam_eligibility.py are for.

Every method's new `department` parameter defaults to None, and it's
appended AFTER the existing `programme` parameter — so every existing
caller (FinanceCategoryReportView, the Django-admin collection_report
view) that calls these positionally still works unchanged.
"""

from decimal import Decimal

from django.db.models import Case, CharField, F, Sum, Value, When

from ..models import PaymentAllocation, PaymentItem


class FinanceReportService:

    @staticmethod
    def _successful_allocations(session=None, semester=None, programme=None, department=None):
        qs = PaymentAllocation.objects.filter(payment__status="successful")
        if session:
            qs = qs.filter(payment_item__session=session)
        if semester:
            qs = qs.filter(payment_item__semester=semester)
        if programme:
            qs = qs.filter(payment_item__student__programme=programme)
        if department:
            qs = qs.filter(payment_item__student__department=department)
        return qs

    @classmethod
    def totals_by_category(cls, session=None, semester=None, programme=None, department=None):
        """Course fees are grouped together under the label 'Course Fees'
        alongside each named FeeCategory, so registrars see the full
        collection picture in one table."""
        qs = cls._successful_allocations(session, semester, programme, department).annotate(
            category_label=Case(
                When(payment_item__fee_assignment__isnull=False,
                     then=F("payment_item__fee_assignment__category__name")),
                default=Value("Course Fees"),
                output_field=CharField(),
            )
        )
        return qs.values("category_label").annotate(total_collected=Sum("amount")).order_by("-total_collected")

    @classmethod
    def totals_by_course(cls, session=None, semester=None, programme=None, department=None):
        qs = cls._successful_allocations(session, semester, programme, department).filter(
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
    def totals_by_method(cls, session=None, semester=None, programme=None, department=None):
        """Breakdown by how the money came in (bank transfer, card,
        wallet, etc) — rounds out the accounting picture alongside the
        category/course breakdowns, and is useful for reconciling how
        much of total collection is coming through student wallets."""
        qs = cls._successful_allocations(session, semester, programme, department)
        return (
            qs.values(method=F("payment__method"))
            .annotate(total_collected=Sum("amount"))
            .order_by("-total_collected")
        )

    @classmethod
    def grand_total(cls, session=None, semester=None, programme=None, department=None) -> Decimal:
        return cls._successful_allocations(session, semester, programme, department).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

    @classmethod
    def debtors(cls, session=None, semester=None, programme=None, department=None):
        """
        One row per student with at least one outstanding (unpaid or
        part-paid) PaymentItem in scope: their total amount due, total
        paid, and outstanding balance.

        Computed in Python rather than a single SQL aggregate, since
        `balance`/`is_cleared` are properties derived per-item
        (clearance-threshold percentages differ per FeeAssignment, and a
        course fee's own rule differs from a mandatory fee's) rather than
        a plain column Django can SUM directly. Re-deriving that logic in
        raw SQL here would mean two places could quietly disagree about
        what "owing" means — this keeps PaymentItem as the single source
        of truth and just aggregates its already-correct per-item results.
        """
        qs = PaymentItem.objects.select_related(
            "student", "student__department", "student__programme", "student__level",
            "fee_assignment__category", "course_registration__course",
        ).prefetch_related("allocations__payment")

        if session:
            qs = qs.filter(session=session)
        if semester:
            qs = qs.filter(semester=semester)
        if programme:
            qs = qs.filter(student__programme=programme)
        if department:
            qs = qs.filter(student__department=department)

        by_student = {}
        for item in qs:
            if item.is_cleared:
                continue
            row = by_student.setdefault(item.student_id, {
                "student": item.student,
                "total_due": Decimal("0.00"),
                "total_paid": Decimal("0.00"),
                "outstanding": Decimal("0.00"),
                "item_count": 0,
            })
            row["total_due"] += item.amount_due or Decimal("0.00")
            row["total_paid"] += item.amount_paid
            row["outstanding"] += item.balance
            row["item_count"] += 1

        return sorted(by_student.values(), key=lambda r: r["outstanding"], reverse=True)

    @classmethod
    def total_outstanding(cls, session=None, semester=None, programme=None, department=None) -> Decimal:
        return sum(
            (row["outstanding"] for row in cls.debtors(session, semester, programme, department)),
            Decimal("0.00"),
        )
