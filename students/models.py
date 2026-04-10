from django.db import models
import math
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
from django.urls import reverse
# from portal.models import Teacher
from staff.models import Lecturer
# from attendance.models import AttendanceTotal
from datetime import date
from curriculum.models import Faculty, Department, Programme, Level, Session



# Blood Group
A_Positive = 'A+'
A_Negative = 'A-'
B_Positive = 'B+'
AB_Positive = 'AB+'
AB_Negative = 'AB-'
O_Positive = 'O+'
O_Negative = 'O-'
select = 'select'


blood_group = [
    (A_Positive, 'A+'),
    (A_Negative, 'B-'),
    (B_Positive, 'B+'),
    (AB_Positive, 'AB+'),
    (AB_Negative, 'AB-'),
    (O_Positive, 'O+'),
    (O_Negative, 'O-'),
    (select, 'select'),

]

# Genotype
AA = 'AA'
AS = 'AS'
AC = 'AC'
SS = 'SS'
select = 'select'

genotype = [
    (AA, 'AA'),
    (AS, 'AS'),
    (AC, 'AC'),
    (SS, 'SS'),
    (select, 'select'),

]

#TERTIARY MODEL FOR HOSTEL=======================================

class Hostel(models.Model):
    GENDER_CHOICES = [('male', 'Male'), ('female', 'Female'), ('mixed', 'Mixed')]

    name = models.CharField(max_length=100, unique=True, default="TEMPORARY_NAME")
    hostel_master = models.ForeignKey(
        'staff.Lecturer', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_hostels'
    )
    gender_type = models.CharField(max_length=10, choices=GENDER_CHOICES, default='mixed')
    capacity = models.PositiveIntegerField(default=1, help_text="Total bed spaces in this hostel")
    description = models.TextField(blank=True, help_text="Location details or rules")
    slug = models.SlugField(unique=True, null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def occupied_spaces(self):
        # Dynamically count students assigned to this hostel
        return self.student_hostel_name.count() # matches related_name in Student model

class Room(models.Model):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=10)
    max_occupancy = models.PositiveIntegerField(default=4)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.hostel.name} - Room {self.room_number}"
    



# Tertiary Logic

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, help_text="Select user or create new user")
    matric_number = models.CharField(max_length=100, unique=True, help_text="Must match username")
    middle_name = models.CharField(max_length=50, blank=True, null=True)

    # Academic Placement
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name="students")
    programme = models.ForeignKey(Programme, on_delete=models.SET_NULL, null=True)
    level = models.ForeignKey(Level, on_delete=models.SET_NULL, null=True )
    date_admitted = models.DateField()

    # -------------------------
    # PERSONAL INFORMATION
    # -------------------------

    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
    ]

    gender = models.CharField( max_length=10, choices=GENDER_CHOICES)
    DOB = models.DateField(default='1998-01-01')
    class StudentType(models.TextChoices):
        FULL_TIME = 'FT', 'Full-Time'
        PART_TIME = 'PT', 'Part-Time'
        SANDWICH  = 'SW', 'Sandwich'  # Added for vacation-based students
        WEEKEND   = 'WK', 'Weekend'   # Sometimes separated from Part-time

    student_type = models.CharField(
        max_length=2,
        choices=StudentType.choices,
        default=StudentType.FULL_TIME,
        help_text="Select student enrollment category")
    
    # ----------------------
    # HOSTEL INFORMATION
    #-----------------------
    hostel_name = models.ForeignKey(
        Hostel, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='student_hostel_name'
    )
    assigned_room = models.ForeignKey(
        Room, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='occupants'
    )
    
    # -------------------------
    # MEDICAL INFORMATION
    # -------------------------

    blood_group = models.CharField(max_length=15, blank=True, null=True, choices=blood_group)
    genotype = models.CharField(max_length=15, blank=True, null=True, choices=genotype)
    health_remark = models.CharField(max_length=200, blank=True)

    # -------------------------
    # GUARDIAN INFORMATION
    # (Optional in tertiary but retained)
    # -------------------------

    guardian_name = models.CharField(max_length=100, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    guardian_address = models.CharField(max_length=200, blank=True)
    guardian_email = models.EmailField(blank=True)

    RELATIONSHIP_CHOICES = [
        ("parent", "Parent"),
        ("father", "Father"),
        ("mother", "Mother"),
        ("guardian", "Guardian"),
        ("other", "Other"),
    ]

    relationship = models.CharField( max_length=20, choices=RELATIONSHIP_CHOICES, blank=True)

    # -------------------------
    # STATUS & FINANCE
    # -------------------------

    STATUS_CHOICES = [
        ("active", "Active"),
        ("graduated", "Graduated"),
        ("withdrawn", "Withdrawn"),
        ("suspended", "Suspended"),
        ("expelled", "Expelled"),
    ]

    student_status = models.CharField( max_length=20, choices=STATUS_CHOICES, default="active")
    fee_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    # -------------------------
    # UTILITIES
    # -------------------------
       
    def get_full_name(self):
        """
        Returns: UPPERCASE_SURNAME Firstname Middlename
        Example: DOE John Smith
        """
        if not self.user:
            return self.matric_number or f"Student #{self.id}"

        # .upper() is applied specifically to the last_name
        last = getattr(self.user, 'last_name', '').strip().upper()
        first = getattr(self.user, 'first_name', '').strip()
        middle = (self.middle_name or '').strip()
        
        names = [last, first, middle]
        full_name = " ".join(filter(None, names))
            
        # Fallback to Matric Number or Username if all name fields are empty
        return full_name or self.matric_number or self.user.username
        

    def __str__(self):
        return f"{self.matric_number} - {self.get_full_name()}"

    def get_absolute_url(self):
        return reverse("students:student-detail", kwargs={"pk": self.pk})

    class Meta:
        ordering = ["user__last_name"]
        verbose_name = "Student"
        verbose_name_plural = "Students"



class GraduationRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="graduation_records")
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, help_text="Session student completed programme")
    programme = models.ForeignKey(Programme, on_delete=models.SET_NULL, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    level_completed = models.ForeignKey(Level, on_delete=models.SET_NULL, null=True, help_text="Final level completed (e.g. OND 2, HND 2)")
    date_graduated = models.DateField()
    remarks = models.CharField(max_length=200, blank=True, help_text="Optional remarks (Distinction, Upper Credit, etc.)")
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.matric_number} - {self.programme} ({self.session})"

    class Meta:
        verbose_name = "Graduation Record"
        verbose_name_plural = "Graduation Records"
        ordering = ["-date_graduated"]



#parent Model
class Parent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, help_text='The user account for this parent.')
    guardian_name = models.CharField(max_length=60, blank=False, null=True)  
    guardian_address = models.CharField(max_length=200, blank=True, null=True)  
    guardian_phone = models.CharField(max_length=15, blank=True, null=True)
    guardian_email = models.CharField(max_length=30, blank=True, null=True)
    # You can add other parent-specific fields here if needed,
    # e.g., address, phone_number, etc.
    # The guardian_name, guardian_address, etc., from the Student model
    # can be moved here to avoid redundancy.

    def __str__(self):
        return self.user.get_full_name()
