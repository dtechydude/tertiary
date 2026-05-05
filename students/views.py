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
from students.models import Student, Hostel, Parent, GraduationRecord
from staff.models import Lecturer
from students.forms import StudentUpdateForm, SuperUserStudentUpdateForm
# from payments.models import Payment, CategoryFee # Import Payment and CategoryFee models

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
from datetime import date
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from curriculum.utils.identity import get_school_identity_for_student


from django.utils import timezone




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


# TERTIARY LOGIC =============================================================================
class StudentDetailView(LoginRequiredMixin, DetailView):
    """
    Used by Staff/Admins to view any student's profile via Matric Number.
    """
    model = Student
    template_name = 'students/student_detail.html'
    context_object_name = 'student'

    def get_object(self):
        # Updated from USN=id_ to matric_number=matric_number
        matric_number = self.kwargs.get("matric_number")
        return get_object_or_404(Student, matric_number=matric_number)


# TERTIARY LOGIC===================================================
class StudentSelfDetailView(LoginRequiredMixin, DetailView):
    """
    Used by the logged-in student to view their own profile.
    """
    model = Student
    template_name = 'students/student_self_detail.html'
    context_object_name = 'student'

    def dispatch(self, request, *args, **kwargs):
        # Check if student profile exists before proceeding to get_object
        if not hasattr(request.user, 'student'):
            messages.error(request, "Your student profile could not be found. Please contact administration.")
            return redirect('pages:portal-home')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.request.user.student


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


# TERTIARY LOGIC FOR BORDERS ================================================
# For Boading Students
# @login_required
# def student_boarder_list(request):
#     # Security Check: Ensure only staff/superusers proceed
#     if not (request.user.is_superuser or request.user.is_staff):
#         return render(request, 'pages/portal_home.html')

#     # Optimization: Use select_related to join 'hostel_name' and 'level' 
#     # so they are fetched in a single database query.
#     boarder_students = Student.objects.filter(
#         student_type='boarder'
#     ).exclude(
#         student_status='graduated'
#     ).select_related(
#         'hostel_name', 'level', 'programme'
#     ).order_by('-date_admitted')

#     context = {
#         'boarder_students': boarder_students
#     }

#     return render(request, 'students/student_boarder_list.html', context)

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
    Refactored for Tertiary: Promotes students to the next level within their department.
    """
    levels = Level.objects.all().order_by('rank') # Assuming 'rank' replaces promotion_order
    departments = Department.objects.all()

    if request.method == 'POST':
        from_level_id = request.POST.get('from_level')
        dept_id = request.POST.get('department')
        selected_student_ids = request.POST.getlist('selected_students')

        if not from_level_id or not selected_student_ids:
            messages.error(request, "Please select a level and at least one student.")
            return redirect('students:promote_students')

        try:
            current_level = Level.objects.get(id=from_level_id)
            # Find the next level by rank
            next_level = Level.objects.filter(rank__gt=current_level.rank).order_by('rank').first()

            with transaction.atomic():
                students = Student.objects.filter(id__in=selected_student_ids, current_level=current_level)
                
                if next_level:
                    count = students.count()
                    students.update(current_level=next_level)
                    messages.success(request, f"Successfully promoted {count} students to {next_level.name}.")
                else:
                    # If no next level exists, they should likely be moved to the graduation workflow
                    messages.warning(request, f"{current_level.name} is the final level. Use the Graduation module to graduate these students.")
            
        except Exception as e:
            messages.error(request, f"Promotion failed: {str(e)}")
            
        return redirect('students:promote_students')

    context = {
        'levels': levels,
        'departments': departments,
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

@login_required
def student_distribution_view(request):
    """
    Displays the headcount of students broken down by 
    Programme, Department, and Level.
    """
    # 1. Total Count per Programme
    programme_counts = Student.objects.values('programme__name').annotate(
        total=Count('id')
    ).order_by('programme__name')

    # 2. Total Count per Department
    department_counts = Student.objects.values('department__name').annotate(
        total=Count('id')
    ).order_by('department__name')

    # 3. Detailed breakdown (Level + Department)
    # Changed 'current_level__name' to 'level__name' to match your model
    detailed_counts = Student.objects.values(
        'department__name', 
        'level__name' 
    ).annotate(
        total=Count('id')
    ).order_by('department__name', 'level__id') # Using level__id for ordering

    # 4. Context for the logged-in student
    peers_count = 0
    if hasattr(request.user, 'student'):
        # Changed current_level to level to match your model
        peers_count = Student.objects.filter(
            level=request.user.student.level,
            department=request.user.student.department
        ).count()

    context = {
        'programme_counts': programme_counts,
        'department_counts': department_counts,
        'detailed_counts': detailed_counts,
        'peers_count': peers_count,
    }

    return render(request, 'students/student_distribution.html', context)


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
    template_name = 'student/my_teacher_detail.html'
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
from .models import Student, Session

# --- Helper Function for CSV Export ---
def export_students_csv(queryset):
    """
    Generates a CSV response from a student queryset with Tertiary fields.
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
        "Entry Level",
        "Date Admitted",
        "Graduation Session",
    ])

    for s in queryset:
        # Using select_related in the view makes these lookups efficient
        dept_name = s.department.name if s.department else "N/A"
        prog_name = s.programme.name if s.programme else "N/A"
        session_name = s.graduated_session.name if s.graduated_session else "N/A"
        
        writer.writerow([
            s.matric_number,
            f"{s.last_name} {s.first_name} {s.middle_name or ''}".strip(),
            s.gender,
            s.student_status,
            dept_name,
            prog_name,
            s.level.name if s.level else "N/A",
            s.date_admitted,
            session_name,
        ])

    return response

# --------------------------------------------------

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
    # FIXED: Accessing 'user__last_name' for ordering
    # FIXED: Removed 'graduated_session' from select_related as per FieldError
    students = Student.objects.filter(
        student_status__in=archived_status
    ).select_related('user', 'department', 'programme', 'level').order_by('-date_admitted', 'user__last_name')

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

    # Note: verify if session filtering should target a specific FK on your model
    if session_filter and session_filter != "all":
        # If your model has no graduated_session FK, this filter might need 
        # to target the related name (e.g., graduation_records__session_id)
        pass 
        
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
@login_required
def course_registration_view(request):
    user = request.user
    student = getattr(user, 'student', None)
    is_admin = user.is_superuser or user.is_staff

    if not student and not is_admin:
        messages.error(request, "Access denied.")
        return redirect("pages:portal_home")

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

    # --- POST HANDLER (Sync Pattern) ---
    if request.method == "POST":
        if not student:
            messages.error(request, "Admins cannot modify records.")
            return redirect("course-registration")
        
        if reg_phase == "CLOSED":
            messages.error(request, "The portal is currently closed.")
            return redirect("course-registration")

        selected_courses = request.POST.getlist("courses")
        try:
            with transaction.atomic():
                # Sync: Delete all existing then recreate
                CourseRegistration.objects.filter(
                    student=student, session=current_session, semester=current_semester
                ).delete()

                if selected_courses:
                    new_regs = [
                        CourseRegistration(
                            student=student, course_id=int(c_id),
                            session=current_session, semester=current_semester
                        ) for c_id in selected_courses
                    ]
                    CourseRegistration.objects.bulk_create(new_regs)
                    messages.success(request, "Course registration updated successfully.")
                else:
                    messages.warning(request, "Your registration has been cleared.")
            return redirect("course-registration")
        except Exception as e:
            messages.error(request, f"System Error: {e}")

    # --- GET DATA ---
    total_cost = float(late_fee)
    available_courses = []
    registered_course_ids = []

    if student:
        available_courses = Course.objects.filter(
            department=student.department, level=student.level, semester=current_semester
        )
        regs = CourseRegistration.objects.filter(
            student=student, session=current_session, semester=current_semester
        ).select_related('course')
        registered_course_ids = list(regs.values_list('course_id', flat=True))
        for r in regs:
            total_cost += float(r.course.cost or 0)

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