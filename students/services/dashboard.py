"""
students.services.dashboard
============================

Builds the data behind a student's own "My Profile" page: current
registration, fee clearance, and academic results — pulled from the
curriculum, finance, and results apps. Kept out of views.py so the view
stays thin, per project convention.

Deliberately defensive: a brand-new student may not have any
FeeAssignment, GradingScheme, or Result data configured/generated yet.
Every function here returns a usable, empty-but-valid structure instead
of raising, since a profile page should never 500 for a student who
simply hasn't been billed or graded yet — only real, unexpected errors
should surface.
"""

from curriculum.models import CourseRegistration, Session, Semester


def get_current_period():
    """The institution's current session/semester, as configured in
    curriculum admin — never hardcoded."""
    session = Session.objects.filter(is_current=True).first()
    semester = None
    if session:
        semester = Semester.objects.filter(is_current=True, session=session).first()
    return session, semester


def build_registration_summary(student, session, semester):
    if not session or not semester:
        return {"registrations": [], "total_units": 0}

    from finance.services.exam_eligibility import ExamEligibilityService

    registrations = CourseRegistration.objects.filter(
        student=student, session=session, semester=semester
    ).select_related("course")

    rows = []
    total_units = 0
    for reg in registrations:
        total_units += reg.course.credit_unit
        result = ExamEligibilityService.check(student, reg.course, session, semester)
        rows.append({
            "course": reg.course,
            "is_exam_eligible": result.is_eligible,
            "reasons": result.reasons,
        })

    return {"registrations": rows, "total_units": total_units}


def build_fee_summary(student, session, semester):
    if not session or not semester:
        return {"items": [], "fully_cleared_for_exams": True}

    from finance.services.payments import FinanceService
    from finance.services.exam_eligibility import ExamEligibilityService

    try:
        FinanceService.ensure_semester_fee_items(student, session, semester)
    except Exception:
        # No FeeAssignment configured yet for this session/semester —
        # don't let that break the profile page.
        pass

    return ExamEligibilityService.semester_clearance_summary(student, session, semester)


def build_academic_summary(student, session, semester):
    from results.models import Result
    from results.services.gpa import GPAService

    published_results = Result.objects.filter(
        student=student, is_published=True
    ).select_related("course", "session", "semester").order_by(
        "-session__start_date", "semester"
    )

    semester_gpa = None
    if session and semester:
        semester_gpa = GPAService.calculate_gpa(student, session, semester)

    cgpa = GPAService.calculate_cgpa(student)

    return {
        "results": published_results,
        "semester_gpa": semester_gpa,
        "cgpa": cgpa,
    }


def build_payment_history(student, limit=10):
    from finance.models import Payment

    return Payment.objects.filter(
        student=student, status=Payment.Status.SUCCESSFUL
    ).order_by("-paid_at")[:limit]


def build_outstanding_items(student, session, semester):
    """
    Every unpaid/partially-paid PaymentItem for this student this
    session/semester — course fees for registered courses, plus every
    resolved mandatory/optional fee category. Backs the 'select what to
    pay for' form on the course registration page.
    """
    if not session or not semester:
        return []

    from finance.models import PaymentItem

    items = PaymentItem.objects.filter(
        student=student, session=session, semester=semester
    ).select_related("fee_assignment__category", "course_registration__course")

    rows = []
    for item in items:
        if item.balance <= 0:
            continue  # already fully paid — nothing to offer for payment
        label = (
            item.fee_assignment.category.name
            if item.fee_assignment_id else item.course_registration.course.course_code
        )
        rows.append({
            "id": item.id,
            "label": label,
            "amount_due": item.amount_due,
            "amount_paid": item.amount_paid,
            "balance": item.balance,
            "is_mandatory_for_exam": item.is_mandatory_for_exam,
        })
    return rows


def build_student_dashboard_context(student):
    """Single entry point used by StudentSelfDetailView — assembles
    everything the 'My Profile' page needs in one call."""
    session, semester = get_current_period()

    return {
        "current_session": session,
        "current_semester": semester,
        "registration_summary": build_registration_summary(student, session, semester),
        "fee_summary": build_fee_summary(student, session, semester),
        "academic_summary": build_academic_summary(student, session, semester),
        "recent_payments": build_payment_history(student),
    }
