"""
results.models
==============

Design goals (see project instructions):
  - No fixed CA/Exam split — assessment components and their weights are
    100% database-driven (Assignment, Quiz, Test, Practical, Mid-Semester,
    Examination, or anything else an institution wants).
  - Grading schemes are reusable and resolved per course with sane
    fallbacks (Course override -> Programme default -> global default),
    so results never has to duplicate curriculum's job of deciding what
    a course *is* — only how it is *graded*.
  - Result carries an explicit approval workflow (Lecturer -> HOD -> Dean
    -> Registrar -> Published) instead of a single is_submitted flag.
  - Every score edit and workflow transition is audited (ResultAuditLog).
  - GPA-relevant figures (credit_unit, scheme) are snapshotted on Result
    at creation time, so later curriculum changes never silently rewrite
    a student's academic history.

Removed from the previous version (see MIGRATION_NOTES.md for why):
  - GradingSetting / GradeScale (Programme-only, two-component only)
  - The `Curriculum` (programme/level/semester/course/is_core) model —
    that's curriculum data, not a results concern, and duplicated fields
    already on curriculum.Course.
  - `Examination` — belongs conceptually to a dedicated `examinations`
    app (already in your project's app list) that owns exam scheduling,
    not to `results`, which owns outcomes.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum

from students.models import Student
from curriculum.models import Course, Session, Semester, Programme






class Examination(models.Model):
    name = models.CharField(max_length=150, blank=True)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, blank=True, null=True)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='exams') # Link to semester  
    session = models.ForeignKey(Session, on_delete=models.CASCADE) 
  
    date = models.DateField(null=True) 
    description = models.CharField(max_length=150, blank=True)  

    def __str__ (self):
        return f'{self.name} - {self.promgramme.name} - {self.semester}'
    
    class Meta:
        verbose_name = 'Examinations'
        verbose_name_plural = 'Examinations'
        unique_together = ('name', 'semester', 'date')
        ordering = ['semester__start_date', 'date', 'name']
    

# ---------------------------------------------------------------------------
# Assessment configuration
# ---------------------------------------------------------------------------

class AssessmentComponent(models.Model):
    """
    Institution-configurable catalogue of assessment components, e.g.
    Assignment, Quiz, Test, Practical, Mid-Semester, Examination.
    Reused across as many grading schemes as needed.
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=20, unique=True, help_text="Short code, e.g. CA, EXAM, QUIZ")
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Assessment Component"
        verbose_name_plural = "Assessment Components"

    def __str__(self):
        return self.name


class GradingScheme(models.Model):
    """
    A named, reusable weighting configuration, e.g. "Standard 30/70",
    "Practical Heavy 20/20/60". Owns its components through
    GradingSchemeComponent so weightings are never hardcoded to CA+Exam.
    """
    name = models.CharField(max_length=100, unique=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Fallback scheme used when a course/programme has no explicit assignment.",
    )
    is_active = models.BooleanField(default=True)
    components = models.ManyToManyField(
        AssessmentComponent,
        through="GradingSchemeComponent",
        related_name="grading_schemes",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Grading Scheme"
        verbose_name_plural = "Grading Schemes"

    def __str__(self):
        return self.name

    def total_weight(self):
        return self.schemecomponents.aggregate(total=Sum("weight_percentage"))["total"] or Decimal("0")

    def clean(self):
        if self.pk and self.total_weight() and round(self.total_weight(), 2) != 100:
            raise ValidationError(
                f"Grading scheme '{self.name}' components must sum to 100% "
                f"(currently {self.total_weight()}%)."
            )

    def save(self, *args, **kwargs):
        if self.is_default:
            GradingScheme.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class GradingSchemeComponent(models.Model):
    """Through-model: what a scheme is made of, and how much each part
    of it is worth."""
    scheme = models.ForeignKey(GradingScheme, on_delete=models.CASCADE, related_name="schemecomponents")
    component = models.ForeignKey(AssessmentComponent, on_delete=models.PROTECT, related_name="scheme_links")
    weight_percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Contribution of this component to the total score (%).",
    )
    max_raw_score = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("100.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Maximum obtainable raw score for this component (e.g. a quiz out of 20).",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ("scheme", "component")
        ordering = ["order", "id"]
        verbose_name = "Grading Scheme Component"
        verbose_name_plural = "Grading Scheme Components"

    def __str__(self):
        return f"{self.scheme.name} → {self.component.name} ({self.weight_percentage}%)"


class GradeBoundary(models.Model):
    """
    Dynamic grade scale (A, B, C, ...), scoped to a GradingScheme rather
    than a Programme, since a scheme may be shared by several programmes.
    """
    scheme = models.ForeignKey(GradingScheme, on_delete=models.CASCADE, related_name="grade_boundaries")
    grade = models.CharField(max_length=3)
    min_score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2)
    remark = models.CharField(max_length=50, blank=True)
    is_pass = models.BooleanField(default=True)

    class Meta:
        unique_together = ("scheme", "grade")
        ordering = ["-min_score"]
        indexes = [models.Index(fields=["scheme", "min_score", "max_score"])]
        verbose_name = "Grade Boundary"
        verbose_name_plural = "Grade Boundaries"

    def clean(self):
        if self.min_score > self.max_score:
            raise ValidationError("min_score cannot exceed max_score.")
        overlapping = GradeBoundary.objects.filter(scheme=self.scheme).exclude(pk=self.pk).filter(
            min_score__lte=self.max_score, max_score__gte=self.min_score
        )
        if overlapping.exists():
            raise ValidationError(
                f"Score range {self.min_score}-{self.max_score} overlaps an existing grade boundary "
                f"in this scheme."
            )

    def __str__(self):
        return f"{self.scheme.name}: {self.grade} ({self.min_score}-{self.max_score})"


class ProgrammeGradingScheme(models.Model):
    """Default scheme for an entire programme."""
    programme = models.OneToOneField(Programme, on_delete=models.CASCADE, related_name="grading_scheme_link")
    scheme = models.ForeignKey(GradingScheme, on_delete=models.PROTECT, related_name="programme_links")

    def __str__(self):
        return f"{self.programme} → {self.scheme.name}"


class CourseGradingScheme(models.Model):
    """Optional per-course override (e.g. a lab-heavy course within a
    programme that otherwise uses the standard scheme)."""
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name="grading_scheme_link")
    scheme = models.ForeignKey(GradingScheme, on_delete=models.PROTECT, related_name="course_links")

    def __str__(self):
        return f"{self.course.course_code} → {self.scheme.name}"


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class Result(models.Model):
    """
    One row per student/course/session/semester (per attempt). Carries the
    computed outcome; the raw, component-level scores live in ResultScore.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted to HOD"
        HOD_APPROVED = "hod_approved", "Approved by HOD"
        DEAN_APPROVED = "dean_approved", "Approved by Dean"
        REGISTRAR_APPROVED = "registrar_approved", "Approved by Registrar"
        PUBLISHED = "published", "Published"
        RETURNED = "returned", "Returned for Correction"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="results")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="results")
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name="results")
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT, related_name="results")
    scheme = models.ForeignKey(
        GradingScheme, on_delete=models.PROTECT, null=True, blank=True, related_name="results",
        help_text="Snapshot of the scheme this result was graded under.",
    )

    credit_unit = models.PositiveSmallIntegerField( null=True, blank=True,
        help_text="Snapshot of the course's credit unit at the time this result was created."
    )
    attempt_number = models.PositiveSmallIntegerField(default=1, help_text="1 for a first sit, 2+ for a resit/carry-over.")

    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    grade = models.CharField(max_length=3, blank=True)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    remark = models.CharField(max_length=50, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_published = models.BooleanField(default=False)
    count_in_cgpa = models.BooleanField(
        default=True,
        help_text="Uncheck to exclude this specific attempt from CGPA (e.g. a superseded carry-over attempt).",
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="results_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "course", "session", "semester", "attempt_number")
        ordering = ["-session", "semester", "course__course_code"]
        indexes = [
            models.Index(fields=["student", "session", "semester"]),
            models.Index(fields=["course", "session", "semester"]),
            models.Index(fields=["status"]),
        ]
        permissions = [
            ("submit_result", "Can submit results for HOD review"),
            ("approve_result_hod", "Can approve results as HOD"),
            ("approve_result_dean", "Can approve results as Dean"),
            ("approve_result_registrar", "Can approve results as Registrar"),
            ("publish_result", "Can publish results to students"),
            ("return_result", "Can return results for correction"),
        ]
        verbose_name = "Result"
        verbose_name_plural = "Results"

    def __str__(self):
        return f"{self.student.matric_number} - {self.course.course_code} ({self.session}/{self.semester})"

    @property
    def quality_points(self) -> Decimal:
        if self.grade_point is None:
            return Decimal("0.00")
        return self.grade_point * self.credit_unit


class ResultScore(models.Model):
    """
    Raw score for a single assessment component within a Result. Replaces
    the old fixed tma_score/exam_score columns so institutions can attach
    any number of configured components without a schema change.
    """
    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name="scores")
    component = models.ForeignKey(AssessmentComponent, on_delete=models.PROTECT, related_name="result_scores")
    raw_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        unique_together = ("result", "component")
        ordering = ["component__name"]
        verbose_name = "Result Score"
        verbose_name_plural = "Result Scores"

    def clean(self):
        try:
            link = GradingSchemeComponent.objects.get(scheme=self.result.scheme, component=self.component)
        except GradingSchemeComponent.DoesNotExist:
            raise ValidationError(f"{self.component} is not part of the grading scheme assigned to this result.")
        if self.raw_score > link.max_raw_score:
            raise ValidationError(f"{self.component} score cannot exceed {link.max_raw_score}.")

    def __str__(self):
        return f"{self.result} - {self.component.name}: {self.raw_score}"


class ResultAuditLog(models.Model):
    """
    Immutable trail of every workflow transition or score edit on a
    Result — satisfies the project-wide requirement that result edits be
    audited. Kept local so this app is fully functional standalone; if/when
    the shared `audit` app is finalised, mirror writes into it from
    services/workflow.py rather than duplicating the model there.
    """
    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name="audit_logs")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="result_audit_actions",
    )
    action = models.CharField(max_length=40)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Result Audit Log"
        verbose_name_plural = "Result Audit Logs"

    def __str__(self):
        return f"{self.result} [{self.action}] @ {self.timestamp:%Y-%m-%d %H:%M}"
