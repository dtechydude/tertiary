from rest_framework import permissions


class IsCourseLecturer(permissions.BasePermission):
    """
    Allows access only to a lecturer who is actually assigned to the
    course (for the specific session/semester where relevant).
    """

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and hasattr(request.user, "lecturer")
        )

    def has_object_permission(self, request, view, obj):
        from curriculum.models import CourseAssignment
        return CourseAssignment.objects.filter(
            lecturer=request.user.lecturer,
            course=obj.course,
            session=obj.session,
            semester=obj.semester,
        ).exists()


class IsResultOwner(permissions.BasePermission):
    """Students may only ever read their own results."""

    def has_object_permission(self, request, view, obj):
        return hasattr(request.user, "student") and obj.student_id == request.user.student.id


class CanActOnResultWorkflow(permissions.BasePermission):
    """
    Coarse authentication gate for workflow-action endpoints. The actual
    per-transition permission codename check happens inside
    ResultWorkflowService.transition(), so that rule lives in exactly one
    place rather than being duplicated between the API layer and the
    service layer.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
