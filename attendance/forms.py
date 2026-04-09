from django import forms
from .models import Attendance
from students.models import Student
from curriculum.models import Department, Course
from staff.models import Lecturer
from django.utils import timezone

# --- 1. TAKE ATTENDANCE FORM (Used in Formsets) ---
class AttendanceForm(forms.ModelForm):
    """
    Refactored to support Status Choices (P/A/L/E) 
    instead of just a boolean 'present' checkbox.
    """
    student_full_name = forms.CharField(
        label="Student Name",
        required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control-plaintext'})
    )

    class Meta:
        model = Attendance
        fields = ['status', 'remarks']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'remarks': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Display the student's name for the lecturer's convenience
        if self.instance and self.instance.student:
            name = self.instance.student.get_full_name()
            matric = getattr(self.instance.student, 'matric_number', '')
            self.fields['student_full_name'].initial = f"{name} ({matric})"

# --- 2. ATTENDANCE REPORT FORM (Filtering) ---
class AttendanceReportForm(forms.Form):
    start_date = forms.DateField(
        label="From",
        initial=timezone.localdate() - timezone.timedelta(days=7),
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        label="To",
        initial=timezone.localdate(),
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        required=False,
        label="Filter by Course",
        empty_label="All My Courses",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    current_class = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        required=False,
        label="Department/Class",
        empty_label="All Departments",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        required=False,
        label="Specific Student",
        empty_label="All Students",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        lecturer = kwargs.pop('lecturer', None)
        is_superuser = kwargs.pop('is_superuser', False)
        super().__init__(*args, **kwargs)

        # Logical Filtering based on User Role
        if is_superuser:
            self.fields['course'].queryset = Course.objects.all().order_by('course_code')
            self.fields['current_class'].queryset = Department.objects.all().order_by('name')
            self.fields['student'].queryset = Student.objects.all().order_by('user__last_name')
        
        elif lecturer:
            # Show only courses this lecturer is assigned to
            self.fields['course'].queryset = Course.objects.filter(lecturer=lecturer).order_by('course_code')
            
            # Show departments where this lecturer teaches or is a form lecturer
            self.fields['current_class'].queryset = Department.objects.filter(
                course__lecturer=lecturer
            ).distinct().order_by('name')
            
            # Show students in this lecturer's courses
            self.fields['student'].queryset = Student.objects.filter(
                department__course__lecturer=lecturer
            ).distinct().order_by('last_name')
        
        else:
            # Default empty state for non-staff
            self.fields['course'].queryset = Course.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and start > end:
            self.add_error('end_date', "End date cannot be before start date.")
        return cleaned_data