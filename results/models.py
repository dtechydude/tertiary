from django.db import models
from django.contrib.auth.models import User
from users.models import Profile
from students.models import Student
from curriculum.models import Department, Semester, Course, Session, Programme
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
    
