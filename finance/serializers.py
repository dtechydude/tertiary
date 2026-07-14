from rest_framework import serializers

from .models import FeeAssignment, FeeCategory, Payment, PaymentAllocation, PaymentItem


class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCategory
        fields = ["id", "name", "code", "description", "is_active"]


class FeeAssignmentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = FeeAssignment
        fields = [
            "id", "category", "category_name", "programme", "level", "session", "semester",
            "amount", "is_mandatory_for_exam", "allow_part_payment", "clearance_threshold_percentage",
        ]


class PaymentItemSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_cleared = serializers.BooleanField(read_only=True)
    is_mandatory_for_exam = serializers.BooleanField(read_only=True)

    class Meta:
        model = PaymentItem
        fields = [
            "id", "student", "session", "semester", "course_registration", "fee_assignment",
            "label", "amount_due", "amount_paid", "balance", "is_cleared", "is_mandatory_for_exam",
        ]

    def get_label(self, obj):
        if obj.fee_assignment_id:
            return obj.fee_assignment.category.name
        return obj.course_registration.course.course_code


class PaymentAllocationSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = PaymentAllocation
        fields = ["id", "payment_item", "label", "amount"]

    def get_label(self, obj):
        item = obj.payment_item
        return item.fee_assignment.category.name if item.fee_assignment_id else item.course_registration.course.course_code


class PaymentSerializer(serializers.ModelSerializer):
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    method_display = serializers.CharField(source="get_method_display", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "student", "reference", "amount", "method", "method_display",
            "status", "status_display", "paid_at", "created_at", "allocations",
        ]
        read_only_fields = ["status", "paid_at", "created_at"]


class RecordPaymentSerializer(serializers.Serializer):
    """Input payload for FinanceService.record_payment()."""
    student_id = serializers.IntegerField()
    reference = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    method = serializers.ChoiceField(choices=Payment.Method.choices, default=Payment.Method.BANK_TRANSFER)
    allocations = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2),
        help_text="{payment_item_id: amount, ...}",
    )
    mark_successful = serializers.BooleanField(default=True)
