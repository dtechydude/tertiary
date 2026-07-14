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




# New School Identity
class SchoolIdentity(models.Model):
    name = models.CharField(max_length=100)
    identity_label = models.CharField(
        max_length=50,
        help_text="e.g. Main, Faculty of Science, School of Engineering"
    )
    is_default = models.BooleanField(default=False)

    address_line_1 = models.CharField(max_length=100)
    address_line_2 = models.CharField(max_length=100, blank=True, null=True)
    phone1 = models.CharField(max_length=15)
    phone2 = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    website = models.CharField(max_length=100, blank=True, null=True)

    logo = models.ImageField(upload_to='official_pics', default='school_logo.jpg')
    signature = models.ImageField(upload_to='official_pics', blank=True, null=True)

    slug = models.SlugField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk and SchoolIdentity.objects.count() >= 5:
            raise ValidationError("Maximum of 5 identities allowed.")

        if self.is_default:
            SchoolIdentity.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.identity_label})"
 
    
class AcademicIdentityMapping(models.Model):
    """
    Maps identity to Department or Faculty
    """

    faculty = models.ForeignKey(
        'curriculum.Faculty',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    department = models.OneToOneField(
        'curriculum.Department',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    school_identity = models.ForeignKey(
        SchoolIdentity,
        on_delete=models.CASCADE
    )

    def __str__(self):
        if self.department:
            return f"{self.department.name} → {self.school_identity.identity_label}"
        if self.faculty:
            return f"{self.faculty.name} → {self.school_identity.identity_label}"
        return "Unassigned Mapping"


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

#Semester
class Semester(models.Model):
    FIRST = "First"
    SECOND = "Second"
    THIRD = "Third"

    SEMESTER_CHOICES = [
        (FIRST, "First Semester"),
        (SECOND, "Second Semester"),
        (THIRD, "Third Semester"),
    ]

    name = models.CharField(max_length=20, choices=SEMESTER_CHOICES)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='terms')
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, help_text='check the box if the semester is current semester in the current session')
    # New Administrative Control Fields
    reg_start_date = models.DateField(null=True, blank=True, help_text="When the portal opens")
    reg_end_date = models.DateField(null=True, blank=True, help_text="Normal registration deadline")
    late_reg_end_date = models.DateField(null=True, blank=True, help_text="Absolute final deadline")
    late_reg_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Manual kill-switch (In case of emergency or school strike)
    is_reg_active = models.BooleanField(default=True, verbose_name="Portal Manual Override")

    class Meta:
        # Ensures that "First Term" doesn't appear twice within the same session
        unique_together = ('name', 'session')
        ordering = ['session', 'start_date']

    def __str__(self):
        return f"{self.name} ({self.session.name})"    


    def __str__(self):
        return self.name
 
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
    hod = models.ForeignKey("staff.Lecturer", on_delete=models.SET_NULL, null=True, blank=True, related_name="heading_department")

    def __str__(self):
        return self.name

# Program
class QualificationType(models.Model):
    """
    Configurable catalogue of qualifications this institution awards —
    e.g. National Diploma, Higher National Diploma, Bachelor's Degree,
    Postgraduate Diploma, Master's Degree, Professional Certificate, or
    anything else the school wants to add later, without a code change.
    """
    name = models.CharField(max_length=100, unique=True)
    short_code = models.CharField(max_length=20, unique=True, help_text="e.g. ND, HND, BSc, PGD, MSc, CERT")
    award_title = models.CharField(
        max_length=150, blank=True,
        help_text="Full title printed on certificates/transcripts, e.g. 'Higher National Diploma'",
    )
    duration_years = models.DecimalField(
        max_digits=3, decimal_places=1, default=2,
        help_text="Standard duration for this qualification, e.g. 2, 2.5, 4, 5",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Qualification Type"
        verbose_name_plural = "Qualification Types"

    def __str__(self):
        return self.name


class Programme(models.Model):
    """
    A specific academic programme, e.g. "Computer Science", "Accountancy",
    "Public Health" — no longer tied to a fixed 4-choice list. What *kind*
    of award it is (Diploma, Degree, Certificate, Masters, or anything
    else the institution wants) is driven entirely by `qualification_type`,
    which is admin-managed data, not code.

    NOTE — breaking change from the previous version: `name` used to be
    restricted to OND/HND/CERTIFICATE/OTHERS via `choices=`. It's now a
    free-text title. See PATCH_NOTES.md for the migration path: existing
    rows need `qualification_type` backfilled (their old `name` value maps
    directly onto a QualificationType you create once), and their `name`
    should then be updated to the programme's actual title.
    """
    qualification_type = models.ForeignKey(
        QualificationType, on_delete=models.PROTECT, related_name="programmes",
        help_text="What kind of award this is — Diploma, Degree, Certificate, Masters, or anything else configured.",
    )
    name = models.CharField(
        max_length=150,
        help_text="The programme's actual title, e.g. 'Computer Science', 'Accountancy', 'Public Health'.",
    )

    class Meta:
        ordering = ["qualification_type__name", "name"]
        verbose_name = "Programme"
        verbose_name_plural = "Programmes"

    def __str__(self):
        if self.qualification_type_id:
            return f"{self.qualification_type.short_code} {self.name}"
        return self.name


class RegistrationPolicy(models.Model):
    """
    How many credit units a student may/must register per semester.
    Resolution order: Level-specific override -> Programme-wide default.
    Mirrors the resolution pattern used by the results app's grading
    scheme (course override -> programme default -> global default), so
    a final-year level can carry a lower cap than its programme's general
    rule without any special-casing in the registration app's validators.

    NOTE: once a dedicated `registration` app exists (per the project's
    module list), this is a natural candidate to move there. It lives in
    curriculum for now because it's configured alongside Programme/Level,
    which already live here.
    """
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name="registration_policies",
        null=True, blank=True,
        help_text="Programme-wide default. Leave blank if this policy is only for a specific level.",
    )
    level = models.OneToOneField(
        "Level", on_delete=models.CASCADE, related_name="registration_policy",
        null=True, blank=True,
        help_text="Overrides the programme default for this specific level only.",
    )

    min_units_per_semester = models.PositiveSmallIntegerField(default=12)
    max_units_per_semester = models.PositiveSmallIntegerField(default=24)
    max_carryover_units = models.PositiveSmallIntegerField(
        default=0,
        help_text="Extra units allowed above the max, reserved for carry-over/resit courses. 0 = no allowance.",
    )

    class Meta:
        verbose_name = "Registration Policy"
        verbose_name_plural = "Registration Policies"
        constraints = [
            models.CheckConstraint(
                check=models.Q(min_units_per_semester__lte=models.F("max_units_per_semester")),
                name="curriculum_min_units_lte_max_units",
            ),
        ]

    def clean(self):
        if not self.programme_id and not self.level_id:
            raise ValidationError("A RegistrationPolicy must be tied to at least a Programme or a Level.")
        if self.min_units_per_semester > self.max_units_per_semester:
            raise ValidationError("min_units_per_semester cannot exceed max_units_per_semester.")

    def __str__(self):
        scope = self.level or self.programme
        return f"{scope} — {self.min_units_per_semester}-{self.max_units_per_semester} units"


# Level
class Level(models.Model):
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="levels")
    name = models.CharField(max_length=20)  # OND 1, OND 2, HND 1, HND 2

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

    lecturer = models.ForeignKey("staff.Lecturer", on_delete=models.SET_NULL,  null=True, blank=True, related_name="courses")

    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.course_code} - {self.title}"


class CourseAssignment(models.Model):
    lecturer = models.ForeignKey('staff.Lecturer', on_delete=models.CASCADE, related_name="course_assignments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    is_course_adviser = models.BooleanField(default=False)
    assigned_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("lecturer", "course", "session", "semester")

    def __str__(self):
        return f"{self.course.course_code} - {self.lecturer.get_full_name()} ({self.session})"
 


# Students Course Registrations
class CourseRegistration(models.Model):
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="course_registrations"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="registrations"
    )
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)

    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "course", "session", "semester")

    def __str__(self):
        return f"{self.student} - {self.course} ({self.session} / {self.semester})"





#===================================================================
# Subject For E-Learning
class ELearningSubject(models.Model):
    subject_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    standard = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='subjects')
    # image = models.ImageField(upload_to=save_subject_image, blank=True, verbose_name='Subject Image')
    description = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(null=True, blank=True)

    def __str__(self):
        return f'{self.name} - {self.standard.name}'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.subject_id)
        super().save(*args, **kwargs)

    class Meta:
      verbose_name = 'E-Learning Subjects'
      verbose_name_plural = 'E-Learning Subjects'
      ordering = ['name']
      unique_together = ('name', 'standard')


def save_lesson_files(instance, filename):
    upload_to = 'Images/'
    ext = filename.split('.')[-1]
    # get file name
    if instance.lesson_id:
        filename = 'lesson_files/{}.{}'.format(instance.lesson_id,instance.lesson_id, ext)
        if os.path.exists(filename):
            new_name = str(instance.lesson_id) + str('1')
            filename = 'lesson_images/{}/{}.{}'.format(instance.lesson_id,new_name, ext)
    
    return os.path.join(upload_to, filename)
    

class Lesson(models.Model):
    lesson_id = models.CharField(max_length=100, unique=True)
    standard = models.ForeignKey(Level, on_delete=models.CASCADE)
    subject = models.ForeignKey(ELearningSubject, on_delete=models.CASCADE, related_name='lessons')
    name = models.CharField(max_length=250)
    position = models.PositiveSmallIntegerField(verbose_name="Chapter no.")
    video = EmbedVideoField(blank=True, null=True)
    notes = models.FileField(upload_to='save_lesson_files', verbose_name="Notes", blank=True)
    # comment = RichTextField(blank=True, null=True)
    comment = HTMLField(blank=True, null=True)
    # comment = CKEditor5Field('Text', config_name='extends')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(null=True, blank=True)

    class Meta:
        ordering = ['position']
        verbose_name = 'E-Learning Lessons'
        verbose_name_plural = 'E-Learning Lessons'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('curriculum:lesson_list', kwargs={'slug':self.subject.slug, 'standard':self.standard.slug})

    @property
    def html_stripped(self):
       
       return strip_tags(self.comment)
            
            

# comment module
class Comment(models.Model):
    lesson_name = models.ForeignKey(Lesson, null=True, on_delete=models.CASCADE, related_name='comments')
    comm_name = models. CharField(max_length=100, blank=True)
    # reply = models.ForeignKey("comment", null=True, blank=True, on_delete=CASCADE, related_name='replies')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField(max_length=500)
    date_added = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.comm_name = slugify("comment by" + "-" + str(self.author) + str(self.date_added))
        super().save(*args, **kwargs)

    def __str__(self):
        return self.comm_name

    class Meta:
        ordering = ['-date_added']


class Reply(models.Model):
    comment_name = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='replies')
    reply_body = models.TextField(max_length=500)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "reply to" + str(self.comment_name.comm_name)
    