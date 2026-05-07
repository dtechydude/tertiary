from django import forms
from .models import Attendance
from students.models import Student
from curriculum.models import Department, Course, CourseAssignment
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
# class AttendanceReportForm(forms.Form):
#     start_date = forms.DateField(
#         label="From",
#         initial=timezone.localdate() - timezone.timedelta(days=7),
#         widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
#     )

#     end_date = forms.DateField(
#         label="To",
#         initial=timezone.localdate(),
#         widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
#     )

#     course = forms.ModelChoiceField(
#         queryset=Course.objects.none(),
#         required=False,
#         label="Filter by Course",
#         empty_label="All My Courses",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     # ✅ RENAMED internally to match backend logic (level/department confusion removed)
#     department = forms.ModelChoiceField(
#         queryset=Department.objects.none(),
#         required=False,
#         label="Department",
#         empty_label="All Departments",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     student = forms.ModelChoiceField(
#         queryset=Student.objects.none(),
#         required=False,
#         label="Specific Student",
#         empty_label="All Students",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     def __init__(self, *args, **kwargs):
#         lecturer = kwargs.pop('lecturer', None)
#         is_superuser = kwargs.pop('is_superuser', False)
#         super().__init__(*args, **kwargs)

#         # ==============================
#         # ADMIN VIEW
#         # ==============================
#         if is_superuser:
#             self.fields['course'].queryset = Course.objects.all().order_by('course_code')
#             self.fields['department'].queryset = Department.objects.all().order_by('name')
#             self.fields['student'].queryset = Student.objects.select_related('user').all().order_by('user__last_name')

#         # ==============================
#         # LECTURER VIEW (CORRECT LOGIC)
#         # ==============================
#         elif lecturer:
#             from curriculum.models import CourseAssignment  # adjust import if needed

#             # Get assigned courses via CourseAssignment
#             assigned_courses = CourseAssignment.objects.filter(
#                 lecturer=lecturer
#             ).select_related('course')

#             course_ids = assigned_courses.values_list('course_id', flat=True)

#             # ✅ COURSES
#             self.fields['course'].queryset = Course.objects.filter(
#                 id__in=course_ids
#             ).order_by('course_code')

#             # ✅ DEPARTMENTS (based on assigned courses)
#             self.fields['department'].queryset = Department.objects.filter(
#                 course__id__in=course_ids
#             ).distinct().order_by('name')

#             # ✅ STUDENTS (registered for assigned courses)
#             self.fields['student'].queryset = Student.objects.filter(
#                 course_registrations__course_id__in=course_ids
#             ).distinct().select_related('user').order_by('user__last_name')

#         # ==============================
#         # FALLBACK
#         # ==============================
#         else:
#             self.fields['course'].queryset = Course.objects.none()
#             self.fields['department'].queryset = Department.objects.none()
#             self.fields['student'].queryset = Student.objects.none()

#     def clean(self):
#         cleaned_data = super().clean()
#         start = cleaned_data.get('start_date')
#         end = cleaned_data.get('end_date')

#         if start and end and start > end:
#             self.add_error('end_date', "End date cannot be before start date.")

#         return cleaned_data

# class AttendanceReportForm(forms.Form):

#     start_date = forms.DateField(
#         label="From",
#         widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
#     )

#     end_date = forms.DateField(
#         label="To",
#         widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
#     )

#     course = forms.ModelChoiceField(
#         queryset=Course.objects.none(),
#         required=False,
#         empty_label="All Courses",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     department = forms.ModelChoiceField(
#         queryset=Department.objects.none(),
#         required=False,
#         empty_label="All Departments",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     student = forms.ModelChoiceField(
#         queryset=Student.objects.none(),
#         required=False,
#         empty_label="All Students",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     def __init__(self, *args, **kwargs):
#         lecturer = kwargs.pop('lecturer', None)
#         is_superuser = kwargs.pop('is_superuser', False)
#         student_user = kwargs.pop('student_user', None)
#         super().__init__(*args, **kwargs)

#         # -----------------------------
#         # ADMIN
#         # -----------------------------
#         if is_superuser:
#             self.fields['course'].queryset = Course.objects.all()
#             self.fields['department'].queryset = Department.objects.all()
#             self.fields['student'].queryset = Student.objects.all()

#         # -----------------------------
#         # LECTURER
#         # -----------------------------
#         elif lecturer:
#             courses = CourseAssignment.objects.filter(
#                 lecturer=lecturer
#             ).values_list('course', flat=True)

#             self.fields['course'].queryset = Course.objects.filter(id__in=courses)
#             self.fields['department'].queryset = Department.objects.filter(
#                 student__course_registrations__course__in=courses
#             ).distinct()

#             self.fields['student'].queryset = Student.objects.filter(
#                 course_registrations__course__in=courses
#             ).distinct()

#         # -----------------------------
#         # STUDENT
#         # -----------------------------
#         elif student_user:
#             self.fields['course'].queryset = Course.objects.filter(
#                 course_registrations__student=student_user
#             ).distinct()

#             self.fields['department'].queryset = Department.objects.filter(
#                 student=student_user
#             )

#             self.fields['student'].queryset = Student.objects.filter(
#                 id=student_user.id
#             )

#     def clean(self):
#         cleaned_data = super().clean()
#         start = cleaned_data.get('start_date')
#         end = cleaned_data.get('end_date')

#         if start and end and start > end:
#             self.add_error('end_date', "End date cannot be before start date.")

#         return cleaned_data

# class AttendanceReportForm(forms.Form):

#     start_date = forms.DateField(
#         widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
#     )
#     end_date = forms.DateField(
#         widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
#     )

#     course = forms.ModelChoiceField(
#         queryset=Course.objects.none(),
#         required=False,
#         empty_label="All Courses",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     department = forms.ModelChoiceField(
#         queryset=Department.objects.none(),
#         required=False,
#         empty_label="All Departments",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     def __init__(self, *args, **kwargs):
#         lecturer = kwargs.pop('lecturer', None)
#         is_superuser = kwargs.pop('is_superuser', False)
#         student = kwargs.pop('student', None)

#         super().__init__(*args, **kwargs)

#         if is_superuser:
#             self.fields['course'].queryset = Course.objects.all()
#             self.fields['department'].queryset = Department.objects.all()

#         elif lecturer:
#             self.fields['course'].queryset = Course.objects.filter(
#                 courseassignment__lecturer=lecturer
#             )

#             self.fields['department'].queryset = Department.objects.filter(
#                 student__course_registrations__course__courseassignment__lecturer=lecturer
#             ).distinct()

#         elif student:
#             # ✅ STUDENT sees ONLY their courses
#             self.fields['course'].queryset = Course.objects.filter(
#                 course_registrations__student=student
#             )

#             self.fields['department'].queryset = Department.objects.filter(
#                 student=student
#             )

#         else:
#             self.fields['course'].queryset = Course.objects.none()
#             self.fields['department'].queryset = Department.objects.none()

#     def clean(self):
#         cleaned_data = super().clean()
#         start = cleaned_data.get('start_date')
#         end = cleaned_data.get('end_date')

#         if start and end and start > end:
#             self.add_error('end_date', "End date cannot be before start date.")

#         return cleaned_data

# class AttendanceReportForm(forms.Form):

#     start_date = forms.DateField(
#         widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
#     )
#     end_date = forms.DateField(
#         widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
#     )

#     course = forms.ModelChoiceField(
#         queryset=Course.objects.none(),
#         required=False,
#         empty_label="All Courses",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     department = forms.ModelChoiceField(
#         queryset=Department.objects.none(),
#         required=False,
#         empty_label="All Departments",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     def __init__(self, *args, **kwargs):
#         lecturer = kwargs.pop('lecturer', None)
#         is_superuser = kwargs.pop('is_superuser', False)
#         student = kwargs.pop('student', None)

#         super().__init__(*args, **kwargs)

#         if is_superuser:
#             self.fields['course'].queryset = Course.objects.all()
#             self.fields['department'].queryset = Department.objects.all()

#         elif lecturer:
#             # ✅ FIXED HERE
#             self.fields['course'].queryset = Course.objects.filter(
#                 assignments__lecturer=lecturer
#             ).distinct()

#             self.fields['department'].queryset = Department.objects.filter(
#                 student__course_registrations__course__assignments__lecturer=lecturer
#             ).distinct()

#         elif student:
#             self.fields['course'].queryset = Course.objects.filter(
#                 registrations__student=student
#             ).distinct()

#             self.fields['department'].queryset = Department.objects.filter(
#                 student=student
#             )

#         else:
#             self.fields['course'].queryset = Course.objects.none()
#             self.fields['department'].queryset = Department.objects.none()


# class AttendanceReportForm(forms.Form):

#     start_date = forms.DateField(
#         label="From",
#         widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
#     )

#     end_date = forms.DateField(
#         label="To",
#         widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
#     )

#     course = forms.ModelChoiceField(
#         queryset=Course.objects.none(),
#         required=False,
#         empty_label="All Courses",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     department = forms.ModelChoiceField(
#         queryset=Department.objects.none(),
#         required=False,
#         empty_label="All Departments",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     student = forms.ModelChoiceField(
#         queryset=Student.objects.none(),
#         required=False,
#         empty_label="All Students",
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     def __init__(self, *args, **kwargs):
#         lecturer = kwargs.pop('lecturer', None)
#         is_superuser = kwargs.pop('is_superuser', False)
#         student_user = kwargs.pop('student', None)

#         super().__init__(*args, **kwargs)

#         # ---------------- SUPERUSER ----------------
#         if is_superuser:
#             self.fields['course'].queryset = Course.objects.all()
#             self.fields['department'].queryset = Department.objects.all()
#             self.fields['student'].queryset = Student.objects.all()

#         # ---------------- LECTURER ----------------
#         elif lecturer:
#             self.fields['course'].queryset = Course.objects.filter(
#                 assignments__lecturer=lecturer
#             ).distinct()

#             self.fields['department'].queryset = Department.objects.filter(
#                 course__assignments__lecturer=lecturer
#             ).distinct()

#             self.fields['student'].queryset = Student.objects.filter(
#                 course_registrations__course__assignments__lecturer=lecturer
#             ).distinct()

#         # ---------------- STUDENT ----------------
#         elif student_user:
#             self.fields['course'].queryset = Course.objects.filter(
#                 registrations__student=student_user
#             ).distinct()

#             self.fields['department'].queryset = Department.objects.filter(
#                 students=student_user
#             )

#             self.fields['student'].queryset = Student.objects.filter(
#                 id=student_user.id
#             )

#         else:
#             self.fields['course'].queryset = Course.objects.none()
#             self.fields['department'].queryset = Department.objects.none()
#             self.fields['student'].queryset = Student.objects.none()

#     def clean(self):
#         cleaned = super().clean()
#         start = cleaned.get("start_date")
#         end = cleaned.get("end_date")

#         if start and end and start > end:
#             self.add_error("end_date", "End date cannot be before start date.")

#         return cleaned

class AttendanceReportForm(forms.Form):

    start_date = forms.DateField(
        label="From",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    end_date = forms.DateField(
        label="To",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        required=False,
        empty_label="All Courses",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        required=False,
        empty_label="All Departments",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        required=False,
        empty_label="All Students",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        lecturer = kwargs.pop('lecturer', None)
        is_superuser = kwargs.pop('is_superuser', False)
        student = kwargs.pop('student', None)

        super().__init__(*args, **kwargs)

        # ---------------- ADMIN ----------------
        if is_superuser:
            self.fields['course'].queryset = Course.objects.all()
            self.fields['department'].queryset = Department.objects.all()
            self.fields['student'].queryset = Student.objects.all()

        # ---------------- LECTURER ----------------
        elif lecturer:
            self.fields['course'].queryset = Course.objects.filter(
                assignments__lecturer=lecturer
            ).distinct()

            self.fields['department'].queryset = Department.objects.filter(
                course__assignments__lecturer=lecturer
            ).distinct()

            self.fields['student'].queryset = Student.objects.filter(
                course_registrations__course__assignments__lecturer=lecturer
            ).distinct()

        # ---------------- STUDENT (SELF VIEW ONLY) ----------------
        elif student:
            self.fields['course'].queryset = Course.objects.filter(
                registrations__student=student
            ).distinct()

            self.fields['department'].queryset = Department.objects.filter(
                students=student
            )

            self.fields['student'].queryset = Student.objects.filter(
                id=student.id
            )

        else:
            self.fields['course'].queryset = Course.objects.none()
            self.fields['department'].queryset = Department.objects.none()
            self.fields['student'].queryset = Student.objects.none()

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")

        if start and end and start > end:
            self.add_error("end_date", "End date cannot be before start date.")

        return cleaned