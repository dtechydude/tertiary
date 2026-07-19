from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.db import models
import datetime
#converting html to pdf
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
# from xhtml2pdf import pisa
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from students.models import Student, Hostel, GraduationRecord
from staff.models import Lecturer
from students.forms import StudentUpdateForm, SuperUserStudentUpdateForm

from users.forms import UserRegisterForm
from curriculum.models import Session, Semester, Programme, SchoolIdentity, Level, Department, CourseRegistration, Course
import io
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from django.http import FileResponse
import csv
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.template.loader import get_template
from xhtml2pdf import pisa

from django.db import IntegrityError, transaction, models
from django.core.exceptions import ValidationError
from datetime import date
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from curriculum.utils.identity import get_school_identity_for_student
from curriculum.services.registration import resolve_registration_policy

from django.utils import timezone
from decimal import Decimal, InvalidOperation




# TERTIARY LOGIC ===============================================
@login_required
def student_list(request):
    # 1. AUTHENTICATION & ROLE CHECK
    user = request.user
    is_admin = user.is_superuser or user.is_staff
    is_teacher = hasattr(user, 'teacher')

    # 2. DATA FILTERING LOGIC
    # Base queryset: Active students only for the general list
    students_queryset = Student.objects.select_related('user', 'department', 'level', 'programme').exclude(student_status='graduated')

    if is_admin:
        all_students = students_queryset.order_by('department', 'matric_number')
    elif is_teacher:
        # In tertiary, teachers see students in their Department
        teacher_dept = user.teacher.department if hasattr(user.teacher, 'department') else None
        all_students = students_queryset.filter(department=teacher_dept).order_by('level', 'matric_number')
    else:
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    # 3. CSV EXPORT LOGIC
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = f"Students_Export_{timezone.now().strftime('%Y%m%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Matric Number', 'Full Name', 'Department', 'Programme', 
            'Level', 'Gender', 'Student Type', 'Fee Balance', 'Status'
        ])

        for s in all_students:
            writer.writerow([
                s.matric_number,
                s.get_full_name(),
                s.department.name if s.department else 'N/A',
                s.programme.name if s.programme else 'N/A',
                s.level.name if s.level else 'N/A',
                s.get_gender_display(),
                s.get_student_type_display(),
                s.fee_balance,
                s.get_student_status_display()
            ])
        return response

    # 4. RENDER
    return render(request, 'students/student_list.html', {
        'all_students': all_students,
        'is_admin': is_admin
    })


# # TERTIARY LOGIC =============================================================================
# class StudentDetailView(LoginRequiredMixin, DetailView):
#     """
#     Used by Staff/Admins to view any student's profile via Matric Number.
#     """
#     model = Student
#     template_name = 'students/student_detail.html'
#     context_object_name = 'student'

#     def get_object(self):
#         # Updated from USN=id_ to matric_number=matric_number
#         matric_number = self.kwargs.get("matric_number")
#         return get_object_or_404(Student, matric_number=matric_number)

#     def get_context_data(self, **kwargs):
#         from students.services.dashboard import build_student_dashboard_context

#         context = super().get_context_data(**kwargs)
#         context.update(build_student_dashboard_context(self.object))
#         return context


# # TERTIARY LOGIC===================================================
# class StudentSelfDetailView(LoginRequiredMixin, DetailView):
#     """
#     Used by the logged-in student to view their own profile — including
#     their current course registration, fee clearance status, and
#     published results/GPA (pulled from the finance and results apps via
#     students.services.dashboard).
#     """
#     model = Student
#     template_name = 'students/student_self_detail.html'
#     context_object_name = 'student'

#     def dispatch(self, request, *args, **kwargs):
#         # Check if student profile exists before proceeding to get_object
#         if not hasattr(request.user, 'student'):
#             messages.error(request, "Your student profile could not be found. Please contact administration.")
#             return redirect('pages:portal-home')
#         return super().dispatch(request, *args, **kwargs)

#     def get_object(self, queryset=None):
#         return self.request.user.student

#     def get_context_data(self, **kwargs):
#         from students.services.dashboard import build_student_dashboard_context

#         context = super().get_context_data(**kwargs)
#         context.update(build_student_dashboard_context(self.object))
#         return context



from django.contrib.auth.mixins import LoginRequiredMixin


# TERTIARY LOGIC =============================================================================
class StudentDetailView(LoginRequiredMixin, DetailView):
    """
    Used by Staff/Admins to view any student's profile via Matric Number.
    """
    model = Student
    template_name = 'students/student_detail.html'
    context_object_name = 'student'

    def dispatch(self, request, *args, **kwargs):
        # LoginRequiredMixin only guarantees "logged in" — it does not
        # restrict this to staff, despite the docstring above. Without
        # this check, any authenticated student could view any other
        # student's full profile (fee balance, medical info, guardian
        # details, results) just by changing the matric number in the URL.
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "You do not have permission to view this page.")
            return redirect('pages:portal-home')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        matric_number = self.kwargs.get("matric_number")
        return get_object_or_404(
            Student.objects.select_related('department__faculty', 'level', 'programme', 'user__profile'),
            matric_number=matric_number,
        )

    def get_context_data(self, **kwargs):
        from students.services.dashboard import build_student_dashboard_context

        context = super().get_context_data(**kwargs)
        context.update(build_student_dashboard_context(self.object))
        return context


# TERTIARY LOGIC===================================================
class StudentSelfDetailView(LoginRequiredMixin, DetailView):
    """
    Used by the logged-in student to view their own profile — including
    their current course registration, fee clearance status, and
    published results/GPA (pulled from the finance and results apps via
    students.services.dashboard).
    """
    model = Student
    template_name = 'students/student_self_detail.html'
    context_object_name = 'student'

    def dispatch(self, request, *args, **kwargs):
        # Authentication check must run first — previously the student-
        # profile check ran before super().dispatch(), so an anonymous
        # visitor (who also fails hasattr(user, 'student')) got the
        # "profile not found" message and a redirect to the portal home,
        # instead of LoginRequiredMixin's normal redirect to the login page.
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        if not hasattr(request.user, 'student'):
            messages.error(request, "Your student profile could not be found. Please contact administration.")
            return redirect('pages:portal-home')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.request.user.student

    def get_context_data(self, **kwargs):
        from students.services.dashboard import build_student_dashboard_context

        context = super().get_context_data(**kwargs)
        context.update(build_student_dashboard_context(self.object))
        return context


# TERTIARY LOGIC ===============================
# Student Search List

def student_search_list(request):
    """
    Unified view to list all students or filter them based on a search query.
    """
    # 1. Get the base queryset
    student_list = Student.objects.all().order_by('matric_number')
    
    # 2. Extract search query from GET request
    query = request.GET.get('search', '').strip()

    # 3. Apply filtering if a query exists
    if query:
        student_list = student_list.filter(
            Q(user__first_name__icontains=query) | 
            Q(user__last_name__icontains=query) | 
            Q(matric_number__icontains=query) | 
            Q(level__name__icontains=query) | 
            Q(department__name__icontains=query) |  # Added for tertiary flow
            Q(programme__name__icontains=query) |   # Added for tertiary flow
            Q(guardian_name__icontains=query)
        ).distinct()

    # 4. Pagination (30 students per page)
    page = request.GET.get('page', 1)
    paginator = Paginator(student_list, 30)
    
    try:
        students = paginator.page(page)
    except PageNotAnInteger:
        students = paginator.page(1)
    except EmptyPage:
        students = paginator.page(paginator.num_pages)

    context = {
        'students': students,
        'query': query,
    }
    
    return render(request, 'students/search_student_list.html', context)


@login_required
def student_boarder_list(request):
    if not (request.user.is_superuser or request.user.is_staff):
        return render(request, 'pages/portal_home.html')

    boarder_students = Student.objects.filter(
        assigned_room__isnull=False   # ✅ THIS IS THE REAL BOARDER LOGIC
    ).exclude(
        student_status='graduated'
    ).select_related(
        'hostel_name',
        'assigned_room',
        'level',
        'programme',
        'user'
    ).order_by('-date_admitted')

    return render(request, 'students/student_boarder_list.html', {
        'boarder_students': boarder_students
    })



# ==========================================================================
# GRADUATED Students Tertiary

def is_authorized_staff(user):
    return user.is_superuser or user.is_staff

@user_passes_test(is_authorized_staff)
def graduate_students_view(request):
    """
    Logic to move students from 'active' to 'graduated' status.
    """
    levels = Level.objects.all().order_by('name')
    sessions = Session.objects.all().order_by('-start_date')
    students = Student.objects.none()
    selected_level = None

    # Step 1: Filter students by Level to select who is ready for graduation
    level_id = request.GET.get('level')
    if level_id:
        selected_level = get_object_or_404(Level, id=level_id)
        students = Student.objects.filter(
            level=selected_level, 
            student_status='active'
        ).order_by('user__last_name')

    if request.method == "POST":
        selected_ids = request.POST.getlist('selected_students')
        session_id = request.POST.get('graduation_session_id')
        
        if not selected_ids:
            messages.error(request, "Please select at least one student.")
            return redirect(request.path)

        graduation_session = get_object_or_404(Session, id=session_id)

        try:
            with transaction.atomic():
                # Get the 'Alumni' level (create if doesn't exist)
                alumni_level, _ = Level.objects.get_or_create(name='Alumni')
                
                students_to_grad = Student.objects.filter(id__in=selected_ids)
                count = students_to_grad.count()

                for student in students_to_grad:
                    # Create the record using the new tertiary model fields
                    GraduationRecord.objects.create(
                        student=student,
                        session=graduation_session,
                        programme=student.programme,
                        department=student.department,
                        level_completed=student.level,
                        date_graduated=timezone.now().date(),
                        remarks=request.POST.get(f'remarks_{student.id}', '')
                    )

                    # Update student status
                    student.student_status = 'graduated'
                    student.level = alumni_level
                    student.save()

            messages.success(request, f"Successfully moved {count} students to Alumni status.")
            return redirect('students:alumni_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'students/graduate_students.html', {
        'levels': levels,
        'sessions': sessions,
        'students': students,
        'selected_level': selected_level,
        'title': 'Process Graduation',
    })

@user_passes_test(is_authorized_staff)
def alumni_list_view(request):
    """
    Comprehensive list of graduates with filtering and CSV export.
    """
    queryset = Student.objects.filter(student_status='graduated').select_related(
        'user', 'department', 'programme'
    ).prefetch_related('graduation_records')

    # Filtering Logic
    session_id = request.GET.get('session')
    dept_id = request.GET.get('department')
    q = request.GET.get('q')

    if session_id:
        queryset = queryset.filter(graduation_records__session_id=session_id)
    if dept_id:
        queryset = queryset.filter(department_id=dept_id)
    if q:
        queryset = queryset.filter(
            models.Q(user__first_name__icontains=q) |
            models.Q(user__last_name__icontains=q) |
            models.Q(matric_number__icontains=q)
        )

    queryset = queryset.distinct().order_by('-graduation_records__date_graduated')

    # CSV Export
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename="alumni_records.csv"'
        writer = csv.writer(response)
        writer.writerow(["Matric No", "Name", "Programme", "Department", "Graduation Date"])
        for s in queryset:
            writer.writerow([s.matric_number, s.get_full_name(), s.programme, s.department, s.graduation_records.first().date_graduated if s.graduation_records.exists() else "N/A"])
        return response

    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'students/alumni_list.html', {
        'alumni': page_obj,
        'sessions': Session.objects.all().order_by('-start_date'),
        'departments': Department.objects.all(),
    })

@user_passes_test(is_authorized_staff)
def readmit_student(request, student_id):
    """
    Moves a student from 'graduated' back to 'active'.
    """
    student = get_object_or_404(Student, id=student_id, student_status='graduated')
    levels = Level.objects.exclude(name='Alumni')

    if request.method == 'POST':
        new_level_id = request.POST.get('new_level')
        new_level = get_object_or_404(Level, id=new_level_id)
        
        student.level = new_level
        student.student_status = 'active'
        student.save()
        
        # Optional: Delete graduation record if readmission is a correction
        # GraduationRecord.objects.filter(student=student).delete()

        messages.success(request, f"{student.get_full_name()} readmitted to {new_level.name}.")
        return redirect('students:alumni_list')

    return render(request, 'students/readmit_student.html', {'student': student, 'levels': levels})

#  End Graduated View Code for tertiary
#======================================================================================

# TERTIARY LOGIC=========================================
# Promotion logic

def is_authorized_to_manage(user):
    return user.is_superuser or user.groups.filter(name='Registrar').exists()

@user_passes_test(is_authorized_to_manage)
def promote_students_view(request):
    """
    Promotes selected students from one Level to another within a
    Department. Staff pick both the source and target level explicitly
    rather than relying on an inferred "next level," since Level has no
    ordering/rank field in the current curriculum schema — guessing the
    "next" level from name alone would be unreliable across programmes.
    """
    levels = Level.objects.all().order_by('name')
    departments = Department.objects.all()
    students = Student.objects.none()
    selected_from_level = None

    from_level_id = request.GET.get('level')
    dept_id = request.GET.get('dept')
    if from_level_id:
        selected_from_level = get_object_or_404(Level, id=from_level_id)
        students = Student.objects.filter(
            level=selected_from_level, student_status='active'
        ).select_related('user', 'department').order_by('user__last_name')
        if dept_id:
            students = students.filter(department_id=dept_id)

    if request.method == 'POST':
        from_level_id = request.POST.get('from_level')
        to_level_id = request.POST.get('to_level')
        selected_student_ids = request.POST.getlist('selected_students')

        if not from_level_id or not to_level_id or not selected_student_ids:
            messages.error(request, "Please select a source level, a target level, and at least one student.")
            return redirect('students:promote_students')

        if from_level_id == to_level_id:
            messages.error(request, "Source and target level cannot be the same.")
            return redirect('students:promote_students')

        try:
            from_level = get_object_or_404(Level, id=from_level_id)
            to_level = get_object_or_404(Level, id=to_level_id)

            with transaction.atomic():
                qs = Student.objects.filter(id__in=selected_student_ids, level=from_level)
                count = qs.count()
                qs.update(level=to_level)

            messages.success(request, f"Successfully promoted {count} students to {to_level.name}.")
        except Exception as e:
            messages.error(request, f"Promotion failed: {str(e)}")

        return redirect('students:promote_students')

    context = {
        'levels': levels,
        'departments': departments,
        'students': students,
        'selected_from_level': selected_from_level,
        'title': 'Level Promotion',
    }
    return render(request, 'students/promote_students.html', context)





 # Hostel List
@login_required
def hostel_list(request):
    hostel_list = Hostel.objects.all()
    # boarder_student = Student.objects.all().order_by('-date_admitted')

    context ={
        'hostel_list': hostel_list,
    }         
    
    return render(request, 'students/hostel_list.html', context)
    


# TERTIARY LOGIC for students count ===================================================
#count students in each class

# @login_required
# def student_distribution_view(request):
#     """
#     Displays the headcount of students broken down by 
#     Programme, Department, and Level.
#     """
#     # 1. Total Count per Programme
#     programme_counts = Student.objects.values('programme__name').annotate(
#         total=Count('id')
#     ).order_by('programme__name')

#     # 2. Total Count per Department
#     department_counts = Student.objects.values('department__name').annotate(
#         total=Count('id')
#     ).order_by('department__name')

#     # 3. Detailed breakdown (Level + Department)
#     # Changed 'current_level__name' to 'level__name' to match your model
#     detailed_counts = Student.objects.values(
#         'department__name', 
#         'level__name' 
#     ).annotate(
#         total=Count('id')
#     ).order_by('department__name', 'level__id') # Using level__id for ordering

#     # 4. Context for the logged-in student
#     peers_count = 0
#     if hasattr(request.user, 'student'):
#         # Changed current_level to level to match your model
#         peers_count = Student.objects.filter(
#             level=request.user.student.level,
#             department=request.user.student.department
#         ).count()

#     context = {
#         'programme_counts': programme_counts,
#         'department_counts': department_counts,
#         'detailed_counts': detailed_counts,
#         'peers_count': peers_count,
#     }

#     return render(request, 'students/student_distribution.html', context)

import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render

from students.models import Student


def _get_detailed_distribution():
    """
    Shared query: Faculty -> Department -> Level -> Programme headcount.
    Used by both the on-screen report and the CSV export so the two
    can never drift out of sync.
    """
    return Student.objects.values(
        'department__faculty__name',
        'department__name',
        'level__name',
        'programme__name',
    ).annotate(
        total=Count('id')
    ).order_by(
        'department__faculty__name',
        'department__name',
        'level__id',
        'programme__name',
    )


@login_required
def student_distribution_view(request):
    """
    Displays the headcount of students broken down by Faculty, Department,
    Level, and Programme, plus a hierarchical Faculty -> Department view
    for the standalone report page.

    Assumes Department has a ForeignKey to Faculty (department.faculty).
    If your curriculum.models.Department uses a different field name for
    that relationship, update the `department__faculty__...` lookups below.
    """

    total_students = Student.objects.count()

    # 1. Total Count per Faculty
    faculty_counts = Student.objects.values(
        'department__faculty__name'
    ).annotate(
        total=Count('id')
    ).order_by('department__faculty__name')

    # 2. Total Count per Department (flat, kept for backward compatibility /
    #    quick reference table)
    department_counts = Student.objects.values(
        'department__faculty__name', 'department__name'
    ).annotate(
        total=Count('id')
    ).order_by('department__faculty__name', 'department__name')

    # 3. Total Count per Programme
    programme_counts = Student.objects.values('programme__name').annotate(
        total=Count('id')
    ).order_by('programme__name')

    # 4. Total Count per Level
    level_counts = Student.objects.values('level__name').annotate(
        total=Count('id')
    ).order_by('level__id')

    # 5. Full detailed breakdown: Faculty -> Department -> Level -> Programme
    detailed_counts = _get_detailed_distribution()

    # 6. Build a nested Faculty -> Department -> rows structure so the
    #    template can render an accordion instead of one long flat table.
    faculty_map = {}

    for row in detailed_counts:
        faculty_name = row['department__faculty__name'] or 'Unassigned Faculty'
        department_name = row['department__name'] or 'Unassigned Department'

        faculty_entry = faculty_map.setdefault(faculty_name, {
            'name': faculty_name,
            'total': 0,
            'departments': {},
        })

        department_entry = faculty_entry['departments'].setdefault(department_name, {
            'name': department_name,
            'total': 0,
            'rows': [],
        })

        department_entry['rows'].append({
            'level': row['level__name'] or 'Unspecified',
            'programme': row['programme__name'] or 'Unspecified',
            'total': row['total'],
        })
        department_entry['total'] += row['total']
        faculty_entry['total'] += row['total']

    # Convert dicts -> sorted lists for stable, predictable template iteration
    faculties = []
    for faculty_name in sorted(faculty_map.keys()):
        faculty_entry = faculty_map[faculty_name]
        faculty_entry['departments'] = sorted(
            faculty_entry['departments'].values(),
            key=lambda d: d['name']
        )
        faculties.append(faculty_entry)

    # 7. Context for the logged-in student — how many peers share their
    #    exact Level + Department
    peers_count = 0
    if hasattr(request.user, 'student'):
        peers_count = Student.objects.filter(
            level=request.user.student.level,
            department=request.user.student.department
        ).count()

    context = {
        'total_students': total_students,
        'faculty_counts': faculty_counts,
        'department_counts': department_counts,
        'programme_counts': programme_counts,
        'level_counts': level_counts,
        'detailed_counts': detailed_counts,
        'faculties': faculties,
        'faculty_count': len(faculties),
        'department_count': len({row['department__name'] for row in department_counts}),
        'peers_count': peers_count,
    }

    return render(request, 'students/student_distribution.html', context)


@login_required
def student_distribution_csv_export(request):
    """
    Offline copy of the full Faculty -> Department -> Level -> Programme
    breakdown, for registrars/admin who need it outside the portal
    (board reports, accreditation submissions, backups, etc.).
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponse("Not permitted.", status=403)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_enrollment_distribution.csv"'

    writer = csv.writer(response)
    writer.writerow(['Faculty', 'Department', 'Level', 'Programme', 'Student Count'])

    total = 0
    for row in _get_detailed_distribution():
        writer.writerow([
            row['department__faculty__name'] or 'Unassigned',
            row['department__name'] or 'Unassigned',
            row['level__name'] or 'Unspecified',
            row['programme__name'] or 'Unspecified',
            row['total'],
        ])
        total += row['total']

    writer.writerow([])
    writer.writerow(['', '', '', 'Total Students', total])

    return response



# TERTIARY LOGIC ===============================================================    
# new student update form
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Student
from .forms import StudentUpdateForm, SuperUserStudentUpdateForm

class StudentUpdateView(LoginRequiredMixin, UpdateView):
    model = Student
    template_name = 'students/student_update_form.html'

    def dispatch(self, request, *args, **kwargs):
        """Only staff or superusers can access this view."""
        if not request.user.is_staff:
            messages.error(request, "Access Denied: You do not have permission to edit student records.")
            return redirect('pages:portal-home')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        """Retrieve student using matric_number instead of USN."""
        matric = self.kwargs.get("matric_number")
        return get_object_or_404(Student, matric_number=matric)

    def get_form_class(self):
        """Different forms based on administrative hierarchy."""
        if self.request.user.is_superuser:
            return SuperUserStudentUpdateForm
        return StudentUpdateForm

    def get_success_url(self):
        """Redirect to the updated profile view."""
        return reverse_lazy('students:student-detail', kwargs={'matric_number': self.object.matric_number})


class StudentDeleteView(LoginRequiredMixin, DeleteView):
    template_name = 'students/student_delete.html'
    success_url = reverse_lazy('students:student-list')
    
    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Student, id=id_)
    

class MyTeacherDetailView(DetailView):
    template_name = 'students/my_teacher_detail.html'
    context_object_name = 'teacher'
    queryset = Lecturer.objects.all()

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Lecturer, id=id_)
    

# TERTIARY VIEW FOR =============================================
# My Class Mates
@login_required
def my_classmates_view(request):
    try:
        # Get the logged-in user's student profile
        # select_related avoids extra DB hits for tertiary metadata
        student = Student.objects.select_related('department', 'programme', 'level', 'user').get(user=request.user)
        
        # Tertiary Logic: Classmates share Department, Programme, and Level
        department = student.department
        programme = student.programme
        level = student.level

        if department and level:
            # Filter by the academic "Cohort"
            classmates = Student.objects.filter(
                department=department,
                level=level,
                programme=programme,
                student_status='active' # Only show currently enrolled peers
            ).exclude(user=request.user).select_related('user')
        else:
            classmates = Student.objects.none()
            
        context = {
            'student': student,
            'department': department,
            'programme': programme,
            'level': level,
            'classmates': classmates,
        }
        return render(request, 'students/my_classmates.html', context)

    except Student.DoesNotExist:
        return render(request, 'students/no_student_profile.html', {})
    except Exception as e:
        return render(request, 'students/error.html', {'error_message': str(e)})


# TERTIARY LOGIC ==============================================
# Student ID Card

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views import View
from .models import Student
# Ensure SchoolIdentity is imported from the correct app

# class StudentIDCardView(LoginRequiredMixin, View):
#     """
#     Displays a printable ID card for a specific student using Matric Number.
#     """
#     def get(self, request, matric_number):
#         # Fetch using matric_number to align with your existing system logic
#         student = get_object_or_404(
#             Student.objects.select_related('user', 'department', 'level'), 
#             matric_number=matric_number
#         )
        
#         school_identity = SchoolIdentity.objects.first()

#         context = {
#             'student': student,
#             'school_identity': school_identity,
#         }
#         return render(request, 'students/id_card_single.html', context)

from curriculum.utils.identity import get_school_identity_for_student


class StudentIDCardView(LoginRequiredMixin, View):

    def get(self, request, matric_number):

        student = get_object_or_404(
            Student.objects.select_related('user', 'department', 'level'),
            matric_number=matric_number
        )

        school_identity = get_school_identity_for_student(student)

        return render(request, 'students/id_card_single.html', {
            'student': student,
            'school_identity': school_identity,
        })


# class BulkStudentIDCardView(LoginRequiredMixin, View):
#     """
#     View to generate multiple ID cards at once, filtered by tertiary parameters.
#     """
#     def get(self, request):
#         # Fetching tertiary filters from the GET request
#         level_id = request.GET.get('level')
#         dept_id = request.GET.get('department')
#         prog_id = request.GET.get('programme')

#         # Optimizing query with select_related for level/dept/programme
#         students = Student.objects.all().select_related('level', 'department', 'programme')

#         if level_id:
#             students = students.filter(level_id=level_id)
#         if dept_id:
#             students = students.filter(department_id=dept_id)
#         if prog_id:
#             students = students.filter(programme_id=prog_id)

#         # Ensure we only show ID cards for "Active" students
#         students = students.filter(student_status='active')

#         context = {
#             'students': students,
#             'levels': Level.objects.all(),
#             'departments': Department.objects.all(),
#             'programmes': Programme.objects.all(),
#             'selected_level': level_id,
#             'selected_dept': dept_id,
#             'school_identity': SchoolIdentity.objects.first(),
#         }
        
#         return render(request, 'students/id_card_bulk.html', context)

from curriculum.utils.identity import get_school_identity_for_student


class BulkStudentIDCardView(LoginRequiredMixin, View):

    def get(self, request):

        level_id = request.GET.get('level')
        dept_id = request.GET.get('department')
        prog_id = request.GET.get('programme')

        students = Student.objects.all().select_related(
            'level', 'department', 'programme'
        )

        if level_id:
            students = students.filter(level_id=level_id)
        if dept_id:
            students = students.filter(department_id=dept_id)
        if prog_id:
            students = students.filter(programme_id=prog_id)

        students = students.filter(student_status='active')

        # 🔥 KEY FIX: dynamic identity resolution
        first_student = students.first()
        school_identity = get_school_identity_for_student(first_student)

        return render(request, 'students/id_card_bulk.html', {
            'students': students,
            'levels': Level.objects.all(),
            'departments': Department.objects.all(),
            'programmes': Programme.objects.all(),
            'selected_level': level_id,
            'selected_dept': dept_id,
            'school_identity': school_identity,
        })


#TERTIARY LOGIC ============================================================
# LOGIC FOR STUDENT ARCHIVE
import csv
from django.http import HttpResponse
from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import models
from django.contrib.admin.views.decorators import staff_member_required
from .models import Student, Session, Department

# --- Helper Function for CSV Export ---
def export_students_csv(queryset):
    """
    Generates a CSV response from a student queryset.
    Accesses names via the User relationship.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tertiary_student_archive.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Matric Number",
        "Full Name",
        "Gender",
        "Status",
        "Department",
        "Programme",
        "Date Admitted",
    ])

    for s in queryset:
        # Accessing names from the related User model
        full_name = f"{s.user.last_name} {s.user.first_name} {s.middle_name or ''}".strip()
        dept_name = s.department.name if s.department else "N/A"
        prog_name = s.programme.name if s.programme else "N/A"

        writer.writerow([
            s.matric_number,
            full_name.upper(),
            s.gender,
            s.student_status,
            dept_name,
            prog_name,
            s.date_admitted,
        ])

    return response

# --------------------------------------------------

@staff_member_required
def student_archive(request):
    """
    Displays archived records with fixes for User-model name fields
    and Tertiary filtering logic.
    """
    # 1. Base Setup
    archived_status = ['graduated', 'dropped', 'expelled', 'suspended', 'alumni']

    # 2. Base Queryset
    students = Student.objects.filter(
        student_status__in=archived_status
    ).select_related('user', 'department', 'programme', 'level').prefetch_related(
        'graduation_records__session'
    ).order_by('-date_admitted', 'user__last_name')

    # --- GET FILTERS ---
    q = request.GET.get('q')
    status_filter = request.GET.get('status')
    session_filter = request.GET.get('session') # Note: Verify field name for this in your model
    dept_filter = request.GET.get('department')
    page = request.GET.get('page', 1)

    # --- APPLY FILTERS ---
    if q:
        # FIXED: Searching via user__first_name and user__last_name
        students = students.filter(
            models.Q(user__first_name__icontains=q) |
            models.Q(user__last_name__icontains=q) |
            models.Q(matric_number__icontains=q)
        )

    if status_filter and status_filter != "all":
        students = students.filter(student_status=status_filter)

    # Filters by the session in which the student's GraduationRecord was
    # created — Student itself has no direct session FK; that history
    # lives in GraduationRecord (students.models).
    if session_filter and session_filter != "all":
        students = students.filter(graduation_records__session_id=session_filter).distinct()
        
    if dept_filter and dept_filter != "all":
        students = students.filter(department_id=dept_filter)

    # --- CSV EXPORT ---
    if request.GET.get("export") == "csv":
        return export_students_csv(students)

    # --- PAGINATION ---
    paginator = Paginator(students, 20)
    
    try:
        students_page = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        students_page = paginator.page(1)

    # --- PREPARE CONTEXT ---
    # Using a generic fetch for sessions since the related name may vary
    sessions = Session.objects.all().order_by('-start_date')
    departments = Department.objects.all().order_by('name')

    # Preserve filters across pagination
    params = request.GET.copy()
    params.pop('page', None)
    query_string = params.urlencode()

    return render(request, "students/archive.html", {
        "students": students_page,
        "sessions": sessions,
        "departments": departments,
        "selected_status": status_filter,
        "selected_session": session_filter,
        "selected_dept": dept_filter,
        "q": q,
        "query_string": query_string,
    })

# TERTIARY LOGIC
# Course registration
def _export_course_registrations_csv(queryset):
    """CSV export for the admin-facing 'Recent Registrations' report on
    the course registration page. Separate from export_students_csv
    (student archive export) since the columns are entirely different."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="course_registrations.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Student Name", "Matric Number", "Course Code", "Course Title",
        "Session", "Semester", "Validated", "Registered At",
    ])

    for reg in queryset.select_related('student__user', 'course', 'session', 'semester'):
        writer.writerow([
            reg.student.get_full_name(),
            reg.student.matric_number,
            reg.course.course_code,
            reg.course.title,
            str(reg.session),
            str(reg.semester),
            "Yes" if reg.is_validated else "No",
            reg.registered_at.strftime("%Y-%m-%d %H:%M"),
        ])

    return response


# @login_required
# def course_registration_view(request):
#     from finance.services.payments import FinanceService
#     from finance.services.exam_eligibility import ExamEligibilityService

#     user = request.user
#     student = getattr(user, 'student', None)
#     is_admin = user.is_superuser or user.is_staff

#     if not student and not is_admin:
#         messages.error(request, "Access denied.")
#         return redirect("pages:portal-home")

#     current_session = Session.objects.filter(is_current=True).first()
#     current_semester = Semester.objects.filter(is_current=True).first()

#     # --- REGISTRATION PHASE LOGIC ---
#     today = timezone.localdate()
#     reg_phase = "CLOSED"
#     late_fee = 0
#     debug_msg = ""

#     if current_semester:
#         # Priority 1: Manual Override
#         if current_semester.is_reg_active:
#             reg_phase = "OPEN"
#             debug_msg = "Manual override active."
#         # Priority 2: Date Windows
#         elif current_semester.reg_start_date and current_semester.reg_end_date:
#             if today < current_semester.reg_start_date:
#                 reg_phase = "CLOSED"
#                 debug_msg = f"Starts {current_semester.reg_start_date}"
#             elif today <= current_semester.reg_end_date:
#                 reg_phase = "OPEN"
#                 debug_msg = "Normal registration period."
#             elif current_semester.late_reg_end_date and today <= current_semester.late_reg_end_date:
#                 reg_phase = "LATE"
#                 late_fee = current_semester.late_reg_fee
#                 debug_msg = "Late registration period."
#             else:
#                 reg_phase = "CLOSED"
#                 debug_msg = "Deadlines passed."
#         else:
#             debug_msg = "Dates not configured."

#     # --- POST HANDLER ---
#     if request.method == "POST":
#         if not student:
#             messages.error(request, "Admins cannot modify records.")
#             return redirect("students:course-registration")

#         action = request.POST.get("action", "register")

#         # ---------------------------------------------------------
#         # ACTION 1: Save course registration (unchanged sync pattern)
#         # ---------------------------------------------------------
#         if action == "register":
#             if reg_phase == "CLOSED":
#                 messages.error(request, "The portal is currently closed.")
#                 return redirect("students:course-registration")

#             selected_course_ids = [int(c_id) for c_id in request.POST.getlist("courses")]

#             # Enforce the programme/level's unit policy before touching the
#             # database (curriculum.RegistrationPolicy). MAXIMUM is a hard
#             # block (a real resource/administrative cap). MINIMUM is a
#             # warning only, never a block — if the available course list
#             # for this department/level/semester doesn't even add up to
#             # the configured minimum, a hard block would make registration
#             # permanently impossible for every student in that cohort.
#             if selected_course_ids:
#                 selected_courses = Course.objects.filter(id__in=selected_course_ids)
#                 total_units = sum(c.credit_unit for c in selected_courses)
#                 try:
#                     policy = resolve_registration_policy(student.level)
#                     if total_units > policy.max_units_per_semester:
#                         messages.error(
#                             request,
#                             f"You selected {total_units} unit(s), which exceeds the maximum of "
#                             f"{policy.max_units_per_semester} allowed for your level. "
#                             f"Please deselect a course and try again."
#                         )
#                         return redirect("students:course-registration")
#                     if total_units < policy.min_units_per_semester:
#                         messages.warning(
#                             request,
#                             f"Note: {total_units} unit(s) is below the recommended minimum of "
#                             f"{policy.min_units_per_semester} for your level. Your registration "
#                             f"was still saved — register more courses if/when more become available."
#                         )
#                 except ValidationError:
#                     # No RegistrationPolicy configured yet for this level/programme —
#                     # don't block registration just because policy setup is incomplete.
#                     pass

#             try:
#                 with transaction.atomic():
#                     # Sync: Delete all existing then recreate
#                     CourseRegistration.objects.filter(
#                         student=student, session=current_session, semester=current_semester
#                     ).delete()

#                     if selected_course_ids:
#                         new_regs = [
#                             CourseRegistration(
#                                 student=student, course_id=c_id,
#                                 session=current_session, semester=current_semester
#                             ) for c_id in selected_course_ids
#                         ]
#                         created_regs = CourseRegistration.objects.bulk_create(new_regs)

#                         # Bill each newly registered course's fee (finance app) —
#                         # without this, a course with a nonzero cost would never
#                         # show up as something the student owes.
#                         for reg in created_regs:
#                             FinanceService.ensure_course_fee_item(reg)

#                         messages.success(request, "Course registration updated successfully.")
#                     else:
#                         messages.warning(request, "Your registration has been cleared.")
#                 return redirect("students:course-registration")
#             except Exception as e:
#                 messages.error(request, f"System Error: {e}")

#         # ---------------------------------------------------------
#         # ACTION 2: Submit a payment claim covering one or more
#         # outstanding items (course fees and/or mandatory fees),
#         # selected and optionally part-paid by the student.
#         # ---------------------------------------------------------
#         elif action == "submit_payment":
#             from finance.models import PaymentItem

#             reference = request.POST.get("reference", "").strip()
#             method = request.POST.get("method", "bank_transfer")
#             selected_item_ids = request.POST.getlist("pay_items")

#             if not reference:
#                 messages.error(request, "Please provide a payment reference (e.g. your bank transfer reference).")
#                 return redirect("students:course-registration")

#             if not selected_item_ids:
#                 messages.error(request, "Select at least one fee to pay for.")
#                 return redirect("students:course-registration")

#             allocations = {}
#             total_amount = Decimal("0.00")
#             for item_id in selected_item_ids:
#                 item = get_object_or_404(PaymentItem, pk=item_id, student=student)
#                 raw_amount = request.POST.get(f"amount_{item_id}", "").strip().replace(",", "")
#                 try:
#                     amount = Decimal(raw_amount) if raw_amount else item.balance
#                 except InvalidOperation:
#                     amount = item.balance
#                 # Never allow paying more than what's actually owed, and
#                 # never a non-positive amount.
#                 amount = min(amount, item.balance)
#                 if amount > 0:
#                     allocations[item.id] = amount
#                     total_amount += amount

#             if not allocations:
#                 messages.error(request, "Nothing to pay — the selected item(s) are already cleared.")
#                 return redirect("students:course-registration")

#             try:
#                 FinanceService.record_payment(
#                     student=student,
#                     reference=reference,
#                     amount=total_amount,
#                     method=method,
#                     allocations=allocations,
#                     mark_successful=False,  # goes to PENDING until a bursary officer approves it
#                 )
#                 messages.success(
#                     request,
#                     f"Payment of ₦{total_amount:,.2f} submitted for approval. "
#                     f"You'll be cleared once a bursary officer confirms it."
#                 )
#             except ValidationError as e:
#                 messages.error(request, str(e))
#             except IntegrityError:
#                 messages.error(
#                     request,
#                     "That payment reference has already been submitted. "
#                     "If you're re-submitting proof of the same transaction, please contact the bursary office."
#                 )

#             return redirect("students:course-registration")

#     # --- GET DATA ---
#     total_cost = float(late_fee)
#     available_courses = []
#     registered_course_ids = []
#     unit_policy = None
#     fee_clearance = None
#     outstanding_items = []
#     recent_payments = []
#     course_search_debug = ""
#     profile_incomplete = False
#     admin_registrations = []
#     admin_reg_stats = None

#     admin_semesters = Semester.objects.none()
#     selected_reg_semester = ""

#     if is_admin:
#         admin_semesters = Semester.objects.filter(session=current_session).order_by('name') if current_session else Semester.objects.none()

#         # Filter by semester — defaults to the current semester, but staff
#         # can pick any semester within the current session from the dropdown.
#         selected_reg_semester = request.GET.get('reg_semester', '')
#         if not selected_reg_semester and current_semester:
#             selected_reg_semester = str(current_semester.id)

#         admin_qs = CourseRegistration.objects.filter(session=current_session) if current_session else CourseRegistration.objects.none()
#         if selected_reg_semester:
#             admin_qs = admin_qs.filter(semester_id=selected_reg_semester)
#         admin_qs = admin_qs.select_related('student__user', 'course').order_by('-registered_at')

#         total_count = admin_qs.count()
#         validated_count = admin_qs.filter(is_validated=True).count()
#         admin_reg_stats = {
#             'total': total_count,
#             'validated': validated_count,
#             'pending': total_count - validated_count,
#         }

#         # CSV export — same filtered queryset, no pagination applied.
#         if request.GET.get('export') == 'csv':
#             return _export_course_registrations_csv(admin_qs)

#         paginator = Paginator(admin_qs, 25)
#         page_number = request.GET.get('page', 1)
#         admin_registrations = paginator.get_page(page_number)

#     if student:
#         if not student.department or not student.level:
#             # A student without department/level assigned can never match
#             # any Course filter — show this plainly instead of a blank,
#             # unexplained grid.
#             profile_incomplete = True
#             available_courses = Course.objects.none()
#         elif current_semester:
#             # IMPORTANT: match by semester *name* (First/Second/Third), not
#             # the exact Semester row. A Course's curriculum placement ("this
#             # is a First Semester course for HND1 Computer Science") is
#             # stable across academic sessions — but Course.semester is a
#             # hard FK to one specific Semester row, which itself belongs to
#             # one specific Session. Filtering on `semester=current_semester`
#             # therefore goes silently empty the moment the registrar rolls
#             # over to a new session's Semester row, even though nothing
#             # about the curriculum actually changed. The CourseRegistration
#             # itself still correctly ties to the exact
#             # current_session/current_semester below — only the *available
#             # courses to choose from* needed this relaxation.
#             available_courses = Course.objects.filter(
#                 department=student.department,
#                 level=student.level,
#                 semester__name=current_semester.name,
#             ).select_related('semester', 'department', 'level')
#             course_search_debug = (
#                 f"Dept={student.department} | Level={student.level} | "
#                 f"SemesterName='{current_semester.name}' | Found={available_courses.count()}"
#             )
#         else:
#             available_courses = Course.objects.none()
#             course_search_debug = "No current semester configured — cannot resolve available courses."

#         regs = CourseRegistration.objects.filter(
#             student=student, session=current_session, semester=current_semester
#         ).select_related('course')
#         registered_course_ids = list(regs.values_list('course_id', flat=True))
#         for r in regs:
#             total_cost += float(r.course.cost or 0)

#         # Unit policy shown to the student so the limits aren't a surprise
#         # only on submit.
#         try:
#             unit_policy = resolve_registration_policy(student.level)
#         except ValidationError:
#             unit_policy = None

#         # Outstanding mandatory fees (from the finance app) — shown as a
#         # banner so a student understands *why* a course might not be
#         # exam-eligible, without needing to leave this page.
#         if current_session and current_semester:
#             from finance.models import Payment as FinancePayment

#             try:
#                 FinanceService.ensure_semester_fee_items(student, current_session, current_semester)
#                 fee_clearance = ExamEligibilityService.semester_clearance_summary(
#                     student, current_session, current_semester
#                 )
#             except Exception:
#                 # No FeeAssignment configured yet for this session/semester —
#                 # don't let that block the registration page from loading.
#                 fee_clearance = None

#             # Everything the student can choose to pay for right now —
#             # course fees for whatever they're registered for, plus every
#             # resolved mandatory/optional fee category.
#             from students.services.dashboard import build_outstanding_items
#             outstanding_items = build_outstanding_items(student, current_session, current_semester)

#             recent_payments = FinancePayment.objects.filter(student=student).order_by('-created_at')[:10]

#     return render(request, "students/course_registration.html", {
#         "available_courses": available_courses,
#         "registered_course_ids": registered_course_ids,
#         "total_cost": total_cost,
#         "reg_phase": reg_phase,
#         "late_fee": late_fee,
#         "debug_msg": debug_msg,
#         "current_session": current_session,
#         "current_semester": current_semester,
#         "is_student": student is not None,
#         "is_admin": is_admin,
#         "today": today,
#         "unit_policy": unit_policy,
#         "fee_clearance": fee_clearance,
#         "outstanding_items": outstanding_items,
#         "recent_payments": recent_payments,
#         "course_search_debug": course_search_debug,
#         "profile_incomplete": profile_incomplete,
#         "admin_registrations": admin_registrations,
#         "admin_reg_stats": admin_reg_stats,
#         "admin_semesters": admin_semesters,
#         "selected_reg_semester": selected_reg_semester,
#     })


# @login_required
# def course_registration_view(request):
#     from finance.services.payments import FinanceService
#     from finance.services.exam_eligibility import ExamEligibilityService

#     user = request.user
#     student = getattr(user, 'student', None)
#     is_admin = user.is_superuser or user.is_staff

#     if not student and not is_admin:
#         messages.error(request, "Access denied.")
#         return redirect("pages:portal-home")

#     current_session = Session.objects.filter(is_current=True).first()
#     current_semester = Semester.objects.filter(is_current=True).first()

#     # --- REGISTRATION PHASE LOGIC ---
#     today = timezone.localdate()
#     reg_phase = "CLOSED"
#     late_fee = 0
#     debug_msg = ""

#     if current_semester:
#         # Priority 1: Manual Override
#         if current_semester.is_reg_active:
#             reg_phase = "OPEN"
#             debug_msg = "Manual override active."
#         # Priority 2: Date Windows
#         elif current_semester.reg_start_date and current_semester.reg_end_date:
#             if today < current_semester.reg_start_date:
#                 reg_phase = "CLOSED"
#                 debug_msg = f"Starts {current_semester.reg_start_date}"
#             elif today <= current_semester.reg_end_date:
#                 reg_phase = "OPEN"
#                 debug_msg = "Normal registration period."
#             elif current_semester.late_reg_end_date and today <= current_semester.late_reg_end_date:
#                 reg_phase = "LATE"
#                 late_fee = current_semester.late_reg_fee
#                 debug_msg = "Late registration period."
#             else:
#                 reg_phase = "CLOSED"
#                 debug_msg = "Deadlines passed."
#         else:
#             debug_msg = "Dates not configured."

#     # --- POST HANDLER ---
#     if request.method == "POST":
#         if not student:
#             messages.error(request, "Admins cannot modify records.")
#             return redirect("students:course-registration")

#         action = request.POST.get("action", "register")

#         # ---------------------------------------------------------
#         # ACTION 1: Save course registration (unchanged sync pattern)
#         # ---------------------------------------------------------
#         if action == "register":
#             if reg_phase == "CLOSED":
#                 messages.error(request, "The portal is currently closed.")
#                 return redirect("students:course-registration")

#             selected_course_ids = [int(c_id) for c_id in request.POST.getlist("courses")]

#             # Enforce the programme/level's unit policy before touching the
#             # database (curriculum.RegistrationPolicy). MAXIMUM is a hard
#             # block (a real resource/administrative cap). MINIMUM is a
#             # warning only, never a block — if the available course list
#             # for this department/level/semester doesn't even add up to
#             # the configured minimum, a hard block would make registration
#             # permanently impossible for every student in that cohort.
#             if selected_course_ids:
#                 selected_courses = Course.objects.filter(id__in=selected_course_ids)
#                 total_units = sum(c.credit_unit for c in selected_courses)
#                 try:
#                     policy = resolve_registration_policy(student.level)
#                     if total_units > policy.max_units_per_semester:
#                         messages.error(
#                             request,
#                             f"You selected {total_units} unit(s), which exceeds the maximum of "
#                             f"{policy.max_units_per_semester} allowed for your level. "
#                             f"Please deselect a course and try again."
#                         )
#                         return redirect("students:course-registration")
#                     if total_units < policy.min_units_per_semester:
#                         messages.warning(
#                             request,
#                             f"Note: {total_units} unit(s) is below the recommended minimum of "
#                             f"{policy.min_units_per_semester} for your level. Your registration "
#                             f"was still saved — register more courses if/when more become available."
#                         )
#                 except ValidationError:
#                     # No RegistrationPolicy configured yet for this level/programme —
#                     # don't block registration just because policy setup is incomplete.
#                     pass

#             try:
#                 with transaction.atomic():
#                     # Sync: Delete all existing then recreate
#                     CourseRegistration.objects.filter(
#                         student=student, session=current_session, semester=current_semester
#                     ).delete()

#                     if selected_course_ids:
#                         new_regs = [
#                             CourseRegistration(
#                                 student=student, course_id=c_id,
#                                 session=current_session, semester=current_semester
#                             ) for c_id in selected_course_ids
#                         ]
#                         CourseRegistration.objects.bulk_create(new_regs)

#                         # Re-fetch instead of trusting bulk_create()'s
#                         # returned objects to have real PKs. bulk_create()
#                         # doesn't reliably populate .pk on the instances it
#                         # hands back across every DB backend/Django version
#                         # combination — and ensure_course_fee_item() below
#                         # depends on reg.pk to link the PaymentItem back to
#                         # this exact registration. Without this, the course
#                         # fee can silently fail to appear in "Pay Your Fees".
#                         created_regs = CourseRegistration.objects.filter(
#                             student=student,
#                             session=current_session,
#                             semester=current_semester,
#                             course_id__in=selected_course_ids,
#                         )

#                         # Bill each newly registered course's fee (finance app) —
#                         # without this, a course with a nonzero cost would never
#                         # show up as something the student owes.
#                         for reg in created_regs:
#                             FinanceService.ensure_course_fee_item(reg)

#                         messages.success(request, "Course registration updated successfully.")
#                     else:
#                         messages.warning(request, "Your registration has been cleared.")
#                 return redirect("students:course-registration")
#             except Exception as e:
#                 messages.error(request, f"System Error: {e}")

#         # ---------------------------------------------------------
#         # ACTION 2: Submit a payment claim covering one or more
#         # outstanding items (course fees and/or mandatory fees),
#         # selected and optionally part-paid by the student.
#         # ---------------------------------------------------------
#         elif action == "submit_payment":
#             from finance.models import PaymentItem

#             reference = request.POST.get("reference", "").strip()
#             method = request.POST.get("method", "bank_transfer")
#             selected_item_ids = request.POST.getlist("pay_items")

#             if not reference:
#                 messages.error(request, "Please provide a payment reference (e.g. your bank transfer reference).")
#                 return redirect("students:course-registration")

#             if not selected_item_ids:
#                 messages.error(request, "Select at least one fee to pay for.")
#                 return redirect("students:course-registration")

#             allocations = {}
#             total_amount = Decimal("0.00")
#             for item_id in selected_item_ids:
#                 item = get_object_or_404(PaymentItem, pk=item_id, student=student)
#                 raw_amount = request.POST.get(f"amount_{item_id}", "").strip().replace(",", "")
#                 try:
#                     amount = Decimal(raw_amount) if raw_amount else item.balance
#                 except InvalidOperation:
#                     amount = item.balance
#                 # Never allow paying more than what's actually owed, and
#                 # never a non-positive amount.
#                 amount = min(amount, item.balance)
#                 if amount > 0:
#                     allocations[item.id] = amount
#                     total_amount += amount

#             if not allocations:
#                 messages.error(request, "Nothing to pay — the selected item(s) are already cleared.")
#                 return redirect("students:course-registration")

#             try:
#                 FinanceService.record_payment(
#                     student=student,
#                     reference=reference,
#                     amount=total_amount,
#                     method=method,
#                     allocations=allocations,
#                     mark_successful=False,  # goes to PENDING until a bursary officer approves it
#                 )
#                 messages.success(
#                     request,
#                     f"Payment of ₦{total_amount:,.2f} submitted for approval. "
#                     f"You'll be cleared once a bursary officer confirms it."
#                 )
#             except ValidationError as e:
#                 messages.error(request, str(e))
#             except IntegrityError:
#                 messages.error(
#                     request,
#                     "That payment reference has already been submitted. "
#                     "If you're re-submitting proof of the same transaction, please contact the bursary office."
#                 )

#             return redirect("students:course-registration")

#     # --- GET DATA ---
#     total_cost = float(late_fee)
#     available_courses = []
#     registered_course_ids = []
#     unit_policy = None
#     fee_clearance = None
#     outstanding_items = []
#     recent_payments = []
#     course_search_debug = ""
#     profile_incomplete = False
#     admin_registrations = []
#     admin_reg_stats = None

#     admin_semesters = Semester.objects.none()
#     selected_reg_semester = ""

#     if is_admin:
#         admin_semesters = Semester.objects.filter(session=current_session).order_by('name') if current_session else Semester.objects.none()

#         # Filter by semester — defaults to the current semester, but staff
#         # can pick any semester within the current session from the dropdown.
#         selected_reg_semester = request.GET.get('reg_semester', '')
#         if not selected_reg_semester and current_semester:
#             selected_reg_semester = str(current_semester.id)

#         admin_qs = CourseRegistration.objects.filter(session=current_session) if current_session else CourseRegistration.objects.none()
#         if selected_reg_semester:
#             admin_qs = admin_qs.filter(semester_id=selected_reg_semester)
#         admin_qs = admin_qs.select_related('student__user', 'course').order_by('-registered_at')

#         total_count = admin_qs.count()
#         validated_count = admin_qs.filter(is_validated=True).count()
#         admin_reg_stats = {
#             'total': total_count,
#             'validated': validated_count,
#             'pending': total_count - validated_count,
#         }

#         # CSV export — same filtered queryset, no pagination applied.
#         if request.GET.get('export') == 'csv':
#             return _export_course_registrations_csv(admin_qs)

#         paginator = Paginator(admin_qs, 25)
#         page_number = request.GET.get('page', 1)
#         admin_registrations = paginator.get_page(page_number)

#     if student:
#         if not student.department or not student.level:
#             # A student without department/level assigned can never match
#             # any Course filter — show this plainly instead of a blank,
#             # unexplained grid.
#             profile_incomplete = True
#             available_courses = Course.objects.none()
#         elif current_semester:
#             # IMPORTANT: match by semester *name* (First/Second/Third), not
#             # the exact Semester row. A Course's curriculum placement ("this
#             # is a First Semester course for HND1 Computer Science") is
#             # stable across academic sessions — but Course.semester is a
#             # hard FK to one specific Semester row, which itself belongs to
#             # one specific Session. Filtering on `semester=current_semester`
#             # therefore goes silently empty the moment the registrar rolls
#             # over to a new session's Semester row, even though nothing
#             # about the curriculum actually changed. The CourseRegistration
#             # itself still correctly ties to the exact
#             # current_session/current_semester below — only the *available
#             # courses to choose from* needed this relaxation.
#             available_courses = Course.objects.filter(
#                 department=student.department,
#                 level=student.level,
#                 semester__name=current_semester.name,
#             ).select_related('semester', 'department', 'level')
#             course_search_debug = (
#                 f"Dept={student.department} | Level={student.level} | "
#                 f"SemesterName='{current_semester.name}' | Found={available_courses.count()}"
#             )
#         else:
#             available_courses = Course.objects.none()
#             course_search_debug = "No current semester configured — cannot resolve available courses."

#         regs = CourseRegistration.objects.filter(
#             student=student, session=current_session, semester=current_semester
#         ).select_related('course')
#         registered_course_ids = list(regs.values_list('course_id', flat=True))
#         for r in regs:
#             total_cost += float(r.course.cost or 0)

#         # Unit policy shown to the student so the limits aren't a surprise
#         # only on submit.
#         try:
#             unit_policy = resolve_registration_policy(student.level)
#         except ValidationError:
#             unit_policy = None

#         # Outstanding mandatory fees (from the finance app) — shown as a
#         # banner so a student understands *why* a course might not be
#         # exam-eligible, without needing to leave this page.
#         if current_session and current_semester:
#             from finance.models import Payment as FinancePayment

#             try:
#                 FinanceService.ensure_semester_fee_items(student, current_session, current_semester)
#                 fee_clearance = ExamEligibilityService.semester_clearance_summary(
#                     student, current_session, current_semester
#                 )
#             except Exception:
#                 # No FeeAssignment configured yet for this session/semester —
#                 # don't let that block the registration page from loading.
#                 fee_clearance = None

#             # Everything the student can choose to pay for right now —
#             # course fees for whatever they're registered for, plus every
#             # resolved mandatory/optional fee category.
#             from students.services.dashboard import build_outstanding_items
#             outstanding_items = build_outstanding_items(student, current_session, current_semester)

#             recent_payments = FinancePayment.objects.filter(student=student).order_by('-created_at')[:10]

#     return render(request, "students/course_registration.html", {
#         "available_courses": available_courses,
#         "registered_course_ids": registered_course_ids,
#         "total_cost": total_cost,
#         "reg_phase": reg_phase,
#         "late_fee": late_fee,
#         "debug_msg": debug_msg,
#         "current_session": current_session,
#         "current_semester": current_semester,
#         "is_student": student is not None,
#         "is_admin": is_admin,
#         "today": today,
#         "unit_policy": unit_policy,
#         "fee_clearance": fee_clearance,
#         "outstanding_items": outstanding_items,
#         "recent_payments": recent_payments,
#         "course_search_debug": course_search_debug,
#         "profile_incomplete": profile_incomplete,
#         "admin_registrations": admin_registrations,
#         "admin_reg_stats": admin_reg_stats,
#         "admin_semesters": admin_semesters,
#         "selected_reg_semester": selected_reg_semester,
#     })


@login_required
def course_registration_view(request):
    from finance.services.payments import FinanceService
    from finance.services.exam_eligibility import ExamEligibilityService

    user = request.user
    student = getattr(user, 'student', None)
    is_admin = user.is_superuser or user.is_staff

    if not student and not is_admin:
        messages.error(request, "Access denied.")
        return redirect("pages:portal-home")

    current_session = Session.objects.filter(is_current=True).first()
    current_semester = Semester.objects.filter(is_current=True).first()

    # --- REGISTRATION PHASE LOGIC ---
    today = timezone.localdate()
    reg_phase = "CLOSED"
    late_fee = 0
    debug_msg = ""

    if current_semester:
        # Priority 1: Manual Override
        if current_semester.is_reg_active:
            reg_phase = "OPEN"
            debug_msg = "Manual override active."
        # Priority 2: Date Windows
        elif current_semester.reg_start_date and current_semester.reg_end_date:
            if today < current_semester.reg_start_date:
                reg_phase = "CLOSED"
                debug_msg = f"Starts {current_semester.reg_start_date}"
            elif today <= current_semester.reg_end_date:
                reg_phase = "OPEN"
                debug_msg = "Normal registration period."
            elif current_semester.late_reg_end_date and today <= current_semester.late_reg_end_date:
                reg_phase = "LATE"
                late_fee = current_semester.late_reg_fee
                debug_msg = "Late registration period."
            else:
                reg_phase = "CLOSED"
                debug_msg = "Deadlines passed."
        else:
            debug_msg = "Dates not configured."

    # --- POST HANDLER ---
    if request.method == "POST":
        if not student:
            messages.error(request, "Admins cannot modify records.")
            return redirect("students:course-registration")

        action = request.POST.get("action", "register")

        # ---------------------------------------------------------
        # ACTION 1: Save course registration (unchanged sync pattern)
        # ---------------------------------------------------------
        if action == "register":
            if reg_phase == "CLOSED":
                messages.error(request, "The portal is currently closed.")
                return redirect("students:course-registration")

            selected_course_ids = [int(c_id) for c_id in request.POST.getlist("courses")]

            # Enforce the programme/level's unit policy before touching the
            # database (curriculum.RegistrationPolicy). MAXIMUM is a hard
            # block (a real resource/administrative cap). MINIMUM is a
            # warning only, never a block — if the available course list
            # for this department/level/semester doesn't even add up to
            # the configured minimum, a hard block would make registration
            # permanently impossible for every student in that cohort.
            if selected_course_ids:
                selected_courses = Course.objects.filter(id__in=selected_course_ids)
                total_units = sum(c.credit_unit for c in selected_courses)
                try:
                    policy = resolve_registration_policy(student.level)
                    if total_units > policy.max_units_per_semester:
                        messages.error(
                            request,
                            f"You selected {total_units} unit(s), which exceeds the maximum of "
                            f"{policy.max_units_per_semester} allowed for your level. "
                            f"Please deselect a course and try again."
                        )
                        return redirect("students:course-registration")
                    if total_units < policy.min_units_per_semester:
                        messages.warning(
                            request,
                            f"Note: {total_units} unit(s) is below the recommended minimum of "
                            f"{policy.min_units_per_semester} for your level. Your registration "
                            f"was still saved — register more courses if/when more become available."
                        )
                except ValidationError:
                    # No RegistrationPolicy configured yet for this level/programme —
                    # don't block registration just because policy setup is incomplete.
                    pass

            try:
                with transaction.atomic():
                    # Sync: Delete all existing then recreate
                    CourseRegistration.objects.filter(
                        student=student, session=current_session, semester=current_semester
                    ).delete()

                    if selected_course_ids:
                        new_regs = [
                            CourseRegistration(
                                student=student, course_id=c_id,
                                session=current_session, semester=current_semester
                            ) for c_id in selected_course_ids
                        ]
                        CourseRegistration.objects.bulk_create(new_regs)

                        # Re-fetch instead of trusting bulk_create()'s
                        # returned objects to have real PKs. bulk_create()
                        # doesn't reliably populate .pk on the instances it
                        # hands back across every DB backend/Django version
                        # combination — and ensure_course_fee_item() below
                        # depends on reg.pk to link the PaymentItem back to
                        # this exact registration. Without this, the course
                        # fee can silently fail to appear in "Pay Your Fees".
                        created_regs = CourseRegistration.objects.filter(
                            student=student,
                            session=current_session,
                            semester=current_semester,
                            course_id__in=selected_course_ids,
                        )

                        # Bill each newly registered course's fee (finance app) —
                        # without this, a course with a nonzero cost would never
                        # show up as something the student owes.
                        for reg in created_regs:
                            FinanceService.ensure_course_fee_item(reg)

                        messages.success(request, "Course registration updated successfully.")
                    else:
                        messages.warning(request, "Your registration has been cleared.")
                return redirect("students:course-registration")
            except Exception as e:
                messages.error(request, f"System Error: {e}")

        # ---------------------------------------------------------
        # ACTION 2: Submit a payment claim covering one or more
        # outstanding items (course fees and/or mandatory fees),
        # selected and optionally part-paid by the student.
        # ---------------------------------------------------------
        elif action == "submit_payment":
            from finance.models import PaymentItem

            reference = request.POST.get("reference", "").strip()
            method = request.POST.get("method", "bank_transfer")
            selected_item_ids = request.POST.getlist("pay_items")

            if not reference:
                messages.error(request, "Please provide a payment reference (e.g. your bank transfer reference).")
                return redirect("students:course-registration")

            if not selected_item_ids:
                messages.error(request, "Select at least one fee to pay for.")
                return redirect("students:course-registration")

            allocations = {}
            total_amount = Decimal("0.00")
            for item_id in selected_item_ids:
                item = get_object_or_404(PaymentItem, pk=item_id, student=student)
                raw_amount = request.POST.get(f"amount_{item_id}", "").strip().replace(",", "")
                try:
                    amount = Decimal(raw_amount) if raw_amount else item.balance
                except InvalidOperation:
                    amount = item.balance
                # Never allow paying more than what's actually owed, and
                # never a non-positive amount.
                amount = min(amount, item.balance)
                if amount > 0:
                    allocations[item.id] = amount
                    total_amount += amount

            if not allocations:
                messages.error(request, "Nothing to pay — the selected item(s) are already cleared.")
                return redirect("students:course-registration")

            try:
                FinanceService.record_payment(
                    student=student,
                    reference=reference,
                    amount=total_amount,
                    method=method,
                    allocations=allocations,
                    mark_successful=False,  # goes to PENDING until a bursary officer approves it
                )
                messages.success(
                    request,
                    f"Payment of ₦{total_amount:,.2f} submitted for approval. "
                    f"You'll be cleared once a bursary officer confirms it."
                )
            except ValidationError as e:
                messages.error(request, str(e))
            except IntegrityError:
                messages.error(
                    request,
                    "That payment reference has already been submitted. "
                    "If you're re-submitting proof of the same transaction, please contact the bursary office."
                )

            return redirect("students:course-registration")

    # --- GET DATA ---
    total_cost = float(late_fee)
    available_courses = []
    registered_course_ids = []
    unit_policy = None
    fee_clearance = None
    outstanding_items = []
    recent_payments = []
    course_search_debug = ""
    profile_incomplete = False
    admin_registrations = []
    admin_reg_stats = None

    admin_semesters = Semester.objects.none()
    selected_reg_semester = ""

    if is_admin:
        admin_semesters = Semester.objects.filter(session=current_session).order_by('name') if current_session else Semester.objects.none()

        # Filter by semester — defaults to the current semester, but staff
        # can pick any semester within the current session from the dropdown.
        selected_reg_semester = request.GET.get('reg_semester', '')
        if not selected_reg_semester and current_semester:
            selected_reg_semester = str(current_semester.id)

        admin_qs = CourseRegistration.objects.filter(session=current_session) if current_session else CourseRegistration.objects.none()
        if selected_reg_semester:
            admin_qs = admin_qs.filter(semester_id=selected_reg_semester)
        admin_qs = admin_qs.select_related('student__user', 'course').order_by('-registered_at')

        total_count = admin_qs.count()
        validated_count = admin_qs.filter(is_validated=True).count()
        admin_reg_stats = {
            'total': total_count,
            'validated': validated_count,
            'pending': total_count - validated_count,
        }

        # CSV export — same filtered queryset, no pagination applied.
        if request.GET.get('export') == 'csv':
            return _export_course_registrations_csv(admin_qs)

        paginator = Paginator(admin_qs, 25)
        page_number = request.GET.get('page', 1)
        admin_registrations = paginator.get_page(page_number)

    if student:
        if not student.department or not student.level:
            # A student without department/level assigned can never match
            # any Course filter — show this plainly instead of a blank,
            # unexplained grid.
            profile_incomplete = True
            available_courses = Course.objects.none()
        elif current_semester:
            # IMPORTANT: match by semester *name* (First/Second/Third), not
            # the exact Semester row. A Course's curriculum placement ("this
            # is a First Semester course for HND1 Computer Science") is
            # stable across academic sessions — but Course.semester is a
            # hard FK to one specific Semester row, which itself belongs to
            # one specific Session. Filtering on `semester=current_semester`
            # therefore goes silently empty the moment the registrar rolls
            # over to a new session's Semester row, even though nothing
            # about the curriculum actually changed. The CourseRegistration
            # itself still correctly ties to the exact
            # current_session/current_semester below — only the *available
            # courses to choose from* needed this relaxation.
            available_courses = Course.objects.filter(
                department=student.department,
                level=student.level,
                semester__name=current_semester.name,
            ).select_related('semester', 'department', 'level')
            course_search_debug = (
                f"Dept={student.department} | Level={student.level} | "
                f"SemesterName='{current_semester.name}' | Found={available_courses.count()}"
            )
        else:
            available_courses = Course.objects.none()
            course_search_debug = "No current semester configured — cannot resolve available courses."

        regs = CourseRegistration.objects.filter(
            student=student, session=current_session, semester=current_semester
        ).select_related('course')
        registered_course_ids = list(regs.values_list('course_id', flat=True))
        for r in regs:
            total_cost += float(r.course.cost or 0)

        # Self-heal: make sure every course the student is *currently*
        # registered for has its PaymentItem, regardless of when or how
        # that registration was created — a registration saved before a
        # past bug fix, one created by an admin directly, etc. Without
        # this, ensure_course_fee_item() only ever runs at the moment of
        # a fresh POST submission, so a pre-existing registration could
        # permanently show no course fee until the student happened to
        # re-save. Mirrors ensure_semester_fee_items() below, which
        # already runs on every GET for exactly the same reason.
        # Idempotent (get_or_create-based) and cheap for a normal course
        # load (a handful of rows), so safe to run on every page view.
        for reg in regs:
            try:
                FinanceService.ensure_course_fee_item(reg)
            except Exception:
                # Never let a single bad row block the whole page from
                # loading — same defensive posture as the mandatory-fee
                # block below.
                pass

        # Unit policy shown to the student so the limits aren't a surprise
        # only on submit.
        try:
            unit_policy = resolve_registration_policy(student.level)
        except ValidationError:
            unit_policy = None

        # Outstanding mandatory fees (from the finance app) — shown as a
        # banner so a student understands *why* a course might not be
        # exam-eligible, without needing to leave this page.
        if current_session and current_semester:
            from finance.models import Payment as FinancePayment

            try:
                FinanceService.ensure_semester_fee_items(student, current_session, current_semester)
                fee_clearance = ExamEligibilityService.semester_clearance_summary(
                    student, current_session, current_semester
                )
            except Exception:
                # No FeeAssignment configured yet for this session/semester —
                # don't let that block the registration page from loading.
                fee_clearance = None

            # Everything the student can choose to pay for right now —
            # course fees for whatever they're registered for, plus every
            # resolved mandatory/optional fee category.
            from students.services.dashboard import build_outstanding_items
            outstanding_items = build_outstanding_items(student, current_session, current_semester)

            recent_payments = FinancePayment.objects.filter(student=student).order_by('-created_at')[:10]

    return render(request, "students/course_registration.html", {
        "available_courses": available_courses,
        "registered_course_ids": registered_course_ids,
        "total_cost": total_cost,
        "reg_phase": reg_phase,
        "late_fee": late_fee,
        "debug_msg": debug_msg,
        "current_session": current_session,
        "current_semester": current_semester,
        "is_student": student is not None,
        "is_admin": is_admin,
        "today": today,
        "unit_policy": unit_policy,
        "fee_clearance": fee_clearance,
        "outstanding_items": outstanding_items,
        "recent_payments": recent_payments,
        "course_search_debug": course_search_debug,
        "profile_incomplete": profile_incomplete,
        "admin_registrations": admin_registrations,
        "admin_reg_stats": admin_reg_stats,
        "admin_semesters": admin_semesters,
        "selected_reg_semester": selected_reg_semester,
    })




# TERTIARY LOGIC FOR HOSTEL ALLOCATION
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import render, redirect
from .models import Hostel, Room, Student


@staff_member_required
def hostel_dashboard(request):
    hostels = Hostel.objects.select_related('hostel_master').prefetch_related('rooms')

    # ✅ THIS is the fix (unassigned students for dropdown)
    unassigned_students = Student.objects.filter(
        assigned_room__isnull=True,
        student_status='active'
    ).select_related('user')

    dashboard_data = []

    for hostel in hostels:
        rooms = hostel.rooms.all()

        room_data = []
        for room in rooms:
            occupants = Student.objects.filter(assigned_room=room).select_related('user')

            room_data.append({
                "room": room,
                "occupants": occupants,
                "occupant_count": occupants.count(),
                "available_space": room.max_occupancy - occupants.count()
            })

        dashboard_data.append({
            "hostel": hostel,
            "total_rooms": rooms.count(),
            "occupied": hostel.occupied_spaces,
            "capacity": hostel.capacity,
            "rooms": room_data
        })

    return render(request, "students/hostel_dashboard.html", {
        "dashboard_data": dashboard_data,
        "students": unassigned_students  # ✅ used in template
    })

@staff_member_required
def assign_room(request):
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        room_id = request.POST.get("room_id")

        student = Student.objects.get(id=student_id)
        room = Room.objects.get(id=room_id)

        # ✅ Prevent over-allocation
        if Student.objects.filter(assigned_room=room).count() >= room.max_occupancy:
            messages.error(request, "Room is full.")
            return redirect("students:hostel-dashboard")

        # ✅ Assign properly
        student.assigned_room = room
        student.hostel_name = room.hostel
        student.save()

        messages.success(request, "Student assigned successfully.")
        return redirect("students:hostel-dashboard")




"""
students.views (Admission Letter additions)
=============================================

Mirrors the Lecturer self/admin view split already used in this project:
  - Self view:  the logged-in student sees their own letter.
  - Admin view: staff view any student's letter, addressed by
                matric_number (not pk) — deliberately, so it matches the
                `matric_number` URL kwarg the school_info context
                processor already special-cases, and the page
                automatically renders with THAT student's department
                branding rather than the viewing staff member's own.

The admission letter itself is never stored/generated ahead of time —
same as the ID card, it's rendered on demand straight from the Student
record, so it's "ready" the moment a student is registered.
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import DetailView

from curriculum.utils.identity import get_school_identity_for_department

from .models import Student


def _student_full_name(student):
    parts = [
        student.user.first_name,
        student.middle_name,
        student.user.last_name,
    ]
    return " ".join(p for p in parts if p).strip() or student.user.username


def _admission_context(student, request):
    verify_url = request.build_absolute_uri(
        reverse('students:verify-admission', kwargs={'matric_number': student.matric_number})
    )
    return {
        'student': student,
        'student_full_name': _student_full_name(student),
        'verify_url': verify_url,
    }


# =====================================================================
# HTML views
# =====================================================================

class AdmissionLetterSelfView(LoginRequiredMixin, DetailView):
    """Student views/prints their own admission letter."""
    model = Student
    template_name = 'students/admission_letter.html'
    context_object_name = 'student'

    def get_object(self):
        return get_object_or_404(
            Student.objects.select_related(
                'user', 'department', 'department__faculty', 'programme',
                'programme__qualification_type', 'level',
            ),
            user=self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_admission_context(self.object, self.request))
        context['is_self_view'] = True
        return context


class AdmissionLetterView(LoginRequiredMixin, DetailView):
    """Staff/admin views/prints any student's admission letter."""
    model = Student
    template_name = 'students/admission_letter.html'
    context_object_name = 'student'

    def get_object(self):
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise PermissionDenied("Not permitted.")

        return get_object_or_404(
            Student.objects.select_related(
                'user', 'department', 'department__faculty', 'programme',
                'programme__qualification_type', 'level',
            ),
            matric_number=self.kwargs.get('matric_number'),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_admission_context(self.object, self.request))
        context['is_self_view'] = False
        return context


# =====================================================================
# Public verification page — the QR code's target. No login required:
# an employer, agency, or the school's own front desk should be able to
# scan the code and immediately see whether the letter is genuine,
# without needing a portal account.
# =====================================================================

def verify_admission_letter(request, matric_number):
    student = Student.objects.select_related(
        'user', 'department', 'programme', 'level'
    ).filter(matric_number=matric_number).first()

    return render(request, 'students/verify_admission.html', {
        'student': student,
        'student_full_name': _student_full_name(student) if student else None,
    })


# =====================================================================
# PDF export
# =====================================================================

@login_required
def admission_letter_self_pdf(request):
    student = get_object_or_404(
        Student.objects.select_related(
            'user', 'department', 'department__faculty', 'programme',
            'programme__qualification_type', 'level',
        ),
        user=request.user,
    )
    return _render_admission_letter_pdf(student, request)


@login_required
def admission_letter_pdf(request, matric_number):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponse("Not permitted.", status=403)

    student = get_object_or_404(
        Student.objects.select_related(
            'user', 'department', 'department__faculty', 'programme',
            'programme__qualification_type', 'level',
        ),
        matric_number=matric_number,
    )
    return _render_admission_letter_pdf(student, request)


def _render_admission_letter_pdf(student, request):
    """Split out so both PDF entry points share one code path."""
    from students.services.admission_letter_pdf import build_admission_letter_pdf

    school_identity = get_school_identity_for_department(student.department)
    verify_url = request.build_absolute_uri(
        reverse('students:verify-admission', kwargs={'matric_number': student.matric_number})
    )

    return build_admission_letter_pdf(
        student=student,
        school_identity=school_identity,
        student_full_name=_student_full_name(student),
        verify_url=verify_url,
    )

"""
students.views (Admission Letter list / bulk-print additions)
================================================================

Two staff-only views:
  - AdmissionLetterListView: browsable, filterable table of every
    student's admission letter, with per-row View/Verify/PDF links.
  - admission_letter_bulk_print_view: renders every matching student's
    full letter, stacked with page breaks, for one big Print/Save-as-PDF
    run over a filtered batch (e.g. "everyone admitted to Computer
    Science in 2025").

Both filters (department, year) apply to the SAME queryset logic, reused
by both views so the list and the bulk print of "what you're currently
looking at" can never disagree with each other.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models.functions import ExtractYear
from django.shortcuts import render
from django.urls import reverse

from curriculum.models import Department
from curriculum.utils.identity import get_school_identity_for_department

from .models import Student
from .views import _student_full_name  # reuse the existing helper


def _filtered_students(request):
    students = Student.objects.select_related(
        'user', 'department', 'department__faculty', 'programme',
        'programme__qualification_type', 'level',
    ).order_by('department__name', '-date_admitted')

    department_id = request.GET.get('department')
    year = request.GET.get('year')

    if department_id:
        students = students.filter(department_id=department_id)
    if year:
        students = students.filter(date_admitted__year=year)

    return students, department_id, year


def _filter_options():
    """Shared by the list and bulk-print pages so their filter dropdowns
    are always built from the exact same source, never two copies that
    can quietly drift apart."""
    departments = Department.objects.all().order_by('name')
    available_years = (
        Student.objects.annotate(admit_year=ExtractYear('date_admitted'))
        .values_list('admit_year', flat=True)
        .distinct()
        .order_by('-admit_year')
    )
    return departments, available_years


@staff_member_required
def admission_letter_list_view(request):
    students, department_id, year = _filtered_students(request)
    departments, available_years = _filter_options()

    return render(request, 'students/admission_letter_list.html', {
        'students': students,
        'departments': departments,
        'available_years': available_years,
        'selected_department': department_id,
        'selected_year': year,
        'total_count': students.count(),
    })


@staff_member_required
def admission_letter_bulk_print_view(request):
    students, department_id, year = _filtered_students(request)
    departments, available_years = _filter_options()

    department_obj = None
    if department_id:
        department_obj = Department.objects.filter(id=department_id).first()

    # Resolve school_info per student, but cache by department so a batch
    # that's mostly (or entirely) one department doesn't re-run the
    # AcademicIdentityMapping lookup for every single row.
    identity_cache = {}
    letters = []

    for student in students:
        dept_id = student.department_id
        if dept_id not in identity_cache:
            identity_cache[dept_id] = get_school_identity_for_department(student.department)

        verify_url = request.build_absolute_uri(
            reverse('students:verify-admission', kwargs={'matric_number': student.matric_number})
        )

        letters.append({
            'student': student,
            'student_full_name': _student_full_name(student),
            'school_info': identity_cache[dept_id],
            'verify_url': verify_url,
        })

    return render(request, 'students/admission_letter_bulk_print.html', {
        'letters': letters,
        'departments': departments,
        'available_years': available_years,
        'selected_department': department_id,
        'selected_year': year,
        'department': department_obj,
        'year': year,
        'total_count': len(letters),
    })
