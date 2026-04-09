# # your_app_name/utils.py (or views.py)
# from datetime import date
# from .models import Student, Attendance # Adjust import path as needed

# def get_student_present_attendance_count(student_instance, start_date, end_date):
#     """
#     Calculates the total number of 'Present' attendance records for a specific student
#     within a given date range (inclusive).

#     Args:
#         student_instance (Student): The Student model instance for whom to get the count.
#         start_date (datetime.date): The start date of the attendance period.
#         end_date (datetime.date): The end date of the attendance period.

#     Returns:
#         int: The total count of 'Present' attendance records for the student
#              within the specified date range.
#     """
#     if not isinstance(student_instance, Student):
#         raise TypeError("student_instance must be an instance of the Student model.")
#     if not all(isinstance(d, date) for d in [start_date, end_date]):
#         raise TypeError("start_date and end_date must be datetime.date objects.")
        
#     if start_date > end_date:
#         raise ValueError("start_date cannot be after end_date.")

#     present_count = Attendance.objects.filter(
#         student=student_instance,             # Filter by the specific student
#         status='P',                     # Filter where status is 'Present'
#         date__gte=start_date,      # Attendance date is greater than or equal to start_date
#         date__lte=end_date         # Attendance date is less than or equal to end_date
#     ).count()                                 # Get the total count

#     return present_count

#===============================================================================
# NEW LOGIC FOR ATTENDANCE UTILS
#==================================================================================

from datetime import date
from django.db.models import Q
from .models import Student, Attendance

def get_student_attendance_metrics(student_instance, start_date, end_date, course=None):
    """
    Calculates attendance metrics (Present count and Percentage) for a student.
    
    Args:
        student_instance (Student): The Student model instance.
        start_date (date): Start of period.
        end_date (date): End of period.
        course (Course, optional): Specific course to filter by.
    """
    if not isinstance(student_instance, Student):
        raise TypeError("student_instance must be an instance of the Student model.")

    # Base filter for the student and date range
    filters = Q(student=student_instance, date__range=(start_date, end_date))
    
    # If a specific course is provided, add it to the filter
    if course:
        filters &= Q(course=course)

    records = Attendance.objects.filter(filters)
    
    total_classes = records.count()
    # Using the 'P' status from the restructured model
    present_count = records.filter(status='P').count()
    
    # Calculate percentage (handle division by zero)
    attendance_percentage = 0
    if total_classes > 0:
        attendance_percentage = round((present_count / total_classes) * 100, 2)

    return {
        'present_count': present_count,
        'total_classes': total_classes,
        'percentage': attendance_percentage
    }