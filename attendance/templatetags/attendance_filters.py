from django import template
from datetime import date, timedelta

register = template.Library()

@register.filter
def date_range(start_date, end_date):
    """
    Generates a list of dates between start_date and end_date (inclusive).
    Usage: {% for day in start|date_range:end %}
    """
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        return []

    delta = end_date - start_date
    # Limit range to 31 days to prevent template performance crashes
    days_to_generate = min(delta.days + 1, 31) 
    
    return [start_date + timedelta(days=i) for i in range(days_to_generate)]

@register.filter
def get_attendance_record(attendance_dict, student_and_date):
    """
    Specifically for the reporting matrix. 
    Expects a dictionary and a 'student.id,date' string.
    Usage: {{ attendance_data|get_attendance_record:lookup_string }}
    """
    try:
        # In views.py, attendance_data is structured as {student_obj: {date_obj: record_obj}}
        student, target_date = student_and_date
        return attendance_dict.get(student, {}).get(target_date)
    except (TypeError, ValueError, AttributeError):
        return None

@register.filter
def status_color(status_code):
    """
    Returns a Bootstrap badge class based on the attendance status.
    Usage: <span class="badge {{ record.status|status_color }}">
    """
    colors = {
        'P': 'bg-success',  # Present - Green
        'A': 'bg-danger',   # Absent - Red
        'L': 'bg-warning',  # Late - Yellow
        'E': 'bg-info',     # Excused - Blue
    }
    return colors.get(status_code, 'bg-secondary')

# @register.filter
# def get_item(dictionary, key):
#     """
#     Generic dictionary lookup. Improved for nested data.
#     """
#     if not dictionary:
#         return None
    
#     if isinstance(dictionary, dict):
#         return dictionary.get(key)
#     return None
@register.filter
def get_item(dictionary, key):
    """
    Safe dictionary lookup that handles date keys properly.
    """
    if not dictionary:
        return None

    try:
        # Normalize date objects (VERY IMPORTANT)
        if hasattr(key, "isoformat"):
            for k in dictionary.keys():
                if hasattr(k, "isoformat") and k == key:
                    return dictionary.get(k)
        return dictionary.get(key)
    except Exception:
        return None