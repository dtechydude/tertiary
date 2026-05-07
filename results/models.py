from django.db import models
from django.contrib.auth.models import User
from users.models import Profile
from students.models import Student
from curriculum.models import Department, Semester, Course, Session, Programme, Level
from django.conf import settings
from django.template.defaultfilters import slugify
from django.core.validators import MaxValueValidator, MinValueValidator 
from django.urls import reverse, reverse_lazy
from django.db import models
from django.db.models import UniqueConstraint, Sum, Avg # Import Avg for average calculations
from django.core.exceptions import ValidationError




class Examination(models.Model):
    name = models.CharField(max_length=150, blank=True)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, blank=True, null=True)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='exams') # Link to semester  
    session = models.ForeignKey(Session, on_delete=models.CASCADE) 
  
    date = models.DateField(null=True) 
    description = models.CharField(max_length=150, blank=True)  

    def __str__ (self):
        return f'{self.name} - {self.promgramme.name} - {self.semester}'
    
    class Meta:
        verbose_name = 'Examinations'
        verbose_name_plural = 'Examinations'
        unique_together = ('name', 'semester', 'date')
        ordering = ['semester__start_date', 'date', 'name']
    

# Tertiary Logic
class GradingSetting(models.Model):
    program = models.ForeignKey(Programme, on_delete=models.CASCADE)
    tma_weight = models.FloatField(default=30.0)
    exam_weight = models.FloatField(default=70.0)

    def total_weight(self):
        return self.tma_weight + self.exam_weight
    
class GradeScale(models.Model):
    program = models.ForeignKey(Programme, on_delete=models.CASCADE)
    min_score = models.FloatField()
    max_score = models.FloatField()
    grade = models.CharField(max_length=2)  # A, B, C...
    grade_point = models.FloatField()       # 5.0, 4.0...
    remark = models.CharField(max_length=50)

    class Meta:
        ordering = ['-min_score']


class Result(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)

    tma_score = models.FloatField(default=0)
    exam_score = models.FloatField(default=0)

    total_score = models.FloatField(blank=True, null=True)
    grade = models.CharField(max_length=2, blank=True)
    grade_point = models.FloatField(blank=True, null=True)
    remark = models.CharField(max_length=50, blank=True)

    credit_unit = models.IntegerField()

    is_submitted = models.BooleanField(default=False)
    date_uploaded = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'course', 'session', 'semester']


class Curriculum(models.Model):
    program = models.ForeignKey(Programme, on_delete=models.CASCADE)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    is_core = models.BooleanField(default=True)