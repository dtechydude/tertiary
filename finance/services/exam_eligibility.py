"""
finance.services.exam_eligibility
===================================

The gate: can this student sit the exam for this course, this semester?
Combines the course's own fee (if any) with every fee category the
institution has flagged `is_mandatory_for_exam=True`. This is what
enforces "courses that are not registered and paid for will not be able
to take exams for them."
"""

from dataclasses import dataclass, field
from typing import List

from ..models import PaymentItem


@dataclass
class ExamEligibilityResult:
    is_eligible: bool
    outstanding_items: List[PaymentItem] = field(default_factory=list)


class ExamEligibilityService:

    @staticmethod
    def check(student, course, session, semester) -> ExamEligibilityResult:
        outstanding = []

        course_item = PaymentItem.objects.filter(
            course_registration__student=student,
            course_registration__course=course,
            course_registration__session=session,
            course_registration__semester=semester,
        ).select_related("fee_assignment").first()
        if course_item and not course_item.is_cleared:
            outstanding.append(course_item)

        mandatory_items = PaymentItem.objects.filter(
            student=student, session=session, semester=semester,
            fee_assignment__is_mandatory_for_exam=True,
        ).select_related("fee_assignment__category")
        outstanding.extend(item for item in mandatory_items if not item.is_cleared)

        return ExamEligibilityResult(is_eligible=not outstanding, outstanding_items=outstanding)

    @classmethod
    def is_course_exam_eligible(cls, student, course, session, semester) -> bool:
        return cls.check(student, course, session, semester).is_eligible

    @staticmethod
    def semester_clearance_summary(student, session, semester) -> dict:
        """Every billable item for this student this semester, cleared or
        not — backs a student-facing 'my fees' screen."""
        items = PaymentItem.objects.filter(
            student=student, session=session, semester=semester
        ).select_related("fee_assignment__category", "course_registration__course")

        rows = []
        for item in items:
            label = (
                item.fee_assignment.category.name
                if item.fee_assignment_id else item.course_registration.course.course_code
            )
            rows.append({
                "label": label,
                "amount_due": item.amount_due,
                "amount_paid": item.amount_paid,
                "balance": item.balance,
                "is_cleared": item.is_cleared,
                "is_mandatory_for_exam": item.is_mandatory_for_exam,
            })

        return {
            "items": rows,
            "fully_cleared_for_exams": all(row["is_cleared"] for row in rows if row["is_mandatory_for_exam"]),
        }

    @classmethod
    def course_attendance_list(cls, course, session, semester) -> list:
        """
        Every student registered for a course, with their exam
        eligibility — the list an invigilator/registrar uses to decide
        who is actually admitted to sit the paper. A natural candidate to
        relocate into a dedicated `examinations` app later; it lives here
        for now since eligibility itself is computed here.
        """
        from curriculum.models import CourseRegistration
        registrations = CourseRegistration.objects.filter(
            course=course, session=session, semester=semester
        ).select_related("student")

        rows = []
        for reg in registrations:
            result = cls.check(reg.student, course, session, semester)
            rows.append({
                "student": reg.student,
                "is_eligible": result.is_eligible,
                "outstanding_items": result.outstanding_items,
            })
        return rows
