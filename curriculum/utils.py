from curriculum.models import SchoolIdentity, AcademicIdentityMapping


def get_student_identity(student):
    """
    Returns correct identity for a student based on:
    Department → Faculty → Default
    """

    # 1. Department override
    dept_mapping = AcademicIdentityMapping.objects.filter(
        department=student.department
    ).select_related('school_identity').first()

    if dept_mapping:
        return dept_mapping.school_identity

    # 2. Faculty fallback
    faculty = getattr(student.department, 'faculty', None)

    if faculty:
        faculty_mapping = AcademicIdentityMapping.objects.filter(
            faculty=faculty
        ).select_related('school_identity').first()

        if faculty_mapping:
            return faculty_mapping.school_identity

    # 3. Default identity
    return SchoolIdentity.objects.filter(is_default=True).first()