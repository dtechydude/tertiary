#=================================================================================================
# NEW TERTIARY ATTENDANCE TAKING LOGIC
#=======================================================================================
from django.shortcuts import render, redirect, get_object_or_404
from django.forms import modelformset_factory
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .forms import AttendanceReportForm
from .models import Attendance
from students.models import Student
from curriculum.models import Course, Semester, CourseAssignment, Department, Session
from staff.models import Lecturer
from .utils import get_student_attendance_metrics
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required






# def is_authorized_to_view_student(user, student_id):
#     if user.is_staff or user.is_superuser:
#         return True
#     try:
#         student = Student.objects.get(pk=student_id)
#         # Check if the user is the student or their form lecturer
#         if student.user == user: return True
#         if student.form_lecturer and student.form_lecturer.user == user: return True
#     except Student.DoesNotExist:
#         pass
#     return False

def is_authorized_to_view_student(user, student_id):
    if user.is_staff or user.is_superuser:
        return True

    try:
        student = Student.objects.get(pk=student_id)

        # Student can view self
        if student.user == user:
            return True

        # Lecturer check via department (safe tertiary fallback)
        if hasattr(user, 'lecturer'):
            if student.department == user.lecturer.department:
                return True

    except Student.DoesNotExist:
        pass

    return False

# ==========================================
# ACCESS CONTROL HELPER
# ==========================================
def can_manage_attendance(user, course):
    """
    Checks if user is allowed to take/edit attendance for a specific course.
    Only the assigned lecturer, an admin (is_staff), or a superuser is allowed.
    """
    if user.is_superuser or user.is_staff:
        return True
    
    try:
        # Check if the user has a lecturer profile and if they are assigned to this course
        if hasattr(user, 'lecturer') and course.lecturer == user.lecturer:
            return True
    except Lecturer.DoesNotExist:
        pass
    
    return False

# ==========================================
# 1. TAKE COURSE ATTENDANCE
# ==========================================
# @login_required
# def take_course_attendance(request, course_id):
#     course = get_object_or_404(Course, id=course_id)

#     # SECURITY: Verify assigned lecturer or admin status
#     if not can_manage_attendance(request.user, course):
#         messages.error(request, "Access Denied: You are not authorized to manage attendance for this course.")
#         return redirect('dashboard')

#     # Get date from GET request or default to today
#     selected_date_str = request.GET.get('date')
#     if selected_date_str:
#         try:
#             selected_date = timezone.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
#         except ValueError:
#             selected_date = timezone.localdate()
#     else:
#         selected_date = timezone.localdate()

#     # Filter students by Department and Level (matching your Course model structure)
#     students = Student.objects.filter(
#         department=course.department, 
#         level=course.level
#     ).order_by('last_name', 'first_name')

#     # Atomically ensure records exist for all students for this course/date
#     initial_ids = []
#     for student in students:
#         record, _ = Attendance.objects.get_or_create(
#             student=student,
#             course=course,
#             date=selected_date,
#             defaults={'status': Attendance.Status.ABSENT} # Default to Absent in tertiary
#         )
#         initial_ids.append(record.id)

#     AttendanceFormSet = modelformset_factory(
#         Attendance,
#         fields=('status', 'remarks'),
#         extra=0
#     )

#     if request.method == 'POST':
#         formset = AttendanceFormSet(request.POST, queryset=Attendance.objects.filter(id__in=initial_ids))
#         if formset.is_valid():
#             with transaction.atomic():
#                 instances = formset.save(commit=False)
#                 for instance in instances:
#                     # Update marked_by to the lecturer currently submitting
#                     if hasattr(request.user, 'lecturer'):
#                         instance.marked_by = request.user.lecturer
#                     instance.save()
#             messages.success(request, f"Attendance for {course.course_code} on {selected_date} saved.")
#             return redirect('attendance:course_list') # Adjust to your actual course list URL
#     else:
#         formset = AttendanceFormSet(queryset=Attendance.objects.filter(id__in=initial_ids))

#     # Pair forms with student objects for the template display
#     student_forms = zip(students, formset)

#     context = {
#         'course': course,
#         'formset': formset,
#         'student_forms': student_forms,
#         'selected_date': selected_date,
#     }
#     return render(request, 'attendance/take_attendance.html', context)


# @login_required
# def take_course_attendance(request, course_id):
#     course = get_object_or_404(Course, id=course_id)

#     # SECURITY CHECK
#     if not can_manage_attendance(request.user, course):
#         messages.error(request, "Access Denied: Not authorized.")
#         return redirect('dashboard')

#     # DATE HANDLING
#     selected_date = request.GET.get('date')
#     try:
#         selected_date = timezone.datetime.strptime(selected_date, '%Y-%m-%d').date()
#     except:
#         selected_date = timezone.localdate()

#     # ✔ FIXED STUDENT FILTER (NO form_lecturer ERROR)
#     students = Student.objects.filter(
#         department=course.department,
#         level=course.level
#     ).order_by('user__last_name', 'user__first_name')

#     # Ensure attendance records exist
#     attendance_ids = []
#     for student in students:
#         record, _ = Attendance.objects.get_or_create(
#             student=student,
#             course=course,
#             date=selected_date,
#             defaults={'status': Attendance.Status.ABSENT}
#         )
#         attendance_ids.append(record.id)

#     AttendanceFormSet = modelformset_factory(
#         Attendance,
#         fields=('status', 'remarks'),
#         extra=0
#     )

#     queryset = Attendance.objects.filter(id__in=attendance_ids)

#     if request.method == 'POST':
#         formset = AttendanceFormSet(request.POST, queryset=queryset)

#         if formset.is_valid():
#             with transaction.atomic():
#                 instances = formset.save(commit=False)
#                 for obj in instances:
#                     if hasattr(request.user, 'lecturer'):
#                         obj.marked_by = request.user.lecturer
#                     obj.save()

#             messages.success(request, "Attendance saved successfully.")
#             return redirect('attendance:course_list')

#     else:
#         formset = AttendanceFormSet(queryset=queryset)

#     student_forms = zip(students, formset)

#     return render(request, 'attendance/take_attendance.html', {
#         'course': course,
#         'formset': formset,
#         'student_forms': student_forms,
#         'selected_date': selected_date,
#     })

@login_required
def take_course_attendance(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    # --------------------------------------------------
    # SECURITY: Lecturer must be assigned to this course
    # --------------------------------------------------
    is_assigned = CourseAssignment.objects.filter(
        lecturer=request.user.lecturer,
        course=course
    ).exists() if hasattr(request.user, 'lecturer') else False

    if not (request.user.is_staff or request.user.is_superuser or is_assigned):
        messages.error(request, "Access Denied: You are not assigned to this course.")
        return redirect('dashboard')

    # --------------------------------------------------
    # DATE HANDLING
    # --------------------------------------------------
    date_str = request.GET.get('date')
    try:
        selected_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        selected_date = timezone.localdate()

    # --------------------------------------------------
    # STUDENTS: ONLY THOSE REGISTERED FOR THIS COURSE
    # --------------------------------------------------
    students = Student.objects.filter(
        course_registrations__course=course
    ).select_related('user').distinct().order_by(
        'user__last_name',
        'user__first_name'
    )

    # --------------------------------------------------
    # ENSURE ATTENDANCE RECORDS EXIST
    # --------------------------------------------------
    attendance_qs = Attendance.objects.filter(
        course=course,
        date=selected_date,
        student__in=students
    )

    existing_student_ids = set(attendance_qs.values_list('student_id', flat=True))

    new_records = []
    for student in students:
        if student.id not in existing_student_ids:
            new_records.append(
                Attendance(
                    student=student,
                    course=course,
                    date=selected_date,
                    status=Attendance.Status.ABSENT
                )
            )

    if new_records:
        Attendance.objects.bulk_create(new_records)

    attendance_qs = Attendance.objects.filter(
        course=course,
        date=selected_date,
        student__in=students
    )

    # --------------------------------------------------
    # FORMSET
    # --------------------------------------------------
    AttendanceFormSet = modelformset_factory(
        Attendance,
        fields=('status', 'remarks'),
        extra=0
    )

    if request.method == 'POST':
        formset = AttendanceFormSet(request.POST, queryset=attendance_qs)

        if formset.is_valid():
            instances = formset.save(commit=False)

            for obj in instances:
                obj.marked_by = getattr(request.user, 'lecturer', None)
                obj.save()

            messages.success(request, "Attendance successfully saved.")
            return redirect('attendance:attendance-student-list')

    else:
        formset = AttendanceFormSet(queryset=attendance_qs)

    # Pair students with forms for template rendering
    student_forms = zip(students, formset)

    return render(request, 'attendance/take_attendance.html', {
        'course': course,
        'formset': formset,
        'student_forms': student_forms,
        'selected_date': selected_date,
    })

# ==========================================
# 2. SCAN ATTENDANCE AJAX
# ==========================================
@csrf_exempt
@login_required
def scan_attendance_ajax(request, usn):
    """
    Updates attendance status to 'Present' via ID scan.
    Requires 'course_id' to be passed in POST data.
    """
    course_id = request.POST.get('course_id')
    course = get_object_or_404(Course, id=course_id)

    if not can_manage_attendance(request.user, course):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized to mark attendance.'}, status=403)

    try:
        # Match using the Matric Number established in your Student model
        student = Student.objects.get(matric_number__iexact=usn.strip())
        today = timezone.localdate()

        attendance, created = Attendance.objects.update_or_create(
            student=student,
            course=course,
            date=today,
            defaults={'status': Attendance.Status.PRESENT}
        )

        current_total = Attendance.objects.filter(
            course=course, 
            date=today, 
            status=Attendance.Status.PRESENT
        ).count()

        return JsonResponse({
            'status': 'success',
            'message': f'{student.get_full_name()} marked Present for {course.course_code}',
            'present_count': current_total
        })

    except Student.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': f'Matric No. "{usn}" not found.'})
    

@login_required
def attendance_report(request):
    """
    Refactored Global Report View for Admins and Lecturers.
    Supports filtering by Date, Student, and Course.
    """
    user = request.user
    is_superuser = user.is_superuser
    lecturer = getattr(user, 'lecturer', None)

    # Initialize your existing form
    # Note: Ensure your AttendanceReportForm is updated to include a 'course' field
    report_form = AttendanceReportForm(request.GET or None, lecturer=lecturer, is_superuser=is_superuser)
    
    attendance_data = {}
    student_summary = {} 
    
    # Date Range Setup
    today = timezone.localdate()
    start_date = report_form.cleaned_data.get('start_date') if report_form.is_valid() else today - timezone.timedelta(days=7)
    end_date = report_form.cleaned_data.get('end_date') if report_form.is_valid() else today

    if report_form.is_valid():
        selected_student = report_form.cleaned_data.get('student')
        selected_course = report_form.cleaned_data.get('course')
        selected_class = report_form.cleaned_data.get('current_class')

        # Base Query
        records = Attendance.objects.filter(date__range=(start_date, end_date))

        # Apply Filters
        if selected_student:
            records = records.filter(student=selected_student)
        elif not is_superuser and lecturer:
            # If lecturer, only show students in courses they teach
            records = records.filter(course__lecturer=lecturer)
        
        if selected_course:
            records = records.filter(course=selected_course)
        
        if selected_class:
            records = records.filter(student__current_class=selected_class)

        # Process data for the table
        for record in records.select_related('student', 'course').order_by('student__user__last_name', 'date'):
            student = record.student
            if student not in attendance_data:
                attendance_data[student] = {}
                student_summary[student] = {'P': 0, 'A': 0, 'L': 0, 'E': 0, 'total': 0}

            attendance_data[student][record.date] = record
            
            # Increment the specific status count (P, A, L, or E)
            status = record.status
            student_summary[student][status] = student_summary[student].get(status, 0) + 1
            student_summary[student]['total'] += 1

    context = {
        'report_form': report_form,
        'attendance_data': attendance_data,
        'student_summary': student_summary,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'attendance/test_attendance_report.html', context)


# @login_required
# def student_list_view(request):
#     """
#     Displays a list of students the logged-in user is authorized to see.
#     Admins see everyone; Lecturers see their assigned students.
#     """
#     user = request.user
#     title = "Attendance Roster"
    
#     # 1. Staff/Admin View (See All)
#     if user.is_staff or user.is_superuser:
#         students = Student.objects.select_related('current_class', 'department').all().order_by('current_class', 'last_name')
#         title = "All Students Attendance Records"
    
#     # 2. Lecturer View (Filtered by their assigned Department or Form Class)
#     else:
#         try:
#             lecturer_profile = user.lecturer
#             # This filters students who have this lecturer as their "Form Lecturer"
#             # OR students within the lecturer's department.
#             students = Student.objects.filter(
#                 form_lecturer=lecturer_profile
#             ).select_related('current_class', 'department').order_by('last_name')
#             title = f"Roster: {lecturer_profile.user.get_full_name()}'s Students"
            
#         except Lecturer.DoesNotExist:
#             # Fallback if a non-lecturer/non-staff user tries to access this
#             messages.error(request, "Lecturer profile not found.")
#             return redirect('dashboard')

#     context = {
#         'students': students,
#         'title': title,
#         'is_staff': user.is_staff,
#     }
#     return render(request, 'attendance/student_attendance_list.html', context)

from django.db.models import Q

# @login_required
# def student_list_view(request):
#     """
#     Attendance roster view:
#     - Admin/Superuser: sees all students
#     - Lecturer: sees students in courses assigned to them
#     """

#     user = request.user
#     title = "Attendance Roster"

    
#     # ==============================
#     # 1. ADMIN / STAFF VIEW
#     # ==============================
#     if user.is_staff or user.is_superuser:
#         students = Student.objects.select_related(
#             'department', 'level', 'user'
#         ).all().order_by('user__last_name')

#         title = "All Students Attendance Records"

#     # ==============================
#     # 2. LECTURER VIEW (TERTIARY LOGIC)
#     # ==============================
#     else:
#         try:
#             lecturer = user.lecturer

#             # Get all courses assigned to this lecturer
#             assigned_courses = CourseAssignment.objects.filter(
#                 lecturer=lecturer
#             ).values_list('course', flat=True)

#             # Get students registered for those courses
#             students = Student.objects.filter(
#                 course_registrations__course_id__in=assigned_courses
#             ).distinct().select_related(
#                 'department', 'level', 'user'
#             ).order_by('user__last_name')

#             title = f"Roster: {lecturer.user.get_full_name()}"

#         except Lecturer.DoesNotExist:
#             messages.error(request, "Lecturer profile not found.")
#             return redirect('dashboard')
        
#     assigned_courses = CourseAssignment.objects.filter(lecturer=lecturer).select_related('course', 'course__department')
#     departments = Department.objects.filter(course__assignments__lecturer=lecturer).distinct()

#     context = {
#         'students': students,
#         'title': title,
#         'is_staff': user.is_staff,
#         'assigned_courses':assigned_courses,
#         'departments':departments,
#     }

#     return render(request, 'attendance/student_attendance_list.html', context)


@login_required
def student_list_view(request):
    """
    Attendance roster view:
    - Admin/Superuser: sees all students
    - Lecturer: sees students registered to their assigned courses
    """

    user = request.user
    title = "Attendance Roster"

    students = Student.objects.none()
    assigned_courses = CourseAssignment.objects.none()
    departments = Department.objects.none()

    # ==============================
    # 1. ADMIN / STAFF VIEW
    # ==============================
    if user.is_staff or user.is_superuser:

        students = Student.objects.select_related(
            'department', 'level', 'user'
        ).all().order_by('user__last_name')

        title = "All Students Attendance Records"

        # optional filters still available for UI consistency
        assigned_courses = CourseAssignment.objects.select_related(
            'course', 'course__department', 'lecturer'
        )

        departments = Department.objects.all()

    # ==============================
    # 2. LECTURER VIEW
    # ==============================
    else:
        try:
            lecturer = user.lecturer

            # Courses assigned to lecturer
            assigned_courses = CourseAssignment.objects.filter(
                lecturer=lecturer
            ).select_related('course', 'course__department')

            course_ids = assigned_courses.values_list('course_id', flat=True)

            # Students registered to those courses
            students = Student.objects.filter(
                course_registrations__course_id__in=course_ids
            ).distinct().select_related(
                'department', 'level', 'user'
            ).order_by('user__last_name')

            # Departments linked to assigned courses
            departments = Department.objects.filter(
                course__assignments__lecturer=lecturer
            ).distinct()

            title = f"Roster: {lecturer.user.get_full_name()}"

        except Lecturer.DoesNotExist:
            messages.error(request, "Lecturer profile not found.")
            return redirect('dashboard')

    # ==============================
    # CONTEXT
    # ==============================
    context = {
        'students': students,
        'title': title,
        'is_staff': user.is_staff,

        # for template filters
        'assigned_courses': assigned_courses,
        'departments': departments,
    }

    return render(request, 'attendance/student_attendance_list.html', context)



@login_required
def student_attendance_summary(request, student_id):
    """
    Staff/Admin view of a specific student's attendance metrics.
    Uses the logic from utils.py to calculate percentages per course.
    """
    # Authorization Check
    if not is_authorized_to_view_student(request.user, student_id):
        return HttpResponseForbidden("You are not authorized to view this student's records.")
        
    current_student = get_object_or_404(Student, pk=student_id)
    
    try:
        # Get the current active Semester
        current_semester = Semester.objects.get(is_current=True) 
        
        # Get Course-by-Course breakdown using the utility function
        courses = Course.objects.filter(
            department=current_student.department, 
            level=current_student.level
        )
        
        course_reports = []
        for course in courses:
            metrics = get_student_attendance_metrics(
                current_student, 
                current_semester.start_date, 
                current_semester.end_date,
                course=course
            )
            course_reports.append({
                'course': course,
                'metrics': metrics
            })

        # Calculate Overall Metrics
        overall = get_student_attendance_metrics(
            current_student, 
            current_semester.start_date, 
            current_semester.end_date
        )

        context = {
            'student': current_student,
            'course_reports': course_reports,
            'overall': overall,
            'semester': current_semester,
        }
        
    except Semester.DoesNotExist:
        messages.error(request, "No active semester found for reporting.")
        return redirect('attendance:attendance-student-list')

    return render(request, 'attendance/student_attendance_summary.html', context)

@login_required
def student_attendance_detail(request, student_id):
    """
    Displays a detailed calendar/list view of all attendance records 
    for a specific student during the current semester.
    """
    if not is_authorized_to_view_student(request.user, student_id):
        return HttpResponseForbidden("Access Denied.")
    
    current_student = get_object_or_404(Student, pk=student_id)
    
    try:
        current_semester = Semester.objects.get(is_current=True) 
        records = Attendance.objects.filter(
            student=current_student,
            date__range=(current_semester.start_date, current_semester.end_date)
        ).select_related('course').order_by('-date')

        # Prepare a JSON map for the frontend calendar if needed
        attendance_map = {
            rec.date.strftime('%Y-%m-%d'): rec.status for rec in records
        }

        context = {
            'student': current_student,
            'records': records,
            'attendance_data_json': json.dumps(attendance_map),
            'semester': current_semester,
        }
        return render(request, 'attendance/student_attendance_detail.html', context)
    except Semester.DoesNotExist:
        messages.error(request, "Current semester not defined.")
        return redirect('attendance:attendance-student-list')
    

@login_required
def self_attendance_summary(request):
    """ Redirects a logged-in student to their own summary page. """
    try:
        student_profile = request.user.student
        return student_attendance_summary(request, student_profile.id)
    except Exception:
        messages.error(request, "Student profile not found.")
        return redirect('dashboard')

@login_required
def self_attendance_detail(request):
    """ Redirects a logged-in student to their own detailed calendar. """
    try:
        student_profile = request.user.student
        return student_attendance_detail(request, student_profile.id)
    except Exception:
        messages.error(request, "Student profile not found.")
        return redirect('dashboard')


# # Attendance Scanner    
# @login_required
# def attendance_scanner_view(request, course_id=None):
#     """
#     Renders the QR scanner interface. 
#     If course_id is None, it provides a selection of available courses.
#     """
#     # 1. Handle the "Selection" phase if no course_id is provided
#     if course_id is None:
#         if request.user.is_superuser or request.user.is_staff:
#             courses = Course.objects.all()
#         else:
#             # Assuming you have a 'teacher' relationship to Course
#             courses = Course.objects.filter(teacher__user=request.user)
            
#         return render(request, 'attendance/scanner_course_select.html', {
#             'courses': courses
#         })

#     # 2. Handle the "Scanner" phase if course_id is provided
#     course = get_object_or_404(Course, id=course_id)
    
#     if not can_manage_attendance(request.user, course):
#         messages.error(request, "You are not authorized to scan for this course.")
#         return redirect('attendance:attendance_scanner_view') # Redirect back to select

#     return render(request, 'attendance/attendance_scanner.html', {
#         'course': course,
#         'today': timezone.localdate(),
#     })

# attendance/views.py

@login_required
def attendance_scanner_view(request, course_id=None):
    """
    Operates in two modes:
    1. Selection Mode (No ID): User chooses which course they are teaching.
    2. Scanner Mode (With ID): Opens the camera to scan student QRs.
    """
    
    # PHASE 1: SELECTION
    if course_id is None:
        if request.user.is_superuser or request.user.is_staff:
            courses = Course.objects.all()
        else:
            # Safer filtering: only show courses where the user is assigned as the teacher
            # Adjust 'teacher__user' to match your actual Course model relationship
            courses = Course.objects.filter(lecturer__user=request.user)
            
        return render(request, 'attendance/scanner_course_select.html', {
            'courses': courses
        })

    # PHASE 2: SCANNING
    course = get_object_or_404(Course, id=course_id)
    
    # Authorization Check
    # Ensure can_manage_attendance is imported or defined
    if not can_manage_attendance(request.user, course):
        messages.error(request, "Access Denied: You are not assigned to this course.")
        return redirect('attendance:attendance_scanner') 

    return render(request, 'attendance/attendance_scanner.html', {
        'course': course,
        'today': timezone.localdate(),
    })