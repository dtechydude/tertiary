"""
curriculum.views
================

Front-end views for the Faculty/Department/Session/Course structures
defined in curriculum.models, split by audience:

  - Everyone (students, lecturers, staff): the Academic Calendar.
  - Students: My Programme, Course Registration.
  - Lecturers: My Courses, Course Roster, HOD Department Dashboard.
  - Admin/Registrar: Faculty & Department Directory, Registration
    Validation Queue, Session/Semester quick-admin.

Assumptions about neighbouring apps (flag if these don't match your
actual field names):
  - students.Student has: programme, level, department, matric_number,
    student_status (checked against the string "active").
  - staff.Lecturer has: get_full_name(), and is looked up via
    curriculum.CourseAssignment for "what do they teach" (no direct
    courses_assigned-style field is assumed to exist on Lecturer).
"""

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from staff.models import Lecturer
from students.models import Student

from .models import (
    Course,
    CourseAssignment,
    CourseRegistration,
    Department,
    Faculty,
    Level,
    Programme,
    RegistrationPolicy,
    Semester,
    Session,
)


# =====================================================================
# Helpers
# =====================================================================

def _get_student_or_none(user):
    try:
        return Student.objects.select_related('programme', 'level', 'department', 'department__faculty').get(user=user)
    except Student.DoesNotExist:
        return None


def _get_lecturer_or_none(user):
    try:
        return Lecturer.objects.get(user=user)
    except Lecturer.DoesNotExist:
        return None


def _current_session():
    return Session.objects.filter(is_current=True).first()


def _current_semester():
    return Semester.objects.filter(is_current=True).first()


def _is_registrar(user):
    """Staff/superuser, or anyone explicitly granted the validate_registration permission."""
    return user.is_staff or user.is_superuser or user.has_perm('curriculum.validate_registration')


def _is_hod_of(lecturer, department):
    return bool(lecturer and department and department.hod_id == lecturer.id)


def _effective_registration_policy(level):
    """
    Resolution order per the model's own docstring:
    Level-specific override -> Programme-wide default -> hard-coded fallback.
    """
    if level:
        policy = getattr(level, 'registration_policy', None)
        if policy:
            return policy

        if level.programme_id:
            policy = RegistrationPolicy.objects.filter(
                programme_id=level.programme_id, level__isnull=True
            ).first()
            if policy:
                return policy

    class _Fallback:
        min_units_per_semester = 12
        max_units_per_semester = 24
        max_carryover_units = 0

    return _Fallback()


def _registration_window_status(semester):
    """
    Returns a dict describing whether registration is currently open, in
    the late-fee window, or closed, based on the Semester's own
    reg_start_date / reg_end_date / late_reg_end_date / is_reg_active
    fields.
    """
    today = timezone.localdate()

    if not semester:
        return {'state': 'closed', 'label': 'No active semester', 'late_fee': None}

    if not semester.is_reg_active:
        return {'state': 'closed', 'label': 'Registration manually closed by admin', 'late_fee': None}

    if semester.reg_start_date and today < semester.reg_start_date:
        return {
            'state': 'not_started',
            'label': f'Opens {semester.reg_start_date:%b %d, %Y}',
            'late_fee': None,
        }

    if semester.reg_end_date and today <= semester.reg_end_date:
        return {'state': 'open', 'label': 'Open — normal registration', 'late_fee': None}

    if semester.late_reg_end_date and today <= semester.late_reg_end_date:
        return {
            'state': 'late',
            'label': f'Late registration — a fee of {semester.late_reg_fee} applies',
            'late_fee': semester.late_reg_fee,
        }

    if semester.reg_end_date or semester.late_reg_end_date:
        return {'state': 'closed', 'label': 'Registration deadline has passed', 'late_fee': None}

    # No deadlines configured at all — treat as open indefinitely.
    return {'state': 'open', 'label': 'Open', 'late_fee': None}


# =====================================================================
# Academic Calendar — visible to every logged-in user
# =====================================================================

@login_required
def academic_calendar_view(request):
    """
    Every Session and its Semesters, with start/end dates and
    registration windows, so students always know exactly when a
    semester starts/ends and when registration opens/closes.
    """
    sessions = Session.objects.prefetch_related('terms').order_by('-start_date')

    today = timezone.localdate()
    calendar_rows = []

    for session in sessions:
        semesters = []
        for semester in session.terms.all().order_by('start_date'):
            window = _registration_window_status(semester)

            if semester.start_date and semester.end_date:
                if today < semester.start_date:
                    phase = 'upcoming'
                elif today > semester.end_date:
                    phase = 'completed'
                else:
                    phase = 'ongoing'
            else:
                phase = 'unscheduled'

            semesters.append({
                'obj': semester,
                'window': window,
                'phase': phase,
            })
        calendar_rows.append({'session': session, 'semesters': semesters})

    return render(request, 'curriculum/academic_calendar.html', {
        'calendar_rows': calendar_rows,
        'current_session': _current_session(),
        'current_semester': _current_semester(),
    })


# =====================================================================
# Student: My Programme
# =====================================================================

@login_required
def my_programme_view(request):
    student = _get_student_or_none(request.user)
    if not student:
        messages.error(request, "This page is only available to students.")
        return redirect('curriculum:academic-calendar')

    programme = student.programme
    department = student.department
    faculty = department.faculty if department else None

    levels = Level.objects.filter(programme=programme).order_by('id') if programme else Level.objects.none()

    policy = _effective_registration_policy(student.level)

    peer_count = 0
    if student.level_id and student.department_id:
        peer_count = Student.objects.filter(
            level=student.level, department=student.department
        ).exclude(pk=student.pk).count()

    return render(request, 'curriculum/my_programme.html', {
        'student': student,
        'programme': programme,
        'department': department,
        'faculty': faculty,
        'levels': levels,
        'policy': policy,
        'peer_count': peer_count,
    })


# =====================================================================
# Student: Course Registration
# =====================================================================

@login_required
def course_registration_view(request):
    student = _get_student_or_none(request.user)
    if not student:
        messages.error(request, "This page is only available to students.")
        return redirect('curriculum:academic-calendar')

    session = _current_session()
    semester = _current_semester()
    window = _registration_window_status(semester)
    policy = _effective_registration_policy(student.level)

    if not session or not semester:
        messages.warning(request, "There is no active session/semester configured yet.")
        return render(request, 'curriculum/course_registration.html', {
            'window': window, 'session': session, 'semester': semester,
            'available_courses': [], 'my_registrations': [], 'policy': policy,
            'total_units': 0,
        })

    my_registrations = CourseRegistration.objects.filter(
        student=student, session=session, semester=semester
    ).select_related('course')

    registered_course_ids = set(my_registrations.values_list('course_id', flat=True))
    total_units = sum(reg.course.credit_unit for reg in my_registrations)

    available_courses = Course.objects.filter(
        department=student.department,
        level=student.level,
        programme=student.programme,
        session=session,
        semester=semester,
    ).exclude(id__in=registered_course_ids).select_related('lecturer').order_by('course_type', 'course_code')

    if request.method == 'POST':
        if window['state'] not in ('open', 'late'):
            messages.error(request, f"Registration is not currently open. {window['label']}")
            return redirect('curriculum:course-registration')

        action = request.POST.get('action')

        if action == 'register':
            selected_ids = set(request.POST.getlist('course_ids'))
            available_ids = {str(c.id) for c in available_courses}
            valid_selected_ids = selected_ids & available_ids
            selected_courses = Course.objects.filter(id__in=valid_selected_ids)

            new_units = sum(c.credit_unit for c in selected_courses)
            projected_total = total_units + new_units

            max_allowed = policy.max_units_per_semester + policy.max_carryover_units

            if not selected_courses:
                messages.warning(request, "No courses selected.")
            elif projected_total > max_allowed:
                messages.error(
                    request,
                    f"Registering these courses would bring your total to {projected_total} units, "
                    f"exceeding the maximum of {max_allowed} allowed for your level."
                )
            else:
                created = 0
                for course in selected_courses:
                    _, was_created = CourseRegistration.objects.get_or_create(
                        student=student, course=course, session=session, semester=semester,
                    )
                    created += 1 if was_created else 0

                if window['state'] == 'late' and window['late_fee']:
                    messages.warning(
                        request,
                        f"{created} course(s) registered. Note: a late registration fee of "
                        f"{window['late_fee']} applies — see the Finance office."
                    )
                else:
                    messages.success(request, f"{created} course(s) registered successfully.")

            return redirect('curriculum:course-registration')

    return render(request, 'curriculum/course_registration.html', {
        'window': window,
        'session': session,
        'semester': semester,
        'available_courses': available_courses,
        'my_registrations': my_registrations,
        'policy': policy,
        'total_units': total_units,
    })


@login_required
def drop_course_registration(request, registration_id):
    if request.method != 'POST':
        return redirect('curriculum:course-registration')

    student = _get_student_or_none(request.user)
    if not student:
        return HttpResponseForbidden("Not permitted.")

    registration = get_object_or_404(CourseRegistration, id=registration_id, student=student)

    if registration.is_validated:
        messages.error(
            request,
            "This registration has already been validated by the registrar and can no longer "
            "be dropped here — please contact the registrar's office."
        )
        return redirect('curriculum:course-registration')

    semester = registration.semester
    window = _registration_window_status(semester)
    if window['state'] not in ('open', 'late'):
        messages.error(request, f"Registration is not currently open. {window['label']}")
        return redirect('curriculum:course-registration')

    course_code = registration.course.course_code
    registration.delete()
    messages.success(request, f"{course_code} has been dropped from your registration.")
    return redirect('curriculum:course-registration')


# =====================================================================
# Lecturer: My Courses & Course Roster
# =====================================================================

@login_required
def lecturer_courses_view(request):
    lecturer = _get_lecturer_or_none(request.user)
    if not lecturer:
        messages.error(request, "This page is only available to lecturers.")
        return redirect('curriculum:academic-calendar')

    assignments = CourseAssignment.objects.filter(lecturer=lecturer).select_related(
        'course', 'course__department', 'course__level', 'session', 'semester'
    ).order_by('-session__start_date', 'course__course_code')

    rows = []
    for assignment in assignments:
        registered_count = CourseRegistration.objects.filter(
            course=assignment.course, session=assignment.session, semester=assignment.semester
        ).count()
        validated_count = CourseRegistration.objects.filter(
            course=assignment.course, session=assignment.session, semester=assignment.semester,
            is_validated=True,
        ).count()
        rows.append({
            'assignment': assignment,
            'registered_count': registered_count,
            'validated_count': validated_count,
        })

    department = getattr(lecturer, 'heading_department', None)
    is_hod = department.exists() if hasattr(department, 'exists') else False

    return render(request, 'curriculum/lecturer_courses.html', {
        'rows': rows,
        'is_hod': is_hod,
    })


@login_required
def course_roster_view(request, course_id, session_id, semester_id):
    lecturer = _get_lecturer_or_none(request.user)
    course = get_object_or_404(Course, id=course_id)
    session = get_object_or_404(Session, id=session_id)
    semester = get_object_or_404(Semester, id=semester_id)

    is_assigned = lecturer and CourseAssignment.objects.filter(
        lecturer=lecturer, course=course, session=session, semester=semester
    ).exists()
    is_hod = _is_hod_of(lecturer, course.department)

    if not is_assigned and not is_hod and not _is_registrar(request.user):
        messages.error(request, "Access Denied: You are not assigned to this course.")
        return redirect('curriculum:lecturer-courses')

    registrations = CourseRegistration.objects.filter(
        course=course, session=session, semester=semester
    ).select_related('student', 'student__level').order_by('student__matric_number')

    validated_count = sum(1 for r in registrations if r.is_validated)

    return render(request, 'curriculum/course_roster.html', {
        'course': course, 'session': session, 'semester': semester,
        'registrations': registrations, 'validated_count': validated_count,
        'total_count': len(registrations),
    })


# =====================================================================
# Lecturer (HOD): Department Dashboard
# =====================================================================

@login_required
def department_dashboard_view(request):
    lecturer = _get_lecturer_or_none(request.user)
    if not lecturer:
        messages.error(request, "This page is only available to lecturers.")
        return redirect('curriculum:academic-calendar')

    department = Department.objects.filter(hod=lecturer).first()
    if not department and not _is_registrar(request.user):
        messages.error(request, "You are not currently registered as a Head of Department.")
        return redirect('curriculum:lecturer-courses')

    programmes = Programme.objects.none()
    levels = Level.objects.none()
    student_count = 0
    lecturer_count = 0
    course_count = 0
    pending_validations = 0

    if department:
        courses = Course.objects.filter(department=department)
        course_count = courses.count()
        programme_ids = courses.values_list('programme_id', flat=True).distinct()
        programmes = Programme.objects.filter(id__in=programme_ids)
        levels = Level.objects.filter(programme_id__in=programme_ids).order_by('programme__name', 'id')
        student_count = Student.objects.filter(department=department).count()
        lecturer_count = CourseAssignment.objects.filter(
            course__department=department
        ).values('lecturer_id').distinct().count()
        pending_validations = CourseRegistration.objects.filter(
            course__department=department, is_validated=False
        ).count()

    return render(request, 'curriculum/department_dashboard.html', {
        'department': department,
        'programmes': programmes,
        'levels': levels,
        'student_count': student_count,
        'lecturer_count': lecturer_count,
        'course_count': course_count,
        'pending_validations': pending_validations,
    })


# =====================================================================
# Faculty & Department Directory — browsable by everyone, richest for admin
# =====================================================================

@login_required
def faculty_list_view(request):
    faculties = Faculty.objects.annotate(
        department_count=Count('department', distinct=True),
        student_count=Count('department__student', distinct=True),
    ).order_by('name')

    return render(request, 'curriculum/faculty_list.html', {'faculties': faculties})


@login_required
def faculty_detail_view(request, faculty_id):
    faculty = get_object_or_404(Faculty, id=faculty_id)
    departments = Department.objects.filter(faculty=faculty).select_related('hod').annotate(
        student_count=Count('student', distinct=True),
        course_count=Count('course', distinct=True),
    ).order_by('name')

    return render(request, 'curriculum/faculty_detail.html', {
        'faculty': faculty,
        'departments': departments,
    })


@login_required
def department_detail_view(request, department_id):
    department = get_object_or_404(Department.objects.select_related('faculty', 'hod'), id=department_id)
    courses = Course.objects.filter(department=department).select_related('programme', 'level', 'lecturer')
    programme_ids = courses.values_list('programme_id', flat=True).distinct()
    programmes = Programme.objects.filter(id__in=programme_ids).select_related('qualification_type')

    return render(request, 'curriculum/department_detail.html', {
        'department': department,
        'programmes': programmes,
        'student_count': Student.objects.filter(department=department).count(),
        'course_count': courses.count(),
    })


# =====================================================================
# Admin / Registrar: Registration Validation Queue
# =====================================================================

@login_required
def pending_registrations_view(request):
    if not _is_registrar(request.user):
        lecturer = _get_lecturer_or_none(request.user)
        department = Department.objects.filter(hod=lecturer).first() if lecturer else None
        if not department:
            messages.error(request, "Access Denied.")
            return redirect('curriculum:academic-calendar')
        base_qs = CourseRegistration.objects.filter(course__department=department)
    else:
        base_qs = CourseRegistration.objects.all()

    pending = base_qs.filter(is_validated=False).select_related(
        'student', 'course', 'course__department', 'session', 'semester'
    ).order_by('-registered_at')

    session_id = request.GET.get('session')
    semester_id = request.GET.get('semester')
    department_id = request.GET.get('department')

    if session_id:
        pending = pending.filter(session_id=session_id)
    if semester_id:
        pending = pending.filter(semester_id=semester_id)
    if department_id:
        pending = pending.filter(course__department_id=department_id)

    return render(request, 'curriculum/pending_registrations.html', {
        'pending': pending,
        'sessions': Session.objects.all(),
        'semesters': Semester.objects.all(),
        'departments': Department.objects.all(),
    })


@login_required
def validate_registration(request, registration_id):
    if request.method != 'POST':
        return redirect('curriculum:pending-registrations')

    registration = get_object_or_404(CourseRegistration, id=registration_id)

    if not _is_registrar(request.user):
        lecturer = _get_lecturer_or_none(request.user)
        if not _is_hod_of(lecturer, registration.course.department):
            return HttpResponseForbidden("Not permitted.")

    registration.is_validated = True
    registration.validated_by = request.user
    registration.validated_at = timezone.now()
    registration.save(update_fields=['is_validated', 'validated_by', 'validated_at'])

    messages.success(
        request,
        f"Registration validated: {registration.student} — {registration.course.course_code}."
    )
    return redirect('curriculum:pending-registrations')


@login_required
def unvalidate_registration(request, registration_id):
    if request.method != 'POST':
        return redirect('curriculum:pending-registrations')

    registration = get_object_or_404(CourseRegistration, id=registration_id)

    if not _is_registrar(request.user):
        lecturer = _get_lecturer_or_none(request.user)
        if not _is_hod_of(lecturer, registration.course.department):
            return HttpResponseForbidden("Not permitted.")

    registration.is_validated = False
    registration.validated_by = None
    registration.validated_at = None
    registration.save(update_fields=['is_validated', 'validated_by', 'validated_at'])

    messages.warning(request, "Validation revoked — the registration is now pending again.")
    return redirect('curriculum:pending-registrations')


# =====================================================================
# Admin: Session / Semester quick-admin
# =====================================================================

@login_required
def session_admin_view(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Access Denied.")
        return redirect('curriculum:academic-calendar')

    sessions = Session.objects.prefetch_related('terms').order_by('-start_date')

    return render(request, 'curriculum/session_admin.html', {'sessions': sessions})


@login_required
def set_current_session(request, session_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Not permitted.")
    if request.method != 'POST':
        return redirect('curriculum:session-admin')

    session = get_object_or_404(Session, id=session_id)
    Session.objects.exclude(pk=session.pk).filter(is_current=True).update(is_current=False)
    session.is_current = True
    session.save(update_fields=['is_current'])

    messages.success(request, f"{session.name} is now the current session.")
    return redirect('curriculum:session-admin')


@login_required
def set_current_semester(request, semester_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Not permitted.")
    if request.method != 'POST':
        return redirect('curriculum:session-admin')

    semester = get_object_or_404(Semester, id=semester_id)
    Semester.objects.exclude(pk=semester.pk).filter(is_current=True).update(is_current=False)
    semester.is_current = True
    semester.save(update_fields=['is_current'])

    messages.success(request, f"{semester} is now the current semester.")
    return redirect('curriculum:session-admin')
