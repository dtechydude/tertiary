from django.db import models
import math
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
# from portal.models import Dept
# from curriculum.utils import Subject, Standard, Dept
from django.template.defaultfilters import slugify
from users.models import Dept
from curriculum.models import  Department



# Staff Module
class StaffPosition(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=200, blank=True)
    slug = models.SlugField(null=True, blank=True, help_text='Do not enter anything here')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Staff Roles'
        verbose_name_plural = 'Staff Roles'



# Tertiary lecturer

class Lecturer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    staff_id = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name="lecturers")
    position = models.ForeignKey(StaffPosition, on_delete=models.SET_NULL,  null=True, blank=True)

    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
    ]

    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    married = 'married'
    single = 'single'
    select = 'select'

    marital_status = [
        (married, 'married'),
        (single, 'single'),
        (select, 'select'),
    ]

    marital_status = models.CharField(max_length=15, choices=marital_status, default=select)
    DOB = models.DateField(null=True, blank=True)
    date_employed = models.DateField()
    phone = models.CharField(max_length=15, blank=True)
    office_address = models.CharField(max_length=200, blank=True)

    # Academic Qualification
    highest_qualification = models.CharField(max_length=150)
    institution = models.CharField(max_length=150, blank=True)
    year_obtained = models.PositiveIntegerField(null=True, blank=True)
    professional_body = models.CharField(max_length=150, blank=True)

    # Guarantor's information
    guarantor_name = models.CharField(max_length=150, blank=True) 
    guarantor_phone = models.CharField(max_length=15, blank=True) 
    guarantor_address = models.CharField(max_length=150, blank=True) 
    guarantor_email = models.CharField(max_length=60, blank=True)
    
    # next of kin info
    next_of_kin_name = models.CharField(max_length=60, blank=True)  
    next_of_kin_address = models.CharField(max_length=150, blank=True)  
    next_of_kin_phone = models.CharField(max_length=15, blank=True) 

    # Status
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def get_full_name(self):
        names = [self.user.last_name, self.user.first_name, self.middle_name]
        full_name = " ".join(filter(None, names))
        return full_name.strip()

    def __str__(self):
        return f"{self.staff_id} - {self.get_full_name()}"

    class Meta:
        ordering = ["user__last_name"]
        verbose_name = "Lecturer"
        verbose_name_plural = "Lecturers"


