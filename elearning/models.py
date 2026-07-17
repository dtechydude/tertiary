"""
tertiary_elearning.models
==========================

Independent e-learning app for a tertiary institution (polytechnic /
university / college of health sciences etc.) with multiple schools —
Engineering, Medicine/Nursing, Social Sciences, Management, and so on.

This app does NOT touch or redefine the institution's academic structure.
It plugs into the existing `curriculum` app's models — `Course`,
`CourseAssignment`, `CourseRegistration`, `Session`, `Semester` — via
loose (string) foreign keys, the same pattern already used elsewhere in
the project (see curriculum.models.CourseRegistration -> "students.Student").

Why a Course-centred design instead of the old K-12 "Standard / Subject"
pairing:
  - In the K-12 app, a "Level" (a class, e.g. JSS1) had several
    "ELearningSubject" rows (Maths, English...), and each subject had
    "Lesson" rows. That mirrors a single class taking many subjects.
  - In a tertiary institution, the natural equivalent of a "subject" is
    already the `Course` model in `curriculum` (e.g. "NUR201 - Maternal
    Health", "MEE305 - Thermodynamics", "ACC101 - Financial Accounting").
    A course already carries its own Programme, Department, Level,
    Session and Semester, so there is no need for a second "subject"
    layer — it just adds duplicate data entry for the school.

Kept deliberately simple, per the project's hosting constraints
(PythonAnywhere free tier / shared cPanel Python app):
  - No rich-text editor package (django-ckeditor / tinymce / etc.).
    Plain TextField for descriptions — safe, dependency-free, fast to
    install on a restricted host.
  - No embed_video package. Lecturers paste a normal YouTube / Google
    Drive / Vimeo link in a URLField; templates handle basic YouTube
    embedding with a simple oEmbed-friendly iframe, everything else is
    shown as a plain "Watch video" link.
  - No OAuth / API integration for Google Classroom or Microsoft Teams.
    Both are handled the "static link" way: a lecturer/admin pastes the
    Google Classroom invite link (and class code) or the Microsoft
    Teams class/meeting link once, and the app just displays a
    "Join on Google Classroom" / "Join on Microsoft Teams" button.
    This works with the free Google Workspace for Education and
    Microsoft Teams for Education tiers and needs zero server-side
    credentials, background jobs, or webhooks.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.db import models


MATERIAL_TYPE_CHOICES = (
    ("video", "Video"),
    ("document", "Document / Slides"),
    ("note", "Written Note"),
    ("link", "External Link / Resource"),
)

PLATFORM_CHOICES = (
    ("google_classroom", "Google Classroom"),
    ("ms_teams", "Microsoft Teams"),
)


def material_upload_path(instance, filename):
    """Keeps uploads namespaced by course so a shared-hosting media
    folder doesn't turn into one giant flat directory."""
    course_code = getattr(instance.course, "course_code", "misc")
    return f"elearning/{slugify(course_code)}/{filename}"


class CourseMaterial(models.Model):
    """
    A single unit of e-learning content for a course — a recorded
    lecture, a slide deck, a PDF handout, a written note, or a link to
    an external resource. Equivalent to the old K-12 "Lesson", but
    attached directly to a tertiary `Course` instead of a
    Level+Subject pair.
    """

    course = models.ForeignKey(
        "curriculum.Course",
        on_delete=models.CASCADE,
        related_name="elearning_materials",
    )

    title = models.CharField(max_length=250)
    material_type = models.CharField(
        max_length=20, choices=MATERIAL_TYPE_CHOICES, default="note"
    )
    week_number = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Week / Position",
        help_text="Used to order material within the course, e.g. Week 1, Week 2.",
    )

    description = models.TextField(
        blank=True,
        help_text="Plain text notes/summary. Keep formatting simple — no rich text editor required.",
    )
    video_url = models.URLField(
        blank=True,
        verbose_name="Video link",
        help_text="Paste a YouTube, Google Drive, or Vimeo link.",
    )
    file = models.FileField(
        upload_to=material_upload_path,
        blank=True,
        null=True,
        verbose_name="Attachment (PDF, slides, doc, etc.)",
    )
    external_link = models.URLField(
        blank=True, help_text="Any other external resource link."
    )

    is_published = models.BooleanField(
        default=True,
        help_text="Uncheck to save as a draft, hidden from students.",
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_course_materials",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    slug = models.SlugField(max_length=280, blank=True)

    class Meta:
        ordering = ["course", "week_number", "-created_at"]
        verbose_name = "Course Material"
        verbose_name_plural = "Course Materials"

    def __str__(self):
        return f"{self.course.course_code} — {self.title}"

    def clean(self):
        if not any([self.description, self.video_url, self.file, self.external_link]):
            raise ValidationError(
                "Add at least one of: description, video link, file, or external link."
            )

    def save(self, *args, **kwargs):
        base = f"{self.course.course_code}-{self.title}"
        self.slug = slugify(base)[:280]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("elearning:material_detail", kwargs={"pk": self.pk})

    @property
    def youtube_embed_url(self):
        """Best-effort conversion of a common YouTube URL into an embeddable one.
        Returns None if it doesn't look like YouTube — templates fall back to a
        plain link in that case."""
        url = self.video_url
        if not url:
            return None
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[-1].split("?")[0]
            return f"https://www.youtube.com/embed/{video_id}"
        if "watch?v=" in url:
            video_id = url.split("watch?v=")[-1].split("&")[0]
            return f"https://www.youtube.com/embed/{video_id}"
        return None


class OnlineClassLink(models.Model):
    """
    A simple, static link to a live/virtual class for a course — either
    a Google Classroom (free, Education tier) or Microsoft Teams
    (Teams for Education, free tier) class. No API keys or OAuth: the
    lecturer/admin pastes the invite link once, students click to join.
    """

    course = models.ForeignKey(
        "curriculum.Course",
        on_delete=models.CASCADE,
        related_name="online_class_links",
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    label = models.CharField(
        max_length=150,
        blank=True,
        help_text="Optional display name, e.g. 'Weekly Lecture' or 'Lab Session'.",
    )
    join_link = models.URLField(
        help_text=(
            "Paste the Google Classroom invite link (classroom.google.com/c/...) "
            "or the Microsoft Teams class/meeting link here."
        )
    )
    class_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Optional. Google Classroom class code, shown for students who join manually.",
    )
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["course", "platform"]
        verbose_name = "Online Class Link"
        verbose_name_plural = "Online Class Links"

    def __str__(self):
        platform_name = dict(PLATFORM_CHOICES).get(self.platform, self.platform)
        return f"{self.course.course_code} — {platform_name}"

    @property
    def display_name(self):
        platform_name = dict(PLATFORM_CHOICES).get(self.platform, self.platform)
        return self.label or platform_name


class MaterialComment(models.Model):
    """A student/lecturer question or note left under a course material."""

    material = models.ForeignKey(
        CourseMaterial, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.material}"


class MaterialReply(models.Model):
    """A reply to a comment — usually the lecturer answering a student question."""

    comment = models.ForeignKey(
        MaterialComment, on_delete=models.CASCADE, related_name="replies"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Reply by {self.author} to comment #{self.comment_id}"
