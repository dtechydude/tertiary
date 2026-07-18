from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path

from .models import FeeAssignment, FeeCategory, Payment, PaymentAllocation, PaymentItem, SchoolBankDetail
from .services.reports import FinanceReportService


@admin.register(SchoolBankDetail)
class SchoolBankDetailAdmin(admin.ModelAdmin):
    list_display = ("acc_name", "acc_number", "bank_name")
    search_fields = ("name", "bank")
    list_filter = ("bank_name",)


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


@admin.register(FeeAssignment)
class FeeAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "category", "programme", "level", "session", "semester",
        "amount", "is_mandatory_for_exam", "allow_part_payment",
    )
    list_filter = ("session", "semester", "category", "is_mandatory_for_exam")
    search_fields = ("category__name", "programme__name")


@admin.register(PaymentItem)
class PaymentItemAdmin(admin.ModelAdmin):
    list_display = ("student", "__str__", "amount_due", "amount_paid", "balance", "is_cleared")
    list_filter = ("session", "semester")
    search_fields = ("student__matric_number",)

    def get_readonly_fields(self, request, obj=None):
        # amount_paid/balance/is_cleared are derived from saved allocations —
        # meaningless (and previously crash-prone) on a not-yet-saved instance.
        if obj is None:
            return ()
        return ("amount_paid", "balance", "is_cleared")

    @admin.display(description="Amount Paid")
    def amount_paid(self, obj):
        return obj.amount_paid

    @admin.display(description="Balance")
    def balance(self, obj):
        return obj.balance

    @admin.display(boolean=True, description="Cleared")
    def is_cleared(self, obj):
        return obj.is_cleared


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    readonly_fields = ("payment_item", "amount")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "student", "amount", "method", "status", "paid_at")
    list_filter = ("status", "method")
    search_fields = ("reference", "student__matric_number")
    inlines = [PaymentAllocationInline]
    change_list_template = "admin/finance/payment/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("collection-report/", self.admin_site.admin_view(self.collection_report), name="finance_collection_report"),
        ]
        return custom + urls

    def collection_report(self, request):
        context = dict(
            self.admin_site.each_context(request),
            by_category=list(FinanceReportService.totals_by_category()),
            by_course=list(FinanceReportService.totals_by_course()),
            grand_total=FinanceReportService.grand_total(),
            title="Fee Collection Report",
        )
        return TemplateResponse(request, "admin/finance/collection_report.html", context)
