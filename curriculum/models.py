from django.db import models
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
from django.template.defaultfilters import slugify
from django.contrib.auth.models import User
from django.urls import reverse
import os
from django.utils.html import strip_tags
from django_ckeditor_5.fields import CKEditor5Field
from embed_video.fields import EmbedVideoField
from django.core.exceptions import ValidationError
from djrichtextfield.models import RichTextField
# from portal.models import Dept
from django.db.models import Sum


from tinymce.models import HTMLField
# from portal.models import Dept
# from staff.models import Teacher


# Register School
class SchoolIdentity(models.Model):
    name = models.CharField(max_length=50)
    address_line_1 = models.CharField(max_length=60)
    address_line_2 = models.CharField(max_length=60, blank=True, null=True)
    phone1 = models.CharField(max_length=11)
    phone2 = models.CharField(max_length=11, blank=True, null=True)
    email = models.CharField(max_length=50)
    logo = models.ImageField(default='school_logo.jpg', upload_to='official_pics', help_text='must not exceed 180px by 180px in size')
    signature = models.ImageField(blank=True, null=True, upload_to='official_pics', help_text='must not exceed 180px by 180px in size')

    slug = models.SlugField(null=True, blank=True)

    def __str__(self):
        return self.name
    class Meta:
        verbose_name_plural = 'School Identity'
        verbose_name_plural = "School Identity Settings"

    # code for ensuring that only single entry is made to this model
    def save(self, *args, **kwargs):
        # Check if any other instance of this model already exists
        if SchoolIdentity.objects.exists() and not self.pk:
            # If an instance exists and we are trying to create a *new* one (self.pk is None),
            # raise a ValidationError.
            raise ValidationError("There can be only one %s instance." % self._meta.verbose_name)
        return super().save(*args, **kwargs)




class Session(models.Model):
    name = models.CharField(max_length=50, unique=True)
    start_date = models.DateField(blank=True, null=True, verbose_name='Start Date')
    end_date = models.DateField(blank=True, null=True, verbose_name='End Date')
    desc = models.TextField(max_length=100, blank=True)
    is_current = models.BooleanField(default=False, help_text='check the box if the session is current') # To easily identify the current session
    slug = models.SlugField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Sessions"
        ordering = ['-start_date'] # Order by newest session first

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# Tertiary Logic
# Faculty
class Faculty(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(blank=True, null=True)

    def __str__(self):
        return self.name


# Department
class Department(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)

    hod = models.ForeignKey(
        "staff.Lecturer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="heading_department"
    )

    def __str__(self):
        return self.name

# Program
class Programme(models.Model):
    OND = "OND"
    HND = "HND"

    PROGRAMME_TYPES = [
        (OND, "OND"),
        (HND, "HND"),
    ]

    name = models.CharField(max_length=10, choices=PROGRAMME_TYPES)

    def __str__(self):
        return self.name

# Level
class Level(models.Model):
    programme = models.ForeignKey(
        Programme,
        on_delete=models.CASCADE,
        related_name="levels"
    )
    name = models.CharField(max_length=20)  # OND 1, OND 2, HND 1, HND 2

    def __str__(self):
        return self.name

#Semester
class Semester(models.Model):
    FIRST = "First"
    SECOND = "Second"

    SEMESTER_CHOICES = [
        (FIRST, "First Semester"),
        (SECOND, "Second Semester"),
    ]

    name = models.CharField(max_length=20, choices=SEMESTER_CHOICES)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='terms')
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, help_text='check the box if the term is current term in the current session')

    class Meta:
        # Ensures that "First Term" doesn't appear twice within the same session
        unique_together = ('name', 'session')
        ordering = ['session', 'start_date']

    def __str__(self):
        return f"{self.name} ({self.session.name})"    


    def __str__(self):
        return self.name


# courses
class Course(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    programme = models.ForeignKey("Programme", on_delete=models.CASCADE)
    level = models.ForeignKey("Level", on_delete=models.CASCADE)
    semester = models.ForeignKey("Semester", on_delete=models.CASCADE)

    title = models.CharField(max_length=200)
    course_code = models.CharField(max_length=20)
    credit_unit = models.PositiveIntegerField(default=2)

    lecturer = models.ForeignKey(
        "staff.Lecturer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses"
    )

    def __str__(self):
        return f"{self.course_code} - {self.title}"


class CourseAssignment(models.Model):

    lecturer = models.ForeignKey(
        'staff.Lecturer',
        on_delete=models.CASCADE,
        related_name="course_assignments"
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE
    )

    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE
    )

    is_course_adviser = models.BooleanField(default=False)

    assigned_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("lecturer", "course", "session", "semester")

    def __str__(self):
        return f"{self.course.course_code} - {self.lecturer.get_full_name()} ({self.session})"
 
        
