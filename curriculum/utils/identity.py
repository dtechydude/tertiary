from curriculum.models import SchoolIdentity
from students.models import Student


def get_school_identity_for_student(student):
    """
    Returns correct identity based on:
    1. Default school identity
    2. Department override (tertiary logic)
    """

    # fallback
    identity = SchoolIdentity.objects.filter(is_default=True).first() \
        or SchoolIdentity.objects.first()

    try:
        if student and student.department:
            dept_identity = getattr(student.department, "school_identity", None)
            if dept_identity:
                return dept_identity
    except Exception:
        pass

    return identity