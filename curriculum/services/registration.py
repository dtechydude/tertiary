"""
curriculum.services.registration
==================================

Resolves the min/max credit-unit policy a student's registration must be
validated against. Kept as a small, dependency-free service so the
`registration` app (or any other caller) can import and use it without
pulling in view/template code.

Resolution order: Level-specific override -> Programme-wide default.
If neither exists, raises so a missing policy is caught during setup
rather than silently allowing unlimited registration.
"""

from django.core.exceptions import ValidationError

from ..models import RegistrationPolicy


def resolve_registration_policy(level) -> RegistrationPolicy:
    level_policy = getattr(level, "registration_policy", None)
    if level_policy:
        return level_policy

    programme_policy = RegistrationPolicy.objects.filter(
        programme=level.programme, level__isnull=True
    ).first()
    if programme_policy:
        return programme_policy

    raise ValidationError(
        f"No RegistrationPolicy configured for level '{level}' or its programme '{level.programme}'. "
        f"Configure one at either the Level or Programme level before allowing registration."
    )


def validate_unit_load(level, total_units_requested: int, is_carryover: bool = False) -> None:
    """
    Raises ValidationError if total_units_requested falls outside the
    resolved policy's min/max — the registration app's course-registration
    validation should call this alongside its other checks (active session,
    payment clearance, prerequisites, duplicate registration, etc.).
    """
    policy = resolve_registration_policy(level)
    effective_max = policy.max_units_per_semester + (policy.max_carryover_units if is_carryover else 0)

    if total_units_requested > effective_max:
        raise ValidationError(
            f"Total requested units ({total_units_requested}) exceed the maximum allowed "
            f"({effective_max}) for {level}."
        )
    if total_units_requested < policy.min_units_per_semester:
        raise ValidationError(
            f"Total requested units ({total_units_requested}) fall below the minimum required "
            f"({policy.min_units_per_semester}) for {level}."
        )
