# Finance App — Accounting Reports, Debtors List & Wallet — Integration Guide

Everything here is **additive**. Nothing in your existing `finance` app was
altered in behavior — every existing view, URL, template, and model keeps
working exactly as it did. This package only adds new files and appends a
few new lines to three existing files (each change is called out precisely
below, with before/after shown).

## What's in this package

```
models_additions.py         → APPEND to finance/models.py
reports.py                  → REPLACES finance/services/reports.py (whole file, backward-compatible)
wallet.py                   → NEW FILE: finance/services/wallet.py
views_changes.py            → 3 precise edits to finance/views.py (documented inline) + new views to APPEND
urls_additions.py           → APPEND inside finance/urls.py's urlpatterns list
admin_additions.py          → APPEND to finance/admin.py (+ one import line edit)
templates/finance/reports_dashboard.html   → NEW template
templates/finance/wallet_dashboard.html    → NEW template
templates/finance/pending_payments.html    → REPLACES the existing file (adds a Wallet Funding section; the existing Payment Claims section is untouched)
```

## Step-by-step

### 1. `finance/models.py`
Open `models_additions.py` and paste its two classes (`Wallet`,
`WalletFundingRequest`) onto the end of your existing `finance/models.py`.
No existing line in that file needs to change — `Decimal`, `models`,
`settings`, `Sum`, and `Student` are all already imported at the top.

### 2. `finance/services/reports.py`
Replace this file's contents entirely with `reports.py` from this package.
It's fully backward compatible: every existing method keeps its original
parameter order, with a new `department=None` parameter appended at the
end of each — so `FinanceCategoryReportView` and the Django-admin
`collection_report` view (which both call these positionally) keep working
unchanged. New in this version: `totals_by_method()`, `debtors()`,
`total_outstanding()`.

### 3. `finance/services/wallet.py` (new file)
Drop `wallet.py` in as `finance/services/wallet.py`. It only imports from
`..models` and `.payments` (your existing `FinanceService`) — nothing in
`payments.py` needed to change; `WalletService.pay_with_wallet()` calls
`FinanceService.record_payment()` exactly as it already exists.

### 4. `finance/views.py`
Open `views_changes.py` — it documents three precise edits (each shown as
"Was: ... / Becomes: ...") plus a block of brand-new view functions to
append at the end of the file:
- **Edit 1**: extend the import lines (adds `Department`, `PaymentItem`,
  `Wallet`, `WalletFundingRequest`, `WalletService`, `Decimal`).
- **Edit 2**: `pending_payments_view` gains one more queryset
  (`pending_wallet_funding`) passed into the same template context — the
  existing `pending_payments` queryset and context key are untouched.
- **Edit 3**: `approve_payment_view` gains an `if payment.method ==
  Payment.Method.WALLET` branch that debits the wallet on approval; every
  other payment method still calls `FinanceService.confirm_payment(payment)`
  exactly as before.
- **New functions to append**: `finance_reports_dashboard_view`,
  `finance_collection_csv_view`, `debtors_csv_view`, `wallet_dashboard_view`,
  `fund_wallet_view`, `apply_wallet_view`, `approve_wallet_funding_view`,
  `reject_wallet_funding_view`.

`reject_payment_view` needs **no changes at all** — rejecting a wallet
payment already behaves correctly as-is (see the comment in the file for
why).

### 5. `finance/urls.py`
Paste the contents of `urls_additions.py` inside the existing
`urlpatterns = [ ... ]` list (e.g. right before the closing `]`). No
existing path changes.

### 6. `finance/admin.py`
Add `Wallet, WalletFundingRequest` to the existing model import line (shown
at the top of `admin_additions.py`), then paste the two new
`@admin.register(...)` classes anywhere in the file.

### 7. Templates
- Copy `reports_dashboard.html` and `wallet_dashboard.html` into
  `finance/templates/finance/` — brand new files, no conflicts.
- **Replace** your existing `finance/templates/finance/pending_payments.html`
  with the version in this package. The Payment Claims section (top half)
  is byte-for-byte the same as your original; only the new Wallet Funding
  Requests section (bottom half) was added.

### 8. Migration
Since `Wallet` and `WalletFundingRequest` are new models, run:
```bash
python manage.py makemigrations finance
python manage.py migrate
```
I didn't hand-write this migration — auto-generating it against your real
project state is safer than me guessing field ordering/app registration
details I can't verify from a zip file alone.

### 9. Permissions
Both new permission-gated views reuse permissions that **already exist** on
`Payment` (`finance.view_finance_reports` for the reports dashboard,
`finance.record_payment` for wallet-funding approval) — no new permissions
to create or assign.

### 10. Wire up navigation (wherever your sidebar/menu lives)
Two new links worth adding to the portal nav, matching the URL names above:
- Staff: `{% url 'finance:reports_dashboard' %}` — "Finance Reports"
- Student: `{% url 'finance:wallet_dashboard' %}` — "My Wallet"

(`{% url 'finance:pending_payments' %}` already existed and is now also the
wallet-funding approval screen — no new nav entry needed there, just note it
now does double duty.)

## The wallet flow, end to end

1. Student clicks **Fund Wallet** on `finance:wallet_dashboard`, enters an
   amount + their bank transfer reference → creates a `WalletFundingRequest`
   (`PENDING`). Nothing credited yet.
2. Staff sees it under **Wallet Funding Requests** on the (now dual-purpose)
   `finance:pending_payments` screen → **Approve & Credit Wallet** →
   `Wallet.balance` increases.
3. Student goes back to their wallet dashboard, sees their bills, checks the
   ones they want to pay off, enters amounts (capped to each bill's
   balance, and to their `available_balance` overall) → **Submit for
   Confirmation** → creates a normal `Payment(method=WALLET, status=PENDING)`
   via your existing `FinanceService.record_payment()`. The wallet balance
   isn't touched yet — but `available_balance` already subtracts anything
   currently pending, so the same funds can't be committed to two different
   bills at once while awaiting review.
4. Staff sees it under the existing **Payment Claims** section (same
   screen, same approve/reject buttons they already use for bank transfers,
   cash, etc.) → **Approve** → the payment is confirmed exactly as any other
   method would be (allocations count immediately, exam eligibility updates
   automatically), and the wallet is now actually debited by that amount.

## CSV exports
- `finance:collection_report_csv` — category totals for whatever
  session/semester/department filter is currently applied on the reports
  dashboard.
- `finance:debtors_csv` — the debtors list for the same filters.

Both are plain `csv` module output (no new package dependency), consistent
with the project's PythonAnywhere-free-tier / shared-hosting constraints.
