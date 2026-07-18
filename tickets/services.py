# tickets/services.py
"""
Two distinct concepts drive everything in this file, and conflating them
was the root cause of the notification bell/list badges not working:

1. NEEDS A REPLY (ticket-level fact, not tied to any specific viewer):
   the ticket is still Open/In Progress and its most recent comment (if
   any) was written by the ticket's own author rather than by staff —
   i.e. the ball is in staff's court. This does NOT go away just because
   a staff member opened the ticket without replying — "I looked at it"
   isn't the same as "I responded to it".

2. UNSEEN ACTIVITY (viewer-specific): whether there's activity on a
   ticket since a given user last viewed it — via TicketReadStatus vs.
   the timestamp of the ticket's most recent comment. This is what makes
   a ticket the *author* is watching light up when staff finally reply.

The previous version only ever tracked "has this user EVER opened this
ticket" (a permanent one-way flag) — so once viewed, a ticket was
considered read forever, even after a brand new reply came in. Comparing
timestamps instead of a boolean fixes that without needing to delete/
reset any read-status rows.
"""

from django.db.models import F, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce

from .models import Comment, Ticket, TicketReadStatus


def _with_last_comment_info(queryset):
    """Annotate with the timestamp + admin-authored flag of each ticket's
    most recent comment (both None if the ticket has no comments yet)."""
    last_comment_at = (
        Comment.objects.filter(ticket=OuterRef('pk')).order_by('-created_at').values('created_at')[:1]
    )
    last_comment_is_admin = (
        Comment.objects.filter(ticket=OuterRef('pk')).order_by('-created_at').values('is_admin_response')[:1]
    )
    return queryset.annotate(
        last_comment_at=Subquery(last_comment_at),
        last_comment_is_admin=Subquery(last_comment_is_admin),
    )


def _with_read_status(queryset, user):
    """Annotate with when `user` last viewed each ticket (None = never)."""
    read_at = TicketReadStatus.objects.filter(user=user, ticket=OuterRef('pk')).values('read_at')[:1]
    return queryset.annotate(my_read_at=Subquery(read_at))


def annotate_reply_status(tickets, user):
    """
    Attach three flags to each ticket in an already-fetched list/page of
    tickets, for use in list-page badges:

      - needs_reply:       ball is in staff's court (see module docstring)
      - has_unseen_reply:  there's an admin reply this user hasn't seen yet
      - has_unseen_broadcast: an announcement this user hasn't opened yet

    Pass in a small, already-paginated list (e.g. one page of results) —
    this re-queries per ticket ID, so it's meant for small batches, not
    an entire table.
    """
    ticket_ids = [t.pk for t in tickets]
    if not ticket_ids:
        return tickets

    annotated_qs = _with_read_status(
        _with_last_comment_info(Ticket.objects.filter(pk__in=ticket_ids)), user
    )
    info_by_id = {t.pk: t for t in annotated_qs}

    for ticket in tickets:
        info = info_by_id.get(ticket.pk)
        if info is None:
            continue

        if ticket.is_broadcast:
            ticket.needs_reply = False
            ticket.has_unseen_reply = False
            ticket.has_unseen_broadcast = info.my_read_at is None
            continue

        ticket.has_unseen_broadcast = False
        ticket.needs_reply = (
            ticket.status not in ('Resolved', 'Closed') and not info.last_comment_is_admin
        )
        ticket.has_unseen_reply = bool(
            info.last_comment_is_admin
            and (info.my_read_at is None or info.last_comment_at > info.my_read_at)
        )

    return tickets


def pending_admin_reply_count():
    """
    Tickets (non-broadcast, not Resolved/Closed) whose most recent
    comment isn't from staff — i.e. genuinely awaiting an admin response.
    This is the staff/admin notification bell count.
    """
    qs = _with_last_comment_info(
        Ticket.objects.filter(is_broadcast=False).exclude(status__in=['Resolved', 'Closed'])
    )
    return qs.filter(
        Q(last_comment_is_admin=False) | Q(last_comment_is_admin__isnull=True)
    ).count()


def unseen_activity_count(user, role=None):
    """
    Tickets/broadcasts relevant to `user` with activity they haven't seen
    yet — a new admin reply on their own ticket, or a broadcast they've
    never opened. `role` is 'students' or 'lecturers' (matches
    Ticket.AUDIENCE_CHOICES) so relevant broadcasts are included too; pass
    None to only consider the user's own submitted tickets.
    This is the student/lecturer notification bell count.
    """
    audience_values = ['all'] + ([role] if role else [])
    base = Ticket.objects.filter(
        Q(author=user) | Q(is_broadcast=True, audience__in=audience_values)
    ).distinct()
    base = _with_read_status(_with_last_comment_info(base), user)
    base = base.annotate(last_activity_at=Coalesce('last_comment_at', 'created_at'))

    return base.filter(
        Q(my_read_at__isnull=True) | Q(last_activity_at__gt=F('my_read_at'))
    ).count()
