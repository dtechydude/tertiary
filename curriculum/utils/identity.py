# from curriculum.models import SchoolIdentity
# from students.models import Student


# def get_school_identity_for_student(student):
#     """
#     Returns correct identity based on:
#     1. Default school identity
#     2. Department override (tertiary logic)
#     """

#     # fallback
#     identity = SchoolIdentity.objects.filter(is_default=True).first() \
#         or SchoolIdentity.objects.first()

#     try:
#         if student and student.department:
#             dept_identity = getattr(student.department, "school_identity", None)
#             if dept_identity:
#                 return dept_identity
#     except Exception:
#         pass

#     return identity

# curriculum/utils/identity.py
from curriculum.models import AcademicIdentityMapping, SchoolIdentity


def get_school_identity_for_department(department):
    """
    Core resolver: Department override -> Faculty override -> Default ->
    any identity at all. This is the one place the fallback chain lives —
    student/lecturer/context-processor code all call this instead of each
    re-implementing (and potentially re-diverging from) the same logic.

    Safe to call with department=None (e.g. a student not yet assigned to
    a department) — skips straight to the default/fallback instead of
    querying AcademicIdentityMapping with department=None, which could
    otherwise match an unrelated faculty-only mapping row that happens to
    also have a null department.
    """
    if department is not None:
        dept_mapping = (
            AcademicIdentityMapping.objects.filter(department=department)
            .select_related('school_identity')
            .first()
        )
        if dept_mapping:
            return dept_mapping.school_identity

        faculty = getattr(department, 'faculty', None)
        if faculty is not None:
            faculty_mapping = (
                AcademicIdentityMapping.objects.filter(faculty=faculty)
                .select_related('school_identity')
                .first()
            )
            if faculty_mapping:
                return faculty_mapping.school_identity

    # Default identity, then any identity at all, so callers never get
    # back None just because nobody's flagged a default yet.
    return (
        SchoolIdentity.objects.filter(is_default=True).first()
        or SchoolIdentity.objects.first()
    )


def get_school_identity_for_student(student):
    """
    Matches the name StudentIDCardView already imports — the previous
    utils file defined `get_student_identity` instead, which raised an
    ImportError the moment anything imported that view.
    """
    department = getattr(student, 'department', None)
    return get_school_identity_for_department(department)


def get_school_identity_for_lecturer(lecturer):
    """Same resolver, for staff ID cards / lecturer-facing pages."""
    department = getattr(lecturer, 'department', None)
    return get_school_identity_for_department(department)