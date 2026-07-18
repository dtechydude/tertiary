from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count
import csv
from django.db.models import F
from django.db import transaction
#converting html to pdf
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
# from xhtml2pdf import pisa
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from collections import Counter
from staff.models import Lecturer
from students.models import Student
from curriculum.models import SchoolIdentity, CourseAssignment
from staff.forms import LecturerUpdateForm, LecturerForm, CustomUserCreationForm, StaffRegisterForm, StaffUpdateForm
from django.contrib.auth.forms import UserCreationForm

from django.core.paginator import Paginator
from django.db.models import Q




@login_required
def lecturers_list(request):
    """
    Staff-only view with:
    - Search
    - Pagination
    - CSV export
    """

    # 🔐 Access Control
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('pages:portal_home')

    # ⚡ Base Query
    lecturers_qs = Lecturer.objects.select_related(
        'user', 'department', 'position'
    ).order_by('user__last_name', 'user__first_name')

    # 🔍 SEARCH
    search_query = request.GET.get('search', '').strip()

    if search_query:
        lecturers_qs = lecturers_qs.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(department__name__icontains=search_query)
        )

    # 📤 CSV EXPORT (respects search)
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="lecturers_list.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Staff ID',
            'Full Name',
            'Department',
            'Position',
            'Gender',
            'Phone',
            'Email',
            'Date Employed'
        ])

        for l in lecturers_qs:
            writer.writerow([
                l.staff_id,
                l.get_full_name(),
                l.department.name if l.department else '',
                l.position.name if l.position else '',
                l.gender,
                l.phone,
                l.user.email,
                l.date_employed
            ])

        return response

    # 📄 PAGINATION
    paginator = Paginator(lecturers_qs, 10)  # 10 per page
    page_number = request.GET.get('page')
    lecturers = paginator.get_page(page_number)

    context = {
        'lecturers': lecturers,
        'search_query': search_query
    }

    return render(request, 'staff/lecturers_list.html', context)



# Tertiary ID CArd
class LecturerIDCardView(LoginRequiredMixin, View):
    """
    Displays a printable ID card for a specific lecturer.
    """

    def get(self, request, lecturer_id):
        lecturer = get_object_or_404(
            Lecturer.objects.select_related('user', 'department'),
            id=lecturer_id
        )

        # Get school identity (fallback safe)
        school_identity = SchoolIdentity.objects.first()

        context = {
            'lecturer': lecturer,
            'school_identity': school_identity,
        }

        return render(request, 'staff/lecturer_id_card.html', context)
    

# Display only my teacher
@login_required # Ensure only logged-in users can access this view
def my_teacher_view(request):
    logged_in_user = request.user

    try:
        # Get the Student profile associated with the logged-in user
        student_profile = Student.objects.get(user=logged_in_user)

        # Get the teacher associated with this student
        my_teacher = student_profile.form_teacher

        context = {
            'student': student_profile,
            'teacher': my_teacher,
            'has_teacher': True if my_teacher else False # For template logic
        }
    except Student.DoesNotExist:
        # Handle cases where a logged-in user doesn't have a Student profile
        # (e.g., if they are a teacher, or haven't completed their profile)
        context = {
            'student': None,
            'teacher': None,
            'has_teacher': False,
            'message': "You don't have a student profile yet."
        }
        # You might redirect them to a profile creation page or show a relevant message
        # return redirect('create_student_profile')

    return render(request, 'students/my_teacher_detail.html', context)


# Specific to the login detail
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Lecturer


# =========================
# 1. LOGGED-IN LECTURER VIEW
# =========================
class LecturerSelfDetailView(LoginRequiredMixin, DetailView):
    """
    Lecturer views their own profile (tertiary portal logic)
    """
    model = Lecturer
    template_name = 'staff/lecturer_self_detail.html'
    context_object_name = 'lecturer'

    def get_object(self):
        return get_object_or_404(
            Lecturer.objects.select_related('user', 'department', 'position'),
            user=self.request.user
        )
    
class LecturerDetailView(LoginRequiredMixin, DetailView):
    """
    Staff/Admin view for any lecturer profile
    """
    model = Lecturer
    template_name = 'staff/lecturer_detail.html'
    context_object_name = 'lecturer'

    def get_object(self):
        return get_object_or_404(
            Lecturer.objects.select_related('user', 'department', 'position'),
            pk=self.kwargs.get("pk")
        )
    


# Lecturer view assigned courses
@login_required
def lecturer_my_courses(request):
    if not hasattr(request.user, "lecturer"):
        return redirect("pages:portal-home")

    assignments = CourseAssignment.objects.select_related(
        "course", "session", "semester"
    ).filter(
        lecturer=request.user.lecturer
    ).order_by("-assigned_date")

    # CSV EXPORT
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="my_courses.csv"'

        writer = csv.writer(response)
        writer.writerow(["Course Code", "Course Title", "Session", "Semester", "Adviser"])

        for a in assignments:
            writer.writerow([
                a.course.course_code,
                a.course.title,
                a.session,
                a.semester,
                "Yes" if a.is_course_adviser else "No"
            ])

        return response

    return render(request, "staff/lecturer_my_courses.html", {
        "assignments": assignments
    })

# admin view lecturers assinged course
@login_required
def admin_course_assignments(request):
    if not request.user.is_staff:
        return redirect("pages:portal-home")

    assignments = CourseAssignment.objects.select_related(
        "lecturer__user",
        "course",
        "session",
        "semester"
    ).order_by("-assigned_date")

    search = request.GET.get("search")
    if search:
        assignments = assignments.filter(
            course__course_code__icontains=search
        ) | assignments.filter(
            lecturer__user__first_name__icontains=search
        )

    # CSV EXPORT
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="course_assignments.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Lecturer",
            "Course Code",
            "Course Title",
            "Session",
            "Semester",
            "Adviser"
        ])

        for a in assignments:
            writer.writerow([
                a.lecturer.get_full_name(),
                a.course.course_code,
                a.course.title,
                a.session,
                a.semester,
                "Yes" if a.is_course_adviser else "No"
            ])

        return response

    return render(request, "staff/admin_course_assignments.html", {
        "assignments": assignments,
        "search": search
    })
  


# Teachers Student Count In Class

class LecturerStudentCountListView(ListView):
    model = Lecturer
    template_name = 'staff/all_teachers_student_counts.html'
    context_object_name = 'lecturer'

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            'teacher__current_class'
        ).order_by('user__last_name', 'user__first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        filtered_teachers = []

        for teacher in context['teachers']:
            # 1. Filter students: Exclude "Alumni"
            active_students = [
                s for s in teacher.teacher.all()
                if s.current_class and s.current_class.name != "Alumni"
            ]

            # 2. Calculate the Total Count
            count = len(active_students)

            # 3. ONLY proceed if the teacher has students (is a form teacher)
            if count > 0:
                teacher.total_student_count = count

                # 4. Determine the Unique Class Objects
                unique_classes = {s.current_class for s in active_students}

                # 5. Create the sorted list for badges
                teacher.class_list = [c.name for c in sorted(list(unique_classes), key=lambda x: x.name)]

                # Add this teacher to our final list
                filtered_teachers.append(teacher)

        # 6. Replace the context with our filtered list
        context['teachers'] = filtered_teachers
        return context
    
"""
staff.views (PDF export additions)
===================================

Server-rendered "Download PDF" for a lecturer's profile, as an alternative
to the browser's Print / Save as PDF button already on both templates.
Mirrors the reportlab pattern already used in finance.services.documents
(build_payment_receipt_pdf / build_registration_slip_pdf), so a downloaded
file looks consistent regardless of the viewer's browser/print settings.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

from curriculum.utils.identity import get_school_identity_for_department

from .models import Lecturer


def _build_lecturer_profile_pdf(lecturer, school_identity):
    """
    Shared PDF layout for both the self-view and admin-view downloads,
    so the document never drifts out of sync between the two.

    `school_identity` must be an already-resolved SchoolIdentity instance
    (or None) — resolve it via curriculum.utils.identity.
    get_school_identity_for_department() before calling this, since
    context processors never run outside of template rendering and can't
    be reached from a raw reportlab view.
    """
    response = HttpResponse(content_type='application/pdf')
    filename = f"{lecturer.user.username}_profile.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'SchoolTitle', parent=styles['Heading1'],
        fontSize=16, textColor=colors.HexColor('#1a237e'), spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#64748b'),
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Heading3'],
        fontSize=11, textColor=colors.HexColor('#1a237e'),
        spaceBefore=14, spaceAfter=6,
    )

    elements = []

    school_name = school_identity.name if school_identity else "School"
    elements.append(Paragraph(school_name, title_style))
    elements.append(Paragraph("Lecturer Academic Profile", subtitle_style))
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", color=colors.HexColor('#1a237e'), thickness=1.5))
    elements.append(Spacer(1, 16))

    # --- Identity block ---
    identity_data = [
        ["Name:", lecturer.get_full_name(), "Username:", f"@{lecturer.user.username}"],
        ["Department:", str(lecturer.department) if lecturer.department else "—",
         "Position:", str(lecturer.position) if lecturer.position else "—"],
        ["Status:", "ACTIVE" if lecturer.is_active else "INACTIVE",
         "Employed:", lecturer.date_employed.strftime('%b %d, %Y') if lecturer.date_employed else "—"],
    ]
    identity_table = Table(identity_data, colWidths=[70, 170, 70, 170])
    identity_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748b')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#64748b')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(identity_table)

    def section(title, rows, col_widths=(140, 340)):
        elements.append(Paragraph(title, section_style))
        table = Table(rows, colWidths=list(col_widths))
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9.5),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748b')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
        ]))
        elements.append(table)

    section("Personal Details", [
        ["Email Address", lecturer.user.email or "—"],
        ["Phone Number", lecturer.phone or "—"],
        ["Gender", lecturer.gender or "—"],
        ["Date of Birth", str(lecturer.DOB) if lecturer.DOB else "—"],
        ["Marital Status", lecturer.marital_status or "—"],
    ])

    section("Academic Credentials", [
        ["Highest Qualification", lecturer.highest_qualification or "—"],
        ["Awarding Institution", lecturer.institution or "—"],
        ["Year Obtained", str(lecturer.year_obtained) if lecturer.year_obtained else "—"],
        ["Professional Memberships", lecturer.professional_body or "No memberships listed"],
    ])

    section("Guarantor Information", [
        ["Guarantor Name", lecturer.guarantor_name or "—"],
        ["Contact Phone", lecturer.guarantor_phone or "—"],
        ["Residential Address", lecturer.guarantor_address or "—"],
    ])

    elements.append(Spacer(1, 24))
    elements.append(HRFlowable(width="100%", color=colors.HexColor('#e2e8f0'), thickness=0.5))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "This document was generated by the school's portal system and reflects the "
        "record on file at the time of generation.",
        subtitle_style,
    ))

    doc.build(elements)
    return response


@login_required
def lecturer_self_profile_pdf(request):
    """Lecturer downloads their own profile as a PDF."""
    lecturer = get_object_or_404(
        Lecturer.objects.select_related('user', 'department', 'position'),
        user=request.user,
    )
    school_identity = get_school_identity_for_department(lecturer.department)
    return _build_lecturer_profile_pdf(lecturer, school_identity)


@login_required
def lecturer_profile_pdf(request, pk):
    """
    Staff/admin downloads any lecturer's profile as a PDF.

    Identity is resolved from the department of the lecturer the document
    is ABOUT, not the viewing admin's own department — mirroring how the
    school_info context processor resolves branding from the *subject*
    of a matric_number-based student page rather than the viewer.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponse("Not permitted.", status=403)

    lecturer = get_object_or_404(
        Lecturer.objects.select_related('user', 'department', 'position'),
        pk=pk,
    )
    school_identity = get_school_identity_for_department(lecturer.department)
    return _build_lecturer_profile_pdf(lecturer, school_identity)




# Teachers Signup View
# Get the custom User model if it exists, otherwise use the default
User = get_user_model()

@login_required
def teacher_user_signup(request):
    school_identity = SchoolIdentity.objects.first()
    
    if request.method == 'POST':
        user_form = CustomUserCreationForm(request.POST)
        if user_form.is_valid():
            # Store validated user data in the session
            request.session['teacher_user_data'] = {
                'username': user_form.cleaned_data['username'],
                'first_name': user_form.cleaned_data['first_name'],
                'last_name': user_form.cleaned_data['last_name'],
                'email': user_form.cleaned_data.get('email', ''), 
                'password': user_form.cleaned_data['password2'],
            }
            messages.success(request, 'User account created successfully. Please fill in the rest of the details.')
            return redirect('staff:teacher_details_signup')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = CustomUserCreationForm()
        
    context = {
        'user_form': user_form,
        'school_identity': school_identity,
    }
    return render(request, 'staff/teacher_user_signup.html', context)



# Get the active User model
User = get_user_model()

@login_required
def teacher_details_signup(request):
    user_data = request.session.get('teacher_user_data')
    if not user_data:
        messages.error(request, 'Session expired. Please start the signup process again.')
        return redirect('staff:teacher_user_signup')

    school_identity = SchoolIdentity.objects.first()

    if request.method == 'POST':
        teacher_form = TeacherForm(request.POST, request.FILES)
        if teacher_form.is_valid():
            try:
                with transaction.atomic():
                    # Create the User instance using data from the *form*
                    user = User.objects.create_user(
                        username=user_data['username'],
                        password=user_data['password'],
                        email=user_data.get('email'),
                        # Get first_name and last_name from the validated form data
                        first_name=teacher_form.cleaned_data['first_name'],
                        last_name=teacher_form.cleaned_data['last_name'],
                    )

                    # Save the Teacher instance linked to the new user
                    teacher = teacher_form.save(commit=False)
                    teacher.user = user
                    teacher.save()
                    teacher_form.save_m2m() 
            
                if 'teacher_user_data' in request.session:
                    del request.session['teacher_user_data']

                messages.success(request, f'Teacher account for {user.first_name} {user.last_name} created successfully.')
                return redirect('staff:teacher_signup_success')
            except Exception as e:
                # Catch the specific KeyError and handle it gracefully
                # If the form is valid, this part should not be hit.
                messages.error(request, f'An error occurred: {e}')
                return redirect('staff:teacher_details_signup')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # On GET, populate the form with initial data from the session
        initial_data = {
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
        }
        teacher_form = TeacherForm(initial=initial_data)

    context = {
        'teacher_form': teacher_form,
        'school_identity': school_identity,
    }
    return render(request, 'staff/teacher_details_signup.html', context)



@login_required
def teacher_signup_success(request):
    """
    Renders the success page after a teacher has been signed up.
    Provides options to sign up another teacher or go back to the dashboard.
    """
    school_identity = SchoolIdentity.objects.first()
    context = {
        'school_identity': school_identity,
    }
    return render(request, 'staff/teacher_signup_success.html', context)

