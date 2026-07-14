"""
finance.services.fee_resolution
================================

Resolves which FeeAssignments actually apply to a given student for a
session/semester, preferring the most specific scope per category:
level+programme match > programme-only match > fully global. Mirrors the
same resolution philosophy the results app uses for grading schemes, so
an institution never needs special-case code to have one level pay a
different hostel fee than the rest of its programme.
"""

from django.db.models import Q

from ..models import FeeAssignment


def resolve_fee_assignments(student, session, semester):
    """Returns a list of FeeAssignment objects, at most one per category,
    picking the most specific match available for this student."""
    candidates = (
        FeeAssignment.objects.filter(session=session, semester=semester)
        .filter(Q(programme__isnull=True) | Q(programme=student.programme))
        .filter(Q(level__isnull=True) | Q(level=student.level))
        .select_related("category")
    )

    best_by_category = {}
    for assignment in candidates:
        specificity = (assignment.level_id is not None, assignment.programme_id is not None)
        current = best_by_category.get(assignment.category_id)
        if current is None or specificity > current[0]:
            best_by_category[assignment.category_id] = (specificity, assignment)

    return [assignment for _, assignment in best_by_category.values()]
