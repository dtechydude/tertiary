from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .models import Ticket, Comment, TicketReadStatus
from .forms import TicketForm, CommentForm, BroadcastTicketForm
from .services import annotate_reply_status
from django.core.paginator import Paginator, EmptyPage
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


@login_required
def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.author = request.user
            ticket.save()

            messages.success(request, 'Your ticket has been submitted successfully!')

            # Notify admins by email. Wrapped in try/except so a broken email
            # backend (very common on free hosting until SMTP is configured)
            # never blocks the ticket from being created.
            try:
                ticket_url = request.build_absolute_uri(
                    f'/tickets/admin/{ticket.id}/'
                )
                subject = f'New Support Ticket: {ticket.title}'
                message = (
                    f'A new support ticket has been submitted by '
                    f'{request.user.get_full_name() or request.user.username} '
                    f'({request.user.username}).\n\n'
                    f'Ticket ID: #{ticket.id}\n'
                    f'Category: {ticket.get_category_display()}\n'
                    f'Priority: {ticket.get_priority_display()}\n\n'
                    f'View Ticket: {ticket_url}'
                )
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = list(
                    User.objects.filter(is_staff=True).exclude(email='').values_list('email', flat=True)
                )
                if recipient_list:
                    send_mail(subject, message, from_email, recipient_list)
            except Exception as e:
                # Never let a broken mail backend block ticket creation.
                print(f"Error sending ticket notification email: {e}")

            return redirect('tickets:ticket_list')
    else:
        form = TicketForm()

    return render(request, 'tickets/create_ticket.html', {'form': form})


@login_required
def ticket_list(request):
    user = request.user
    user_tickets = Ticket.objects.filter(author=user)

    # Determine the user's audience based on their role. Fixed from the
    # K-12 version, which checked `hasattr(user, 'teacher')` — an attribute
    # that doesn't exist on this project's User model (it's `lecturer`),
    # so lecturers never matched and never saw broadcasts addressed to them.
    if hasattr(user, 'student'):
        role = 'students'
    elif hasattr(user, 'lecturer'):
        role = 'lecturers'
    else:
        role = None

    all_tickets = Ticket.objects.filter(
        Q(author=user) |
        Q(is_broadcast=True, audience='all') |
        Q(is_broadcast=True, audience=role)
    ).distinct().order_by('-created_at')

    paginator = Paginator(all_tickets, 10)
    page_number = request.GET.get('page')
    try:
        tickets = paginator.page(page_number)
    except EmptyPage:
        tickets = paginator.page(paginator.num_pages)
    except Exception:
        tickets = paginator.page(1)

    # Attach .needs_reply / .has_unseen_reply / .has_unseen_broadcast to
    # each ticket on this page, so the template can show "New Reply" /
    # "Awaiting Response" badges instead of no indicator at all.
    tickets.object_list = annotate_reply_status(list(tickets.object_list), user)

    return render(request, 'tickets/ticket_list.html', {'tickets': tickets})


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)

    # Authorization check — previously missing entirely, so any logged-in
    # user could view any other user's ticket just by guessing/incrementing
    # the URL. A ticket is visible here only to its author, staff, or (for
    # broadcasts) users in the addressed audience.
    user = request.user
    is_owner = ticket.author_id == user.id
    is_relevant_broadcast = ticket.is_broadcast and (
        ticket.audience == 'all'
        or (ticket.audience == 'students' and hasattr(user, 'student'))
        or (ticket.audience == 'lecturers' and hasattr(user, 'lecturer'))
    )
    if not (is_owner or is_relevant_broadcast or user.is_staff):
        raise PermissionDenied("You don't have access to this ticket.")

    comments = Comment.objects.filter(ticket=ticket).order_by('created_at')

    # Always mark as read for whoever is viewing it, broadcast or not.
    # The old condition (`not ticket.is_broadcast or request.user.is_staff`)
    # meant a non-staff user viewing a BROADCAST never got a read-status
    # row created at all — so broadcasts stayed permanently "unread" for
    # every student/lecturer even after they'd opened and read them.
    TicketReadStatus.objects.update_or_create(
        user=request.user,
        ticket=ticket
    )

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.author = request.user
            comment.ticket = ticket
            # Determined by the actual user, not by which of the two
            # (near-identical) views happened to handle the request —
            # previously this was hardcoded True in admin_ticket_detail
            # and always False here, so a staff member replying via this
            # view (rather than the /admin/ one) would incorrectly count
            # as a "user reply" for notification purposes.
            comment.is_admin_response = request.user.is_staff
            comment.save()
            return redirect('tickets:ticket_detail', pk=ticket.pk)
    else:
        form = CommentForm()

    context = {
        'ticket': ticket,
        'comments': comments,
        'form': form,
    }
    return render(request, 'tickets/ticket_detail.html', context)


# ---------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------

@login_required
def admin_ticket_list(request):
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('pages:portal-home')

    selected_category = request.GET.get('category')

    if selected_category:
        all_tickets = Ticket.objects.filter(category=selected_category).order_by('-created_at')
    else:
        all_tickets = Ticket.objects.all().order_by('-created_at')

    paginator = Paginator(all_tickets, 10)
    page_number = request.GET.get('page')
    try:
        tickets = paginator.page(page_number)
    except EmptyPage:
        tickets = paginator.page(paginator.num_pages)
    except Exception:
        tickets = paginator.page(1)

    # Attach .needs_reply to each ticket on this page for the "Pending
    # Response" badge in the admin table.
    tickets.object_list = annotate_reply_status(list(tickets.object_list), request.user)

    categories = Ticket.CATEGORY_CHOICES

    return render(request, 'tickets/admin_ticket_list.html', {
        'tickets': tickets,
        'categories': categories,
        'selected_category': selected_category
    })


@login_required
def admin_ticket_detail(request, pk):
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('pages:portal-home')

    ticket = get_object_or_404(Ticket, pk=pk)
    comments = ticket.comments.all().order_by('created_at')

    if request.method == 'POST':
        # These three actions were present as buttons in the template but
        # only "close_ticket" was actually handled here — "Assign to Me"
        # and "Mark as Resolved" silently did nothing. All three are wired
        # up now.
        if 'assign_ticket' in request.POST:
            ticket.assigned_to = request.user
            if ticket.status == 'Open':
                ticket.status = 'In Progress'
            ticket.save()
            messages.success(request, 'Ticket assigned to you.')
            return redirect('tickets:admin_ticket_detail', pk=pk)

        if 'resolve_ticket' in request.POST:
            ticket.status = 'Resolved'
            ticket.save()
            messages.success(request, 'Ticket marked as resolved.')
            return redirect('tickets:admin_ticket_detail', pk=pk)

        if 'close_ticket' in request.POST:
            if ticket.status != 'Closed':
                ticket.status = 'Closed'
                ticket.save()
                messages.success(request, 'Ticket has been successfully closed.')
            return redirect('tickets:admin_ticket_detail', pk=pk)

        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.ticket = ticket
            comment.author = request.user
            comment.is_admin_response = True
            comment.save()
            messages.success(request, 'Your response has been sent to the ticket author.')
            return redirect('tickets:admin_ticket_detail', pk=pk)
    else:
        form = CommentForm()

    return render(request, 'tickets/admin_ticket_detail.html', {
        'ticket': ticket,
        'comments': comments,
        'form': form
    })


def is_admin(user):
    return user.is_staff


@login_required
@user_passes_test(is_admin)
def broadcast_ticket_create(request):
    if request.method == 'POST':
        form = BroadcastTicketForm(request.POST)
        if form.is_valid():
            broadcast_ticket = form.save(commit=False)
            broadcast_ticket.is_broadcast = True
            broadcast_ticket.author = request.user
            broadcast_ticket.save()

            messages.success(request, "Broadcast sent successfully.")
            return redirect('tickets:admin_ticket_list')
    else:
        form = BroadcastTicketForm()

    return render(request, 'tickets/broadcast_ticket_form.html', {'form': form})
