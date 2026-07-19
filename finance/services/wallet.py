"""
finance.services.wallet
========================

Wallet funding and wallet-based bill payment.

Kept as its own service (rather than folded into FinanceService) since it
owns a different pair of models (Wallet / WalletFundingRequest) and a
distinct approval flow for the *funding* side. Wallet *spending*
deliberately reuses FinanceService.record_payment()/confirm_payment() as
they already exist — unchanged — so a wallet-funded bill payment shows up
in the exact same pending-payments review screen bursary staff already
use for every other payment method, instead of needing a second parallel
approval screen.

Flow:
  1. Student requests funding (WalletFundingRequest, PENDING) — nothing
     credited yet.
  2. Staff approves -> Wallet.balance += amount (WalletService.approve_funding).
  3. Student applies wallet balance to one or more bills
     (WalletService.pay_with_wallet) -> creates a normal
     Payment(method=WALLET, status=PENDING) via the untouched
     FinanceService.record_payment(). The amount is *reserved*
     (Wallet.available_balance already subtracts any pending wallet
     payment) but not yet deducted from Wallet.balance.
  4. Staff approves that Payment from the pending-payments screen ->
     WalletService.approve_wallet_payment() confirms it via
     FinanceService.confirm_payment() (exactly as any other method would)
     AND permanently debits Wallet.balance by the same amount.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import Payment, Wallet, WalletFundingRequest
from .payments import FinanceService


class WalletService:

    @staticmethod
    def get_or_create_wallet(student) -> Wallet:
        wallet, _ = Wallet.objects.get_or_create(student=student)
        return wallet

    @staticmethod
    @transaction.atomic
    def request_funding(student, amount: Decimal, reference: str) -> WalletFundingRequest:
        if amount is None or amount <= 0:
            raise ValidationError("Funding amount must be positive.")
        if not reference or not reference.strip():
            raise ValidationError("A transfer/teller reference is required.")
        return WalletFundingRequest.objects.create(
            student=student, amount=amount, reference=reference.strip(),
        )

    @staticmethod
    @transaction.atomic
    def approve_funding(funding_request: WalletFundingRequest, reviewed_by=None) -> WalletFundingRequest:
        if funding_request.status != WalletFundingRequest.Status.PENDING:
            raise ValidationError("This funding request has already been reviewed.")

        wallet = WalletService.get_or_create_wallet(funding_request.student)
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        wallet.balance += funding_request.amount
        wallet.save(update_fields=["balance", "updated_at"])

        funding_request.status = WalletFundingRequest.Status.SUCCESSFUL
        funding_request.reviewed_by = reviewed_by
        funding_request.reviewed_at = timezone.now()
        funding_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        return funding_request

    @staticmethod
    @transaction.atomic
    def reject_funding(funding_request: WalletFundingRequest, reviewed_by=None) -> WalletFundingRequest:
        if funding_request.status != WalletFundingRequest.Status.PENDING:
            raise ValidationError("This funding request has already been reviewed.")

        funding_request.status = WalletFundingRequest.Status.REJECTED
        funding_request.reviewed_by = reviewed_by
        funding_request.reviewed_at = timezone.now()
        funding_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        return funding_request

    @staticmethod
    @transaction.atomic
    def pay_with_wallet(student, allocations: dict, reference: str = None) -> Payment:
        """
        Applies wallet balance toward one or more bills.
        `allocations`: {payment_item_id: amount, ...} — same shape
        FinanceService.record_payment already expects.
        """
        wallet = WalletService.get_or_create_wallet(student)
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

        total = sum(Decimal(str(v)) for v in allocations.values())
        if total <= 0:
            raise ValidationError("Total amount to apply from wallet must be positive.")
        if total > wallet.available_balance:
            raise ValidationError(
                f"Amount requested (₦{total}) exceeds your available wallet balance "
                f"(₦{wallet.available_balance})."
            )

        reference = reference or f"WALLET-{student.matric_number}-{timezone.now():%Y%m%d%H%M%S}"
        return FinanceService.record_payment(
            student=student, reference=reference, amount=total,
            method=Payment.Method.WALLET, allocations=allocations,
            mark_successful=False,
        )

    @staticmethod
    @transaction.atomic
    def approve_wallet_payment(payment: Payment, approved_by=None) -> Payment:
        """
        Approves a wallet-funded bill payment: confirms it via the
        unmodified FinanceService.confirm_payment() (exactly as any other
        method would), THEN permanently debits the wallet by the same
        amount — finalizing the reservation that available_balance was
        already accounting for since the student submitted it.
        """
        if payment.method != Payment.Method.WALLET:
            raise ValidationError("approve_wallet_payment() is only for wallet-method payments.")

        wallet = WalletService.get_or_create_wallet(payment.student)
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        if payment.amount > wallet.balance:
            # Shouldn't normally happen (available_balance already guarded
            # this at submission time) — but never let an approval push a
            # wallet negative if something changed in between.
            raise ValidationError(
                f"Cannot approve — wallet balance (₦{wallet.balance}) is lower than the "
                f"payment amount (₦{payment.amount}). Reject this instead."
            )

        FinanceService.confirm_payment(payment)

        wallet.balance -= payment.amount
        wallet.save(update_fields=["balance", "updated_at"])
        return payment
