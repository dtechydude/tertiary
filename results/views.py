"""
results.views
=============

Views stay thin by design: they resolve "who is asking, for what", and
delegate every calculation or state change to the services layer.
Nothing here computes a grade, a GPA, or decides the next workflow status.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404

from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from curriculum.models import Course, CourseAssignment, CourseRegistration, Session, Semester

from .models import Result
from .permissions import IsCourseLecturer
from .serializers import BulkScoreEntrySerializer, ResultSerializer, ResultWorkflowActionSerializer
from .services.gpa import GPAService
from .services.grading import GradingService
from .services.graduation import GraduationService
from .services.progress import AcademicProgressService
from .services.workflow import ResultWorkflowService


class DefaultResultPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


# ---------------------------------------------------------------------------
# API (DRF) — versioned under /api/v1/
# ---------------------------------------------------------------------------

class LecturerCourseResultListView(generics.ListAPIView):
    """Results for one course/session/semester the requesting lecturer is
    assigned to — backs the score-entry grid."""
    serializer_class = ResultSerializer
    permission_classes = [IsAuthenticated, IsCourseLecturer]
    pagination_class = DefaultResultPagination

    def get_queryset(self):
        course = get_object_or_404(Course, pk=self.kwargs["course_id"])
        assignment = get_object_or_404(
            CourseAssignment, lecturer=self.request.user.lecturer, course=course
        )
        return Result.objects.filter(
            course=course, session=assignment.session, semester=assignment.semester
        ).select_related("student", "course").prefetch_related("scores__component")


class BulkScoreEntryView(APIView):
    """
    Lecturer submits/updates component scores for many students in one
    course at once. Confirms registration + assignment before creating a
    Result row; GradingService owns every calculation.
    """
    permission_classes = [IsAuthenticated, IsCourseLecturer]

    @transaction.atomic
    def post(self, request):
        serializer = BulkScoreEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        course = get_object_or_404(Course, pk=data["course_id"])
        assignment = CourseAssignment.objects.filter(
            lecturer=request.user.lecturer, course=course,
            session_id=data["session_id"], semester_id=data["semester_id"],
        ).first()
        if not assignment:
            return Response(
                {"error": "You are not assigned to this course for the given session/semester."},
                status=status.HTTP_403_FORBIDDEN,
            )

        scheme = GradingService.resolve_scheme(course)
        processed, skipped, blocked = [], [], []

        for entry in data["entries"]:
            is_registered = CourseRegistration.objects.filter(
                student_id=entry["student_id"], course=course,
                session_id=data["session_id"], semester_id=data["semester_id"],
            ).exists()
            if not is_registered:
                skipped.append(entry["student_id"])
                continue

            result, _ = Result.objects.get_or_create(
                student_id=entry["student_id"], course=course,
                session_id=data["session_id"], semester_id=data["semester_id"],
                defaults={"scheme": scheme, "credit_unit": course.credit_unit},
            )
            try:
                GradingService.record_scores(result, entry["scores"], actor=request.user)
                processed.append(result.id)
            except ValidationError as e:
                # One student's outstanding fees (or any other validation
                # issue) shouldn't block the rest of the class from being
                # scored — record it and keep going.
                blocked.append({"student_id": entry["student_id"], "reason": str(e)})

        return Response({"processed": processed, "skipped_unregistered": skipped, "blocked": blocked})


class ResultWorkflowActionView(APIView):
    """
    Single endpoint for every approval-chain action (submit, approve_hod,
    approve_dean, approve_registrar, publish, return). Allowed transitions
    and required permissions are resolved entirely inside
    ResultWorkflowService — this view never hardcodes a role name.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, result_id):
        result = get_object_or_404(Result, pk=result_id)
        serializer = ResultWorkflowActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ResultWorkflowService.transition(
                result,
                serializer.validated_data["action"],
                actor=request.user,
                remarks=serializer.validated_data.get("remarks", ""),
            )
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ResultSerializer(result).data)


class StudentResultListView(generics.ListAPIView):
    """Students only ever see PUBLISHED results — enforced at the
    queryset level, not left for a template to filter."""
    serializer_class = ResultSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DefaultResultPagination

    def get_queryset(self):
        student = getattr(self.request.user, "student", None)
        if not student:
            return Result.objects.none()
        return Result.objects.filter(
            student=student, is_published=True
        ).select_related("course").prefetch_related("scores__component")


class StudentGPASummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = getattr(request.user, "student", None)
        if not student:
            return Response({"error": "User is not a student"}, status=status.HTTP_403_FORBIDDEN)
        return Response({"cgpa": str(GPAService.calculate_cgpa(student))})


class StudentGraduationEvaluationView(APIView):
    """
    Registrar-facing (also viewable by the student themself): is this
    student eligible to graduate, and under what classification?
    Delegates entirely to GraduationService — this view makes no
    decisions about thresholds or band names.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        from students.models import Student
        student = get_object_or_404(Student, pk=student_id)

        is_owner = getattr(request.user, "student", None) and request.user.student.id == student.id
        if not is_owner and not request.user.has_perm("results.publish_result"):
            return Response(
                {"error": "You do not have permission to view this student's graduation evaluation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            evaluation = GraduationService.evaluate(student)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "cgpa": str(evaluation.cgpa),
            "total_credit_units": evaluation.total_credit_units,
            "minimum_cgpa_required": str(evaluation.minimum_cgpa_required),
            "minimum_credit_units_required": evaluation.minimum_credit_units_required,
            "meets_cgpa_requirement": evaluation.meets_cgpa_requirement,
            "meets_credit_requirement": evaluation.meets_credit_requirement,
            "is_eligible_to_graduate": evaluation.is_eligible_to_graduate,
            "classification": evaluation.classification,
        })


# ---------------------------------------------------------------------------
# Template views — thin; all logic delegates to services
# ---------------------------------------------------------------------------

def _build_progress_context(request, student):
    """Shared by academic_progress_view (student's own) and
    staff_student_progress_view (any student, staff-only) — one
    implementation, two entry points."""
    filter_session_id = request.GET.get("session") or None
    filter_semester_id = request.GET.get("semester") or None

    filter_session = Session.objects.filter(pk=filter_session_id).first() if filter_session_id else None
    filter_semester = Semester.objects.filter(pk=filter_semester_id).first() if filter_semester_id else None

    progress = AcademicProgressService.build_progress(
        student, filter_session=filter_session, filter_semester=filter_semester
    )

    try:
        evaluation = GraduationService.evaluate(student)
    except ValidationError:
        evaluation = None

    return {
        "student": student,
        "progress": progress,
        "cgpa": GPAService.calculate_cgpa(student),
        "evaluation": evaluation,
        "sessions": Session.objects.all().order_by("-start_date"),
        "semesters": Semester.objects.filter(session=filter_session) if filter_session else Semester.objects.none(),
        "selected_session": filter_session_id or "",
        "selected_semester": filter_semester_id or "",
    }


@login_required
def academic_progress_view(request):
    """A student viewing their own progress toward graduation."""
    student = getattr(request.user, "student", None)
    if not student:
        return render(request, "errors/403.html", {"message": "Student profile required."})

    context = _build_progress_context(request, student)
    return render(request, "results/student/academic_progress.html", context)


@login_required
def staff_student_progress_view(request, matric_number):
    """Staff looking up any student's progress toward graduation."""
    if not (request.user.is_staff or request.user.is_superuser):
        return render(request, "errors/403.html", {"message": "Staff access required."})

    from students.models import Student
    student = get_object_or_404(Student, matric_number=matric_number)

    context = _build_progress_context(request, student)
    context["is_staff_view"] = True
    return render(request, "results/student/academic_progress.html", context)


@login_required
def lecturer_my_courses_view(request):
    """A lecturer's own course list for the current session/semester,
    with at-a-glance status counts — the entry point into score entry."""
    lecturer = getattr(request.user, "lecturer", None)
    if not lecturer:
        return render(request, "errors/403.html", {"message": "Lecturer profile required."})

    current_session = Session.objects.filter(is_current=True).first()
    current_semester = Semester.objects.filter(is_current=True).first()

    assignments = CourseAssignment.objects.filter(
        lecturer=lecturer, session=current_session, semester=current_semester
    ).select_related("course") if current_session and current_semester else CourseAssignment.objects.none()

    rows = []
    for assignment in assignments:
        results_qs = Result.objects.filter(
            course=assignment.course, session=current_session, semester=current_semester
        )
        registered_count = CourseRegistration.objects.filter(
            course=assignment.course, session=current_session, semester=current_semester
        ).count()
        rows.append({
            "course": assignment.course,
            "registered_count": registered_count,
            "scored_count": results_qs.exclude(total_score=0).count(),
            "submitted_count": results_qs.exclude(status=Result.Status.DRAFT).count(),
            "published_count": results_qs.filter(is_published=True).count(),
        })

    return render(request, "results/lecturer/my_courses.html", {
        "rows": rows,
        "current_session": current_session,
        "current_semester": current_semester,
    })


@login_required
def lecturer_submit_scores(request, course_id):
    lecturer = getattr(request.user, "lecturer", None)
    if not lecturer:
        return render(request, "errors/403.html", {"message": "Lecturer profile required."})

    course = get_object_or_404(Course, pk=course_id)

    current_session = Session.objects.filter(is_current=True).first()
    current_semester = Semester.objects.filter(is_current=True).first()

    # IMPORTANT: scope to the current session/semester specifically — a
    # lecturer may have assignments to this same course from past
    # sessions, and grabbing "any" assignment risked entering scores
    # against the wrong academic period entirely.
    assignment = CourseAssignment.objects.filter(
        lecturer=lecturer, course=course, session=current_session, semester=current_semester
    ).first()
    if not assignment:
        return render(request, "errors/403.html", {
            "message": "You are not assigned to this course for the current session/semester."
        })

    registrations = CourseRegistration.objects.filter(
        course=course, session=assignment.session, semester=assignment.semester
    ).select_related("student__user")

    scheme = GradingService.resolve_scheme(course)
    components = list(scheme.schemecomponents.select_related("component"))
    exam_component_ids = {link.component_id for link in components if link.component.is_exam_component}

    # Pre-fill existing scores and eligibility, so re-opening this page
    # shows what's already been entered instead of a blank grid.
    from finance.services.exam_eligibility import ExamEligibilityService

    existing_results = {
        r.student_id: r for r in Result.objects.filter(
            course=course, session=assignment.session, semester=assignment.semester
        ).prefetch_related("scores")
    }

    student_rows = []
    for reg in registrations:
        result = existing_results.get(reg.student_id)
        existing_scores = {s.component_id: s.raw_score for s in result.scores.all()} if result else {}
        is_exam_eligible = ExamEligibilityService.is_course_exam_eligible(
            reg.student, course, assignment.session, assignment.semester
        )
        # Pre-align each component with this student's existing score (if
        # any) — Django templates can't do a dynamic dict[key] lookup, so
        # this pairing has to happen here, not in the template.
        score_cells = [
            {"link": link, "value": existing_scores.get(link.component_id, "")}
            for link in components
        ]
        student_rows.append({
            "student": reg.student,
            "result": result,
            "score_cells": score_cells,
            "is_exam_eligible": is_exam_eligible,
        })

    if request.method == "POST":
        blocked = []
        with transaction.atomic():
            for row in student_rows:
                student = row["student"]
                component_scores = {
                    link.component_id: request.POST.get(f"score_{link.component_id}_{student.id}", 0) or 0
                    for link in components
                }
                result, _ = Result.objects.get_or_create(
                    student=student, course=course,
                    session=assignment.session, semester=assignment.semester,
                    defaults={"scheme": scheme, "credit_unit": course.credit_unit},
                )
                try:
                    GradingService.record_scores(result, component_scores, actor=request.user)
                except ValidationError as e:
                    # Don't let one student's outstanding fees/eligibility
                    # stop the rest of the class from being scored.
                    blocked.append({"student": student, "reason": str(e)})

        if blocked:
            messages.warning(
                request,
                f"{len(blocked)} student(s) could not be scored for the exam component — see details below."
            )
        else:
            messages.success(request, "Scores saved.")

        return redirect("results:lecturer_submit_scores", course_id=course_id)

    return render(request, "results/lecturer/submit_scores.html", {
        "student_rows": student_rows,
        "course": course,
        "assignment": assignment,
        "components": components,
        "exam_component_ids": exam_component_ids,
    })


@login_required
def submit_results_for_review_view(request, course_id):
    """Bulk-submits every DRAFT result for this course/session/semester
    to the HOD for review — the lecturer's half of the approval chain
    (submit -> HOD -> Dean -> Registrar -> Published)."""
    lecturer = getattr(request.user, "lecturer", None)
    if not lecturer:
        return render(request, "errors/403.html", {"message": "Lecturer profile required."})

    course = get_object_or_404(Course, pk=course_id)
    current_session = Session.objects.filter(is_current=True).first()
    current_semester = Semester.objects.filter(is_current=True).first()

    assignment = CourseAssignment.objects.filter(
        lecturer=lecturer, course=course, session=current_session, semester=current_semester
    ).first()
    if not assignment:
        return render(request, "errors/403.html", {"message": "You are not assigned to this course."})

    draft_results = Result.objects.filter(
        course=course, session=current_session, semester=current_semester, status=Result.Status.DRAFT
    )

    if request.method == "POST":
        submitted, failed = 0, 0
        for result in draft_results:
            try:
                ResultWorkflowService.transition(result, "submit", actor=request.user)
                submitted += 1
            except (ValidationError, PermissionDenied):
                failed += 1

        if submitted:
            messages.success(request, f"{submitted} result(s) submitted for HOD review.")
        if failed:
            messages.error(request, f"{failed} result(s) could not be submitted — check your permissions.")

        return redirect("results:lecturer_my_courses")

    return render(request, "results/lecturer/confirm_submit.html", {
        "course": course, "draft_count": draft_results.count(),
    })
