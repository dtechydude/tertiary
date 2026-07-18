# tickets/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import Comment


@receiver(post_save, sender=Comment)
def notify_author_on_response(sender, instance, created, **kwargs):
    """
    Notifies a ticket's author by email when someone else (typically an
    admin/support staff) replies to it.

    Email sending is left commented out on purpose — enable it once
    SMTP/DEFAULT_FROM_EMAIL is configured for your host, otherwise every
    reply will raise/print a connection error. Uncomment the send_mail
    call below to turn it on.
    """
    if not created:
        return

    ticket = instance.ticket
    if instance.author == ticket.author:
        return  # Don't notify someone about their own comment.

    author_email = ticket.author.email
    if not author_email:
        return

    subject = f"Update on your ticket: {ticket.title}"
    message = (
        f"A new response has been added to your ticket titled '{ticket.title}'.\n\n"
        f"Response: {instance.text}\n"
        f"Log in to the portal and open Support > My Tickets to view the full conversation."
    )

    # send_mail(
    #     subject,
    #     message,
    #     settings.DEFAULT_FROM_EMAIL,
    #     [author_email],
    #     fail_silently=True,
    # )
