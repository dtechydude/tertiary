"""
finance.services.exam_eligibility
===================================

The gate: can this student sit the exam for this course, this semester?
Two independent conditions must both hold:
  1. Fee clearance — the course's own fee (if any) and every fee category
     flagged `is_mandatory_for_exam=True` are paid off.
  2. Registrar validation — curriculum.CourseRegistration.is_validated is
     True. Registering and paying doesn't automatically grant exam
     eligibility; a registrar must explicitly sign off on the
     registration itself (course allocation correct, no clashes, etc.).

This is what enforces "courses that are not registered, not validated,
and not paid for will not be able to take exams for them."
"""

from dataclasses import dataclass, field
from typing import List

from ..models import PaymentItem


@dataclass
class ExamEligibilityResult:
    is_eligible: bool
    is_registered: bool = True
    is_validated: bool = True
    outstanding_items: List[PaymentItem] = field(default_factory=list)

    @property
    def reasons(self) -> List[str]:
        """Human-readable reasons this student is/isn't eligible — used
        by the registration slip and attendance list so 'No' never shows
        up unexplained."""
        if not self.is_registered:
            return ["Not registered for this course/semester."]

        reasons = []
        if not self.is_validated:
            reasons.append("Registration pending registrar validation.")
        for item in self.outstanding_items:
            label = (
                item.fee_assignment.category.name
                if item.fee_assignment_id else item.course_registration.course.course_code
            )
            reasons.append(f"Outstanding: {label} (₦{item.balance})")
        return reasons


class ExamEligibilityService:

    @staticmethod
    def check(student, course, session, semester) -> ExamEligibilityResult:
        from curriculum.models import CourseRegistration

        registration = CourseRegistration.objects.filter(
            student=student, course=course, session=session, semester=semester
        ).first()

        if not registration:
            return ExamEligibilityResult(is_eligible=False, is_registered=False, is_validated=False)

        outstanding = []

        course_item = PaymentItem.objects.filter(
            course_registration=registration
        ).select_related("fee_assignment").first()
        if course_item and not course_item.is_cleared:
            outstanding.append(course_item)

        mandatory_items = PaymentItem.objects.filter(
            student=student, session=session, semester=semester,
            fee_assignment__is_mandatory_for_exam=True,
        ).select_related("fee_assignment__category")
        outstanding.extend(item for item in mandatory_items if not item.is_cleared)

        is_eligible = (not outstanding) and registration.is_validated

        return ExamEligibilityResult(
            is_eligible=is_eligible,
            is_registered=True,
            is_validated=registration.is_validated,
            outstanding_items=outstanding,
        )

    @classmethod
    def is_course_exam_eligible(cls, student, course, session, semester) -> bool:
        return cls.check(student, course, session, semester).is_eligible

    @staticmethod
    def semester_clearance_summary(student, session, semester) -> dict:
        """Every billable item for this student this semester, cleared or
        not — backs a student-facing 'my fees' screen. (Registration
        validation status is shown separately, per-course, since it's not
        a billable item — see course_attendance_list / the registration
        slip for that.)"""
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
                "is_validated": result.is_validated,
                "reasons": result.reasons,
                "outstanding_items": result.outstanding_items,
            })
        return rows
