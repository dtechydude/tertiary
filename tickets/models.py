from django.db import models
from django.contrib.auth.models import User


class Ticket(models.Model):
    STATUS_CHOICES = (
        ('Open', 'Open'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
        ('Closed', 'Closed'),
    )

    PRIORITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    )

    # Tertiary-institution categories — added Course Registration, Examinations
    # & Results, Hostel/Accommodation and ID Card, on top of the general ones
    # that already carried over cleanly from the K-12 version.
    CATEGORY_CHOICES = (
        ('Course Registration', 'Course Registration'),
        ('Examinations & Results', 'Examinations & Results'),
        ('Academic', 'Academic (Other)'),
        ('Financial Aid', 'Financial Aid / Bursary'),
        ('Hostel/Accommodation', 'Hostel / Accommodation'),
        ('ID Card', 'ID Card'),
        ('Technical Support', 'Technical Support (Portal/ICT)'),
        ('Facilities', 'Facilities'),
        ('General Inquiry', 'General Inquiry'),
    )

    # 'teachers' -> 'lecturers': this app was adapted from a K-12 project where
    # the only non-student portal role was "Teacher". In the tertiary portal
    # the equivalent role is "Lecturer" (see staff.Lecturer / user.lecturer
    # used everywhere else in the project).
    AUDIENCE_CHOICES = [
        ('all', 'All Users'),
        ('lecturers', 'Lecturers'),
        ('students', 'Students'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()

    # related_name is deliberately non-default ('tickets_submitted') to avoid
    # clashing with any other app's "ticket"/"comment" relations on User.
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets_submitted')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_assigned')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='General Inquiry')

    is_broadcast = models.BooleanField(default=False)
    audience = models.CharField(
        max_length=20,
        choices=AUDIENCE_CHOICES,
        default='all',
        blank=True,
        help_text="Who a broadcast ticket/announcement is addressed to. Ignored for regular tickets.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Ticket #{self.id}: {self.title}"


class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ticket_comments')
    text = models.TextField()
    is_admin_response = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author} on {self.ticket}"


class TicketReadStatus(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Ticket Read Statuses'
        unique_together = ('user', 'ticket')

    def __str__(self):
        return f"{self.user.username} read {self.ticket.title}"
