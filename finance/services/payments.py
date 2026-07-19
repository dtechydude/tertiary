# """
# finance.services.payments
# ==========================

# Owns every write to the payment ledger (PaymentItem / Payment /
# PaymentAllocation). Views and admin call into this instead of touching
# the models directly, so "how much has this student paid, and is it
# enough" is computed exactly one way, everywhere.
# """

# from decimal import Decimal
# from typing import Optional

# from django.core.exceptions import ValidationError
# from django.db import transaction
# from django.utils import timezone

# from ..models import Payment, PaymentAllocation, PaymentItem
# from .fee_resolution import resolve_fee_assignments


# class FinanceService:

#     @staticmethod
#     @transaction.atomic
#     def ensure_semester_fee_items(student, session, semester) -> list:
#         """
#         Creates (idempotently) one PaymentItem per resolved FeeAssignment
#         for this student/session/semester. Safe to call repeatedly — at
#         semester start, or lazily the first time a student tries to pay.
#         """
#         items = []
#         for assignment in resolve_fee_assignments(student, session, semester):
#             item, _ = PaymentItem.objects.get_or_create(
#                 student=student, fee_assignment=assignment,
#                 defaults={"session": session, "semester": semester, "amount_due": assignment.amount},
#             )
#             items.append(item)
#         return items

#     @staticmethod
#     @transaction.atomic
#     def ensure_course_fee_item(course_registration) -> Optional[PaymentItem]:
#         """
#         Call this right after a CourseRegistration is created (from
#         wherever your registration app creates one). Creates the linked
#         PaymentItem for that course's fee, using curriculum.Course.cost.
#         Returns None for free courses (cost <= 0) — nothing to clear.
#         """
#         course = course_registration.course
#         if not course.cost or course.cost <= 0:
#             return None
#         item, _ = PaymentItem.objects.get_or_create(
#             course_registration=course_registration,
#             defaults={
#                 "student": course_registration.student,
#                 "session": course_registration.session,
#                 "semester": course_registration.semester,
#                 "amount_due": course.cost,
#             },
#         )
#         return item

#     @staticmethod
#     @transaction.atomic
#     def record_payment(
#         student, reference: str, amount: Decimal, method: str,
#         allocations: dict, recorded_by=None, mark_successful: bool = True,
#     ) -> Payment:
#         """
#         Records one payment and allocates it across one or more
#         PaymentItems in a single atomic operation.

#         `allocations`: {payment_item_id: amount, ...}. Total must not
#         exceed `amount`. Supports both a lump sum spread across several
#         bills and a single small installment toward one bill.
#         """
#         allocated_sum = sum(Decimal(str(v)) for v in allocations.values())
#         if allocated_sum > amount:
#             raise ValidationError("Total allocated amount cannot exceed the payment amount.")

#         payment = Payment.objects.create(
#             student=student, reference=reference, amount=amount, method=method,
#             status=Payment.Status.SUCCESSFUL if mark_successful else Payment.Status.PENDING,
#             recorded_by=recorded_by,
#             paid_at=timezone.now() if mark_successful else None,
#         )

#         for item_id, alloc_amount in allocations.items():
#             item = PaymentItem.objects.select_for_update().get(pk=item_id, student=student)
#             alloc_amount = Decimal(str(alloc_amount))
#             if alloc_amount <= 0:
#                 continue
#             if alloc_amount > item.balance:
#                 raise ValidationError(
#                     f"Allocation of {alloc_amount} to {item} exceeds its outstanding balance of {item.balance}."
#                 )
#             PaymentAllocation.objects.create(payment=payment, payment_item=item, amount=alloc_amount)

#         return payment

#     @staticmethod
#     @transaction.atomic
#     def confirm_payment(payment: Payment) -> Payment:
#         """Marks a pending payment (e.g. an async gateway callback, or a
#         student-submitted claim a bursary officer has verified) as
#         successful. Its allocations immediately start counting toward
#         each PaymentItem's amount_paid/is_cleared — and therefore exam
#         eligibility — since those are computed live, not cached."""
#         payment.status = Payment.Status.SUCCESSFUL
#         payment.paid_at = timezone.now()
#         payment.save(update_fields=["status", "paid_at"])
#         return payment

#     @staticmethod
#     @transaction.atomic
#     def reject_payment(payment: Payment) -> Payment:
#         """
#         Rejects a PENDING claim that turns out not to be valid (fake or
#         unverifiable reference, wrong amount, etc.) — distinct from
#         reverse_payment, which is for a payment that *was* successful and
#         later bounced/was refunded. A rejected payment's allocations
#         never counted toward any balance in the first place (only
#         SUCCESSFUL payments do), so nothing else needs to change.
#         """
#         payment.status = Payment.Status.FAILED
#         payment.save(update_fields=["status"])
#         return payment

#     @staticmethod
#     @transaction.atomic
#     def reverse_payment(payment: Payment) -> Payment:
#         """
#         Reverses a payment (bounced transfer, refund, etc). Its
#         allocations are kept for audit purposes but stop counting toward
#         any PaymentItem's amount_paid, since that property only sums
#         SUCCESSFUL payments.
#         """
#         payment.status = Payment.Status.REVERSED
#         payment.save(update_fields=["status"])
#         return payment


"""
finance.services.payments
==========================

Owns every write to the payment ledger (PaymentItem / Payment /
PaymentAllocation). Views and admin call into this instead of touching
the models directly, so "how much has this student paid, and is it
enough" is computed exactly one way, everywhere.
"""

from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import Payment, PaymentAllocation, PaymentItem
from .fee_resolution import resolve_fee_assignments


class FinanceService:

    @staticmethod
    @transaction.atomic
    def ensure_semester_fee_items(student, session, semester) -> list:
        """
        Creates (idempotently) one PaymentItem per resolved FeeAssignment
        for this student/session/semester. Safe to call repeatedly — at
        semester start, or lazily the first time a student tries to pay.
        """
        items = []
        for assignment in resolve_fee_assignments(student, session, semester):
            item, _ = PaymentItem.objects.get_or_create(
                student=student, fee_assignment=assignment,
                defaults={"session": session, "semester": semester, "amount_due": assignment.amount},
            )
            items.append(item)
        return items

    @staticmethod
    @transaction.atomic
    def ensure_course_fee_item(course_registration) -> Optional[PaymentItem]:
        """
        Call this right after a CourseRegistration is created (from
        wherever your registration app creates one). Creates the linked
        PaymentItem for that course's fee, using curriculum.Course.cost.
        Returns None for free courses (cost <= 0) — nothing to clear.

        Requires `course_registration.pk` to already be set. This matters
        because get_or_create(course_registration=course_registration, ...)
        resolves to course_registration_id under the hood — if pk is None
        (e.g. from trusting bulk_create()'s returned objects instead of
        re-fetching, which doesn't reliably populate pk on every DB
        backend/Django version), this would otherwise silently attempt
        course_registration_id=None: either an IntegrityError if that
        column is NOT NULL, or a PaymentItem with a null course_registration
        that later crashes build_outstanding_items() with an unrelated,
        confusing AttributeError. Failing here, immediately, with a clear
        message, is much easier to debug than either of those.
        """
        if not course_registration.pk:
            raise ValueError(
                "ensure_course_fee_item() was called with a CourseRegistration "
                "that has no pk set. If this came from bulk_create(), re-fetch "
                "the created rows from the database first instead of using the "
                "objects bulk_create() returns directly — it doesn't reliably "
                "populate .pk on every backend/Django version."
            )

        course = course_registration.course
        if not course.cost or course.cost <= 0:
            return None
        item, _ = PaymentItem.objects.get_or_create(
            course_registration=course_registration,
            defaults={
                "student": course_registration.student,
                "session": course_registration.session,
                "semester": course_registration.semester,
                "amount_due": course.cost,
            },
        )
        return item

    @staticmethod
    @transaction.atomic
    def record_payment(
        student, reference: str, amount: Decimal, method: str,
        allocations: dict, recorded_by=None, mark_successful: bool = True,
    ) -> Payment:
        """
        Records one payment and allocates it across one or more
        PaymentItems in a single atomic operation.

        `allocations`: {payment_item_id: amount, ...}. Total must not
        exceed `amount`. Supports both a lump sum spread across several
        bills and a single small installment toward one bill.
        """
        allocated_sum = sum(Decimal(str(v)) for v in allocations.values())
        if allocated_sum > amount:
            raise ValidationError("Total allocated amount cannot exceed the payment amount.")

        payment = Payment.objects.create(
            student=student, reference=reference, amount=amount, method=method,
            status=Payment.Status.SUCCESSFUL if mark_successful else Payment.Status.PENDING,
            recorded_by=recorded_by,
            paid_at=timezone.now() if mark_successful else None,
        )

        for item_id, alloc_amount in allocations.items():
            item = PaymentItem.objects.select_for_update().get(pk=item_id, student=student)
            alloc_amount = Decimal(str(alloc_amount))
            if alloc_amount <= 0:
                continue
            if alloc_amount > item.balance:
                raise ValidationError(
                    f"Allocation of {alloc_amount} to {item} exceeds its outstanding balance of {item.balance}."
                )
            PaymentAllocation.objects.create(payment=payment, payment_item=item, amount=alloc_amount)

        return payment

    @staticmethod
    @transaction.atomic
    def confirm_payment(payment: Payment) -> Payment:
        """Marks a pending payment (e.g. an async gateway callback, or a
        student-submitted claim a bursary officer has verified) as
        successful. Its allocations immediately start counting toward
        each PaymentItem's amount_paid/is_cleared — and therefore exam
        eligibility — since those are computed live, not cached."""
        payment.status = Payment.Status.SUCCESSFUL
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "paid_at"])
        return payment

    @staticmethod
    @transaction.atomic
    def reject_payment(payment: Payment) -> Payment:
        """
        Rejects a PENDING claim that turns out not to be valid (fake or
        unverifiable reference, wrong amount, etc.) — distinct from
        reverse_payment, which is for a payment that *was* successful and
        later bounced/was refunded. A rejected payment's allocations
        never counted toward any balance in the first place (only
        SUCCESSFUL payments do), so nothing else needs to change.
        """
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        return payment

    @staticmethod
    @transaction.atomic
    def reverse_payment(payment: Payment) -> Payment:
        """
        Reverses a payment (bounced transfer, refund, etc). Its
        allocations are kept for audit purposes but stop counting toward
        any PaymentItem's amount_paid, since that property only sums
        SUCCESSFUL payments.
        """
        payment.status = Payment.Status.REVERSED
        payment.save(update_fields=["status"])
        return payment