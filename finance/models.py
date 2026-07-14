"""
finance.models
==============

Owns semester-wide mandatory fees (Tuition, Acceptance, Hostel, Medical,
Departmental, or any custom category an institution wants) plus a single
unified payment ledger that ALSO covers per-course fees — so exam
eligibility, receipts, and collection reports all read from one place
instead of two parallel systems.

Course registration stays the registration module's job: a
CourseRegistration row means "this student is taking this course this
semester." This app only decides whether that registration is *paid for*
well enough to sit the exam — it doesn't touch registration validation
itself (prerequisites, duplicate registration, unit limits, etc. remain
wherever your registration app already handles them).

Design shape:
  FeeCategory        — the catalogue (Tuition, Hostel, Medical, ...)
  FeeAssignment       — how much a category costs, scoped to
                        session/semester and optionally programme/level
  PaymentItem         — one billable line for one student: either a
                        course's fee OR a FeeAssignment, never both
  Payment             — one payment transaction a student makes
  PaymentAllocation   — how a Payment's amount is split across one or
                        more PaymentItems (supports part-payment AND
                        lump-sum payments covering several bills at once)
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum

from curriculum.models import Programme, Level, Session, Semester, CourseRegistration
from students.models import Student


class FeeCategory(models.Model):
    """
    Institution-configurable catalogue of non-course fee types — Tuition,
    Acceptance Fee, Hostel Fee, Medical Fee, Departmental Fee, or any
    custom category the school wants to add. Never a fixed list.
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=30, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Fee Category"
        verbose_name_plural = "Fee Categories"

    def __str__(self):
        return self.name


class FeeAssignment(models.Model):
    """
    How much a FeeCategory costs for a session/semester, scoped as
    specifically or as broadly as needed:
      - programme + level  -> only that level of that programme
      - programme only     -> every level of that programme (level=None)
      - neither             -> institution-wide default (fully global)
    When resolving what a student owes, the most specific match for each
    category wins — the same resolution philosophy the results app uses
    for grading schemes.
    """
    category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT, related_name="assignments")
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE, null=True, blank=True, related_name="fee_assignments"
    )
    level = models.ForeignKey(
        Level, on_delete=models.CASCADE, null=True, blank=True, related_name="fee_assignments"
    )
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="fee_assignments")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name="fee_assignments")

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_mandatory_for_exam = models.BooleanField(
        default=True,
        help_text="If checked, a student cannot sit exams for ANY course this semester until this fee is cleared.",
    )
    allow_part_payment = models.BooleanField(
        default=True,
        help_text="Whether students may pay this fee in installments over time.",
    )
    clearance_threshold_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("100.00"),
        help_text="Percentage of `amount` that must be paid for this fee to count as cleared. Usually 100.",
    )

    class Meta:
        unique_together = ("category", "programme", "level", "session", "semester")
        ordering = ["session", "semester", "category__name"]
        indexes = [models.Index(fields=["session", "semester", "programme", "level"])]
        verbose_name = "Fee Assignment"
        verbose_name_plural = "Fee Assignments"

    def clean(self):
        if self.level_id and not self.programme_id:
            raise ValidationError("A level-specific fee assignment must also specify its programme.")

    def __str__(self):
        scope = self.level or self.programme or "Institution-wide"
        return f"{self.category.name} — {scope} ({self.session}/{self.semester}): {self.amount}"


class PaymentItem(models.Model):
    """
    One billable line for one student, for one session/semester — either
    a specific course's fee (via `course_registration`) or a non-course
    mandatory fee (via `fee_assignment`). Exactly one of the two is set.
    "Cleared or not" is always checked against a PaymentItem, whether
    it's a course fee or a hostel fee — one rule, one place.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="payment_items")
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name="payment_items")
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT, related_name="payment_items")

    course_registration = models.OneToOneField(
        CourseRegistration, on_delete=models.CASCADE, null=True, blank=True, related_name="payment_item"
    )
    fee_assignment = models.ForeignKey(
        FeeAssignment, on_delete=models.PROTECT, null=True, blank=True, related_name="payment_items"
    )

    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "fee_assignment")
        indexes = [models.Index(fields=["student", "session", "semester"])]
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(course_registration__isnull=False, fee_assignment__isnull=True)
                    | Q(course_registration__isnull=True, fee_assignment__isnull=False)
                ),
                name="payment_item_exactly_one_target",
            )
        ]
        verbose_name = "Payment Item"
        verbose_name_plural = "Payment Items"

    def clean(self):
        if bool(self.course_registration_id) == bool(self.fee_assignment_id):
            raise ValidationError(
                "A PaymentItem must be linked to exactly one of course_registration or fee_assignment."
            )

    def __str__(self):
        target = (
            self.course_registration.course.course_code
            if self.course_registration_id else self.fee_assignment.category.name
        )
        return f"{self.student.matric_number} — {target}: {self.amount_due}"

    @property
    def amount_paid(self) -> Decimal:
        total = self.allocations.filter(payment__status=Payment.Status.SUCCESSFUL).aggregate(
            total=Sum("amount")
        )["total"]
        return total or Decimal("0.00")

    @property
    def balance(self) -> Decimal:
        return self.amount_due - self.amount_paid

    @property
    def clearance_threshold_percentage(self) -> Decimal:
        if self.fee_assignment_id:
            return self.fee_assignment.clearance_threshold_percentage
        return Decimal("100.00")  # a course's own fee always requires full payment

    @property
    def is_cleared(self) -> bool:
        if self.amount_due <= 0:
            return True
        required = self.amount_due * self.clearance_threshold_percentage / Decimal("100")
        return self.amount_paid >= required

    @property
    def is_mandatory_for_exam(self) -> bool:
        if self.course_registration_id:
            return True  # a registered course's own fee always gates its own exam
        return self.fee_assignment.is_mandatory_for_exam


class Payment(models.Model):
    """A single payment transaction a student makes. May be split across
    one or more PaymentItems via PaymentAllocation."""

    class Method(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        CARD = "card", "Card"
        CASH = "cash", "Cash"
        USSD = "ussd", "USSD"
        WALLET = "wallet", "Wallet"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="payments")
    reference = models.CharField(max_length=100, unique=True, help_text="Transaction reference / receipt number.")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.BANK_TRANSFER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payments_recorded",
        help_text="Bursary staff who recorded a manual/offline payment; blank for an online gateway payment.",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["student", "status"])]
        permissions = [
            ("record_payment", "Can record student payments"),
            ("view_finance_reports", "Can view finance collection reports"),
        ]

    def __str__(self):
        return f"{self.reference} — {self.student.matric_number}: {self.amount} ({self.status})"

    @property
    def allocated_total(self) -> Decimal:
        return self.allocations.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    @property
    def unallocated_balance(self) -> Decimal:
        return self.amount - self.allocated_total


class PaymentAllocation(models.Model):
    """
    How much of a single Payment goes toward a single PaymentItem. This
    is what makes both part-payment (many small payments toward one
    bill) and lump-sum payment (one payment spread across many bills)
    possible with the same two models.
    """
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    payment_item = models.ForeignKey(PaymentItem, on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("payment", "payment_item")
        verbose_name = "Payment Allocation"
        verbose_name_plural = "Payment Allocations"

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Allocation amount must be positive.")

    def __str__(self):
        return f"{self.payment.reference} → {self.payment_item}: {self.amount}"
