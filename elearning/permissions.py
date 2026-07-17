"""
tertiary_elearning.permissions
================================

Small, dependency-free access-check helpers. No new roles/groups are
introduced — access is derived from data that already exists in the
`curriculum` app:

  - A user can MANAGE a course's e-learning content if they are staff,
    or a lecturer assigned to that course this session/semester
    (curriculum.CourseAssignment).
  - A user can VIEW a course's e-learning content if they can manage it,
    OR they are a student currently registered for that course
    (curriculum.CourseRegistration).
"""

from curriculum.models import CourseAssignment, CourseRegistration


def _lecturer_profile(user):
    return getattr(user, "lecturer", None)


def _student_profile(user):
    return getattr(user, "student", None)


def can_manage_course(user, course):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True

    lecturer = _lecturer_profile(user)
    if lecturer is None:
        return False
    return CourseAssignment.objects.filter(lecturer=lecturer, course=course).exists()


def can_view_course(user, course):
    if not user.is_authenticated:
        return False
    if can_manage_course(user, course):
        return True

    student = _student_profile(user)
    if student is None:
        return False
    return CourseRegistration.objects.filter(student=student, course=course).exists()


def registered_courses_for_student(student):
    """Distinct Course queryset a student is currently registered for."""
    from curriculum.models import Course

    course_ids = CourseRegistration.objects.filter(student=student).values_list(
        "course_id", flat=True
    )
    return Course.objects.filter(id__in=course_ids).distinct()


def assigned_courses_for_lecturer(lecturer):
    """Distinct Course queryset a lecturer is currently assigned to teach."""
    from curriculum.models import Course

    course_ids = CourseAssignment.objects.filter(lecturer=lecturer).values_list(
        "course_id", flat=True
    )
    return Course.objects.filter(id__in=course_ids).distinct()
