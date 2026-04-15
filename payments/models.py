from django.db import models
from django.contrib.auth.models import User # Assuming User model for staff/admins
from students.models import Student # Assuming you have a Student model in a 'students' app
from decimal import Decimal # Import Decimal for precise calculations
from django.utils import timezone # Import timezone
from django.db.models import Sum # Import Sum for aggregation
from curriculum.models import Semester, Session
from django.conf import settings
from .utils import update_student_ledger # This import is fine
from django.contrib.auth import get_user_model

# Assuming you have semester and Session models already defined.
class BankDetail(models.Model):
    acc_name = models.CharField(max_length=50, blank=False)
    acc_number = models.CharField(max_length=10, blank=False)
    bank_name = models.CharField(max_length=50, blank=False, verbose_name='Bank Name')

    def __str__(self):
        return f'{self.acc_number} - {self.bank_name}'

    class Meta:
        ordering:['bank_name']
        # unique_together = ['acc_number', 'bank_name']



from django.db import models
from django.contrib.auth.models import User

class PaymentCategory(models.Model):
    name = models.CharField(max_length=100, help_text="e.g., Tuition, Library, Admission")
    code = models.SlugField(unique=True, help_text="Unique short code (e.g., LIB, ADM, CREG)", null=True, blank=True)
    description = models.TextField(blank=True)
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Payment(models.Model):
    METHOD_CHOICES = [('gateway', 'Online (Gateway)'), ('manual', 'Bank Transfer/POS')]
    STATUS_CHOICES = [('pending', 'Pending Review'), ('success', 'Verified/Paid'), ('failed', 'Failed')]
    
    # Links
    category = models.ForeignKey(PaymentCategory, on_delete=models.PROTECT)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True) # For non-student payments
    
    # Financials
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    reference = models.CharField(max_length=100, unique=True)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    # Academic Context
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True)
    semester = models.ForeignKey(Semester, on_delete=models.SET_NULL, null=True)
    
    # Verification
    proof_of_payment = models.FileField(upload_to='payments/proofs/', null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approver")
    date_created = models.DateTimeField(auto_now_add=True)
    date_verified = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.reference} - {self.category.name}"
