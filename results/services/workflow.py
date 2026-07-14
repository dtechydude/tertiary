"""
results.services.workflow
===========================

Encodes the required Lecturer -> HOD -> Dean -> Registrar -> Published
pipeline as an explicit state machine. No view, template, or admin action
needs to know what "the next status" is, or which permission guards it —
that logic lives in exactly one place.

Permissions are checked via Django's standard has_perm() against the
custom permissions declared on Result.Meta.permissions, so roles are
assigned through ordinary Django Groups (HOD, Dean, Registrar, ...) —
never hardcoded to a username or role string.
"""

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone

from ..models import Result, ResultAuditLog


class ResultWorkflowService:

    # current_status: {action: (target_status, required_permission_codename)}
    TRANSITIONS = {
        Result.Status.DRAFT: {
            "submit": (Result.Status.SUBMITTED, "results.submit_result"),
        },
        Result.Status.SUBMITTED: {
            "approve_hod": (Result.Status.HOD_APPROVED, "results.approve_result_hod"),
            "return": (Result.Status.RETURNED, "results.return_result"),
        },
        Result.Status.HOD_APPROVED: {
            "approve_dean": (Result.Status.DEAN_APPROVED, "results.approve_result_dean"),
            "return": (Result.Status.RETURNED, "results.return_result"),
        },
        Result.Status.DEAN_APPROVED: {
            "approve_registrar": (Result.Status.REGISTRAR_APPROVED, "results.approve_result_registrar"),
            "return": (Result.Status.RETURNED, "results.return_result"),
        },
        Result.Status.REGISTRAR_APPROVED: {
            "publish": (Result.Status.PUBLISHED, "results.publish_result"),
            "return": (Result.Status.RETURNED, "results.return_result"),
        },
        Result.Status.RETURNED: {
            "submit": (Result.Status.SUBMITTED, "results.submit_result"),
        },
    }

    @staticmethod
    def log(result: Result, actor, action: str, from_status: str = "", to_status: str = "", remarks: str = ""):
        return ResultAuditLog.objects.create(
            result=result, actor=actor, action=action,
            from_status=from_status, to_status=to_status, remarks=remarks,
        )

    @classmethod
    @transaction.atomic
    def transition(cls, result: Result, action: str, actor, remarks: str = "") -> Result:
        allowed = cls.TRANSITIONS.get(result.status, {})
        move = allowed.get(action)
        if not move:
            raise ValidationError(
                f"'{action}' is not a valid transition from status '{result.get_status_display()}'."
            )

        target_status, required_perm = move

        if actor is None or not actor.has_perm(required_perm):
            raise PermissionDenied(f"You do not have permission to '{action}' this result.")

        from_status = result.status
        result.status = target_status
        update_fields = ["status", "updated_at"]

        if action == "submit":
            result.submitted_by = actor
            result.submitted_at = timezone.now()
            update_fields += ["submitted_by", "submitted_at"]
        if action == "publish":
            result.is_published = True
            result.published_at = timezone.now()
            update_fields += ["is_published", "published_at"]
        if action == "return":
            result.is_published = False
            update_fields += ["is_published"]

        result.save(update_fields=update_fields)

        cls.log(result, actor=actor, action=action,
                from_status=from_status, to_status=target_status, remarks=remarks)
        return result

    @classmethod
    @transaction.atomic
    def bulk_transition(cls, results_qs, action: str, actor, remarks: str = "") -> list:
        """For an HOD/Dean/Registrar approving an entire course or
        department's results in one action instead of one at a time."""
        return [
            cls.transition(result, action, actor, remarks)
            for result in results_qs.select_for_update()
        ]
