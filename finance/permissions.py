from rest_framework import permissions


class IsFinanceStaff(permissions.BasePermission):
    """Bursary/registrar staff who can record payments on a student's behalf."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.has_perm("finance.record_payment")
        )


class CanViewFinanceReports(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.has_perm("finance.view_finance_reports")
        )


class IsOwnerStudentOrFinanceStaff(permissions.BasePermission):
    """A student may view their own fee/payment data; staff with the
    finance permission may view anyone's."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        student = getattr(request.user, "student", None)
        if student and getattr(obj, "student_id", None) == student.id:
            return True
        return request.user.has_perm("finance.record_payment") or request.user.has_perm("finance.view_finance_reports")
