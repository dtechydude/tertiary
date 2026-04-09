from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
from students.models import Student
from datetime import date
from django.utils import timezone



# class Attendance(models.Model):
#     student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
#     date = models.DateField(default=timezone.now)
#     present = models.BooleanField(default=False)
#     # Add other attendance-specific fields if needed (e.g., status: 'P', 'A', 'L')

#     class Meta:
#         # Ensures that a student can only have one attendance record per day
#         unique_together = ('student', 'date')
#         ordering = ['-date', 'student__user__first_name'] # Order by date (desc) and student name

#     def __str__(self):
#         return f"{self.student.first_name} - {self.date} - {'Present' if self.present else 'Absent'}"
from django.utils import timezone

class Attendance(models.Model):
    # Choices for more granular tracking
    class Status(models.TextChoices):
        PRESENT = 'P', 'Present'
        ABSENT = 'A', 'Absent'
        LATE = 'L', 'Late'
        EXCUSED = 'E', 'Excused'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    # Link attendance to a specific Course instead of just a date
    course = models.ForeignKey('curriculum.Course', on_delete=models.CASCADE, related_name='course_attendance', default='')
    
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=1, choices=Status.choices, default=Status.ABSENT)
    
    # Optional: Track which lecturer took the attendance
    marked_by = models.ForeignKey('staff.Lecturer', on_delete=models.SET_NULL, null=True)
    remarks = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., 'Student left early for clinic'")

    class Meta:
        # A student has one record per Course per Day
        unique_together = ('student', 'course', 'date')
        ordering = ['-date', 'course', 'student__middle_name']

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.course.code} - {self.date}"