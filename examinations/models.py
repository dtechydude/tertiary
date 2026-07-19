"""
examinations.models
====================

Owns exam scheduling (the timetable) — venues, dates, times, and
invigilators. Exam *eligibility* (can this student sit this exam) stays
in the finance app, since it's fundamentally a fee/validation question;
this app answers "when and where", not "who's allowed in".
"""

from django.core.exceptions import ValidationError
from django.db import models

from curriculum.models import Course, Session, Semester


class ExamVenue(models.Model):
    name = models.CharField(max_length=100, unique=True)
    capacity = models.PositiveIntegerField(default=50)
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Exam Venue"
        verbose_name_plural = "Exam Venues"

    def __str__(self):
        return f"{self.name} (Capacity: {self.capacity})"


class ExamSchedule(models.Model):
    """One exam sitting: a course, a date/time, a venue, and whoever is
    invigilating it. One schedule per course per session/semester."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="exam_schedules")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="exam_schedules")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name="exam_schedules")
    venue = models.ForeignKey(ExamVenue, on_delete=models.SET_NULL, null=True, blank=True, related_name="exam_schedules")

    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    invigilators = models.ManyToManyField(
        "staff.Lecturer", blank=True, related_name="invigilation_duties",
    )
    instructions = models.TextField(
        blank=True,
        help_text="Special instructions shown on the student timetable, e.g. 'Bring your calculator.'",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("course", "session", "semester")
        ordering = ["exam_date", "start_time"]
        indexes = [models.Index(fields=["session", "semester", "exam_date"])]
        verbose_name = "Exam Schedule"
        verbose_name_plural = "Exam Schedules"

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Start time must be before end time.")

        if self.venue_id and self.exam_date and self.start_time and self.end_time:
            clashes = ExamSchedule.objects.filter(
                venue_id=self.venue_id, exam_date=self.exam_date,
            ).exclude(pk=self.pk).filter(
                start_time__lt=self.end_time, end_time__gt=self.start_time,
            )
            if clashes.exists():
                raise ValidationError(
                    f"{self.venue} is already booked for an overlapping time on {self.exam_date}."
                )

    def __str__(self):
        return f"{self.course.course_code} — {self.exam_date} {self.start_time.strftime('%H:%M')}"
