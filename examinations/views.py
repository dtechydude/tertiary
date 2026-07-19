"""
examinations.views
===================

Two audiences: a student's own timetable (their registered courses'
exam sittings, with live eligibility from the finance app so a student
sees *before* exam day whether they're actually cleared to sit), and
staff's master timetable (filterable by session/semester).

Nothing here decides eligibility — that's finance.ExamEligibilityService,
already built. This just displays it alongside the schedule.
"""

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from curriculum.models import CourseRegistration, Semester, Session

from .models import ExamSchedule


@login_required
def student_exam_timetable_view(request):
    student = getattr(request.user, "student", None)
    if not student:
        return render(request, "errors/403.html", {"message": "Student profile required."})

    current_session = Session.objects.filter(is_current=True).first()
    current_semester = Semester.objects.filter(is_current=True).first()

    if not current_session or not current_semester:
        return render(request, "examinations/student_timetable.html", {
            "rows": [], "student": student,
            "current_session": current_session, "current_semester": current_semester,
        })

    registered_course_ids = CourseRegistration.objects.filter(
        student=student, session=current_session, semester=current_semester
    ).values_list("course_id", flat=True)

    schedules = ExamSchedule.objects.filter(
        course_id__in=registered_course_ids, session=current_session, semester=current_semester
    ).select_related("course", "venue").order_by("exam_date", "start_time")

    from finance.services.exam_eligibility import ExamEligibilityService

    rows = []
    for schedule in schedules:
        result = ExamEligibilityService.check(student, schedule.course, current_session, current_semester)
        rows.append({"schedule": schedule, "is_eligible": result.is_eligible, "reasons": result.reasons})

    return render(request, "examinations/student_timetable.html", {
        "rows": rows,
        "student": student,
        "current_session": current_session,
        "current_semester": current_semester,
    })


@login_required
@permission_required("examinations.view_examschedule", raise_exception=True)
def staff_exam_timetable_view(request):
    current_session = Session.objects.filter(is_current=True).first()
    current_semester = Semester.objects.filter(is_current=True).first()

    session_id = request.GET.get("session") or (str(current_session.id) if current_session else "")
    semester_id = request.GET.get("semester") or (str(current_semester.id) if current_semester else "")

    schedules = ExamSchedule.objects.all().select_related(
        "course", "venue", "session", "semester"
    ).prefetch_related("invigilators__user")

    if session_id:
        schedules = schedules.filter(session_id=session_id)
    if semester_id:
        schedules = schedules.filter(semester_id=semester_id)
    schedules = schedules.order_by("exam_date", "start_time")

    return render(request, "examinations/staff_timetable.html", {
        "schedules": schedules,
        "sessions": Session.objects.all().order_by("-start_date"),
        "semesters": Semester.objects.filter(session_id=session_id) if session_id else Semester.objects.none(),
        "selected_session": session_id,
        "selected_semester": semester_id,
    })
