"""
UI-facing helpers for the result approval workflow.

This module intentionally contains NO business logic of its own — every
state transition still goes through ResultWorkflowService.transition(),
exactly as ResultAdmin's bulk actions already do. What lives here is the
glue that both the admin and the new /results/approvals/ front end need:

  * a single source of truth mapping each workflow action to the
    permission that guards it (so it's never hardcoded in a template or
    duplicated between admin.py and views.py)
  * a lookup of "what's the next action for a result in this status"
  * a bulk-transition runner with the same succeeded/failed bookkeeping
    ResultAdmin._run_bulk_transition already does

Reuse note: ResultAdmin._run_bulk_transition duplicates the loop below.
Consider having it call bulk_transition() from here instead next time
admin.py is touched — not changed as part of this piece of work to avoid
an unrelated, unrequested edit to existing, working code.
"""
from __future__ import annotations

import inspect
from typing import Iterable

from django.core.exceptions import PermissionDenied, ValidationError

from ..models import Result
from .workflow import ResultWorkflowService

# Action key -> permission codename (namespaced with the app label).
# Keep this the single source of truth; nothing else should hardcode
# a permission string or a role name.
ACTION_PERMISSIONS = {
    "submit": "results.submit_result",
    "approve_hod": "results.approve_result_hod",
    "approve_dean": "results.approve_result_dean",
    "approve_registrar": "results.approve_result_registrar",
    "publish": "results.publish_result",
    "return": "results.return_result",
}

# Human-readable labels for buttons/dropdowns — kept alongside the
# permission map so templates never need to know the action strings.
ACTION_LABELS = {
    "submit": "Submit to HOD",
    "approve_hod": "Approve as HOD",
    "approve_dean": "Approve as Dean",
    "approve_registrar": "Approve as Registrar",
    "publish": "Publish",
    "return": "Return for Correction",
}

# For a result sitting in a given status, this is the action that moves
# it forward one stage. Draft and Published have no "next" action —
# draft needs the lecturer to submit it first, published is terminal.
NEXT_ACTION_BY_STATUS = {
    Result.Status.SUBMITTED: "approve_hod",
    Result.Status.HOD_APPROVED: "approve_dean",
    Result.Status.DEAN_APPROVED: "approve_registrar",
    Result.Status.REGISTRAR_APPROVED: "publish",
}

# Any result at these stages can be sent back to the lecturer for
# correction. The workflow service still has the final say — this only
# controls whether the button is offered.
RETURNABLE_STATUSES = {
    Result.Status.SUBMITTED,
    Result.Status.HOD_APPROVED,
    Result.Status.DEAN_APPROVED,
    Result.Status.REGISTRAR_APPROVED,
}


def get_available_actions(result: Result, user) -> list[str]:
    """
    Actions this user is permitted to take on this result right now,
    given its current status. Used to decide which buttons render on
    a row/detail page — never duplicate this logic in a template.
    """
    actions = []

    next_action = NEXT_ACTION_BY_STATUS.get(result.status)
    if next_action and user.has_perm(ACTION_PERMISSIONS[next_action]):
        actions.append(next_action)

    if result.status in RETURNABLE_STATUSES and user.has_perm(ACTION_PERMISSIONS["return"]):
        actions.append("return")

    return actions


def apply_transition(result: Result, action: str, actor, note: str = "") -> None:
    """
    Thin wrapper around ResultWorkflowService.transition(). If the
    service's signature already accepts a `note`/`reason` keyword for
    return-for-correction comments, it's passed through automatically;
    otherwise the call falls back to the same signature ResultAdmin
    uses today, so this never breaks against the current service.
    """
    kwargs = {"actor": actor}
    params = inspect.signature(ResultWorkflowService.transition).parameters
    if note:
        if "note" in params:
            kwargs["note"] = note
        elif "reason" in params:
            kwargs["reason"] = note

    ResultWorkflowService.transition(result, action, **kwargs)


def bulk_transition(queryset: Iterable[Result], action: str, actor, note: str = "") -> tuple[list[int], list[tuple[int, str]]]:
    """
    Runs `action` against every result in `queryset`, the same way
    ResultAdmin._run_bulk_transition does. Returns (succeeded_ids,
    failed) where failed is a list of (result_id, error_message) pairs
    so the caller can report specifics instead of just a count.
    """
    succeeded: list[int] = []
    failed: list[tuple[int, str]] = []

    for result in queryset:
        try:
            apply_transition(result, action, actor, note=note)
            succeeded.append(result.pk)
        except PermissionDenied as exc:
            failed.append((result.pk, str(exc) or "You don't have permission for this stage."))
        except ValidationError as exc:
            failed.append((result.pk, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)))

    return succeeded, failed