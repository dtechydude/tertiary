# tickets/context_processors.py
from .services import pending_admin_reply_count, unseen_activity_count


def unread_tickets_count(request):
    """
    Returns the count of tickets needing the logged-in user's attention,
    for the notification bell.

    - Staff/admin: tickets genuinely awaiting an admin reply (not just
      "never opened" — a ticket someone looked at but never replied to
      still counts).
    - Student/Lecturer: their own tickets with an unseen admin reply,
      plus broadcasts addressed to them they haven't opened yet.
    """
    unread_count = 0
    user = getattr(request, "user", None)

    if user and user.is_authenticated:
        if user.is_staff:
            unread_count = pending_admin_reply_count()
        elif hasattr(user, 'student'):
            unread_count = unseen_activity_count(user, role='students')
        elif hasattr(user, 'lecturer'):
            unread_count = unseen_activity_count(user, role='lecturers')
        else:
            # Logged-in account with neither a student nor lecturer
            # profile (e.g. a bare support account) — just their own
            # submitted tickets, no broadcast audience to match.
            unread_count = unseen_activity_count(user, role=None)

    # Key kept as 'unread_count' (not renamed) since the base template's
    # nav badge already references {{ unread_count }}.
    return {'unread_count': unread_count}
