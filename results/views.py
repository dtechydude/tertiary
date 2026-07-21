"""
results.views
=============

Views stay thin by design: they resolve "who is asking, for what", and
delegate every calculation or state change to the services layer.
Nothing here computes a grade, a GPA, or decides the next workflow status.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from curriculum.models import Course, CourseAssignment, CourseRegistration, Session, Semester

from .models import Result, Transcript
from .permissions import IsCourseLecturer
from .serializers import BulkScoreEntrySerializer, ResultSerializer, ResultWorkflowActionSerializer
from .services.gpa import GPAService
from .services.grading import GradingService
from .services.graduation import GraduationService
from .services.progress import AcademicProgressService
from .services.transcript import TranscriptService
from .services.documents import build_transcript_pdf
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


# @login_required
# def lecturer_submit_scores(request, course_id):
#     lecturer = getattr(request.user, "lecturer", None)
#     if not lecturer:
#         return render(request, "errors/403.html", {"message": "Lecturer profile required."})

#     course = get_object_or_404(Course, pk=course_id)

#     current_session = Session.objects.filter(is_current=True).first()
#     current_semester = Semester.objects.filter(is_current=True).first()

#     # IMPORTANT: scope to the current session/semester specifically — a
#     # lecturer may have assignments to this same course from past
#     # sessions, and grabbing "any" assignment risked entering scores
#     # against the wrong academic period entirely.
#     assignment = CourseAssignment.objects.filter(
#         lecturer=lecturer, course=course, session=current_session, semester=current_semester
#     ).first()
#     if not assignment:
#         return render(request, "errors/403.html", {
#             "message": "You are not assigned to this course for the current session/semester."
#         })

#     registrations = CourseRegistration.objects.filter(
#         course=course, session=assignment.session, semester=assignment.semester
#     ).select_related("student__user")

#     scheme = GradingService.resolve_scheme(course)
#     components = list(scheme.schemecomponents.select_related("component"))
#     exam_component_ids = {link.component_id for link in components if link.component.is_exam_component}

#     # Pre-fill existing scores and eligibility, so re-opening this page
#     # shows what's already been entered instead of a blank grid.
#     from finance.services.exam_eligibility import ExamEligibilityService

#     existing_results = {
#         r.student_id: r for r in Result.objects.filter(
#             course=course, session=assignment.session, semester=assignment.semester
#         ).prefetch_related("scores")
#     }

#     student_rows = []
#     for reg in registrations:
#         result = existing_results.get(reg.student_id)
#         existing_scores = {s.component_id: s.raw_score for s in result.scores.all()} if result else {}
#         is_exam_eligible = ExamEligibilityService.is_course_exam_eligible(
#             reg.student, course, assignment.session, assignment.semester
#         )
#         # Pre-align each component with this student's existing score (if
#         # any) — Django templates can't do a dynamic dict[key] lookup, so
#         # this pairing has to happen here, not in the template.
#         score_cells = [
#             {"link": link, "value": existing_scores.get(link.component_id, "")}
#             for link in components
#         ]
#         student_rows.append({
#             "student": reg.student,
#             "result": result,
#             "score_cells": score_cells,
#             "is_exam_eligible": is_exam_eligible,
#         })

#     if request.method == "POST":
#         blocked = []
#         with transaction.atomic():
#             for row in student_rows:
#                 student = row["student"]
#                 component_scores = {
#                     link.component_id: request.POST.get(f"score_{link.component_id}_{student.id}", 0) or 0
#                     for link in components
#                 }
#                 result, _ = Result.objects.get_or_create(
#                     student=student, course=course,
#                     session=assignment.session, semester=assignment.semester,
#                     defaults={"scheme": scheme, "credit_unit": course.credit_unit},
#                 )
#                 try:
#                     GradingService.record_scores(result, component_scores, actor=request.user)
#                 except ValidationError as e:
#                     # Don't let one student's outstanding fees/eligibility
#                     # stop the rest of the class from being scored.
#                     blocked.append({"student": student, "reason": str(e)})

#         if blocked:
#             messages.warning(
#                 request,
#                 f"{len(blocked)} student(s) could not be scored for the exam component — see details below."
#             )
#         else:
#             messages.success(request, "Scores saved.")

#         return redirect("results:lecturer_submit_scores", course_id=course_id)

#     return render(request, "results/lecturer/submit_scores.html", {
#         "student_rows": student_rows,
#         "course": course,
#         "assignment": assignment,
#         "components": components,
#         "exam_component_ids": exam_component_ids,
#     })


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
        # Once a result is published, students can already see it — a
        # lecturer must never be able to silently change it from here
        # again. Everything below (POST handling, template rendering)
        # keys off this flag.
        is_published = bool(result and result.is_published)

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
            "is_published": is_published,
        })

    if request.method == "POST":
        blocked = []
        skipped_published = []
        saved_count = 0

        with transaction.atomic():
            for row in student_rows:
                student = row["student"]

                if row["is_published"]:
                    # Hard stop — never touch a published result here,
                    # regardless of what the submitted form data says.
                    # The template disables these inputs too, but that's
                    # only a UX signal; this is the actual enforcement,
                    # since a disabled attribute doesn't stop a directly
                    # crafted POST request.
                    skipped_published.append(student)
                    continue

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
                    saved_count += 1
                except ValidationError as e:
                    # Don't let one student's outstanding fees/eligibility
                    # stop the rest of the class from being scored.
                    blocked.append({"student": student, "reason": str(e)})

        if skipped_published:
            messages.info(
                request,
                f"{len(skipped_published)} student(s) already have a PUBLISHED result and were left "
                f"unchanged — published results can no longer be edited from here. Contact the "
                f"Registrar if a correction is needed."
            )
        if blocked:
            messages.warning(
                request,
                f"{len(blocked)} student(s) could not be scored for the exam component — see details below."
            )
        if saved_count and not blocked:
            messages.success(request, f"Scores saved for {saved_count} student(s).")

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
        submitted, permission_failed, other_failed = 0, 0, 0
        for result in draft_results:
            try:
                ResultWorkflowService.transition(result, "submit", actor=request.user)
                submitted += 1
            except PermissionDenied:
                permission_failed += 1
            except ValidationError:
                other_failed += 1

        if submitted:
            messages.success(request, f"{submitted} result(s) submitted for HOD review.")
        if permission_failed:
            messages.error(
                request,
                f"{permission_failed} result(s) could not be submitted — you're not the assigned "
                f"lecturer for this course/session/semester, and don't hold the 'Can submit results "
                f"for HOD review' permission either. Contact an administrator if this seems wrong."
            )
        if other_failed:
            messages.error(request, f"{other_failed} result(s) could not be submitted — see details and try again.")

        return redirect("results:lecturer_my_courses")

    return render(request, "results/lecturer/confirm_submit.html", {
        "course": course, "draft_count": draft_results.count(),
    })


# ---------------------------------------------------------------------------
# Approval queue — HOD / Dean / Registrar / Publish.
#
# One page adapts to whichever stage(s) the logged-in user has permission
# to act on, rather than four separate near-identical pages. Bulk-select
# + bulk-action, backed by ResultWorkflowService.bulk_transition (already
# built) so the state machine and permission rules live in exactly one
# place — this view never decides what's a valid transition.
# ---------------------------------------------------------------------------

APPROVAL_STAGES = [
    {
        "key": "hod", "status": Result.Status.SUBMITTED, "perm": "results.approve_result_hod",
        "action": "approve_hod", "label": "HOD Review", "verb": "Approve (HOD)",
    },
    {
        "key": "dean", "status": Result.Status.HOD_APPROVED, "perm": "results.approve_result_dean",
        "action": "approve_dean", "label": "Dean Review", "verb": "Approve (Dean)",
    },
    {
        "key": "registrar", "status": Result.Status.DEAN_APPROVED, "perm": "results.approve_result_registrar",
        "action": "approve_registrar", "label": "Registrar Review", "verb": "Approve (Registrar)",
    },
    {
        "key": "publish", "status": Result.Status.REGISTRAR_APPROVED, "perm": "results.publish_result",
        "action": "publish", "label": "Ready to Publish", "verb": "Publish",
    },
]


@login_required
def approval_queue_view(request):
    accessible_stages = [s for s in APPROVAL_STAGES if request.user.has_perm(s["perm"])]
    if not accessible_stages:
        return render(request, "errors/403.html", {
            "message": "You don't hold any result-approval permission (HOD/Dean/Registrar)."
        })

    active_key = request.GET.get("stage", accessible_stages[0]["key"])
    active_stage = next((s for s in accessible_stages if s["key"] == active_key), accessible_stages[0])

    results_qs = Result.objects.filter(status=active_stage["status"]).select_related(
        "student__user", "course", "session", "semester"
    ).order_by("course__course_code", "student__user__last_name")

    course_id = request.GET.get("course") or ""
    if course_id:
        results_qs = results_qs.filter(course_id=course_id)

    courses_in_queue = Course.objects.filter(
        results__status=active_stage["status"]
    ).distinct().order_by("course_code")

    return render(request, "results/approval_queue.html", {
        "accessible_stages": accessible_stages,
        "active_stage": active_stage,
        "results": results_qs,
        "courses_in_queue": courses_in_queue,
        "selected_course": course_id,
    })


@login_required
@require_POST
def approval_action_view(request):
    action = request.POST.get("action")
    stage_key = request.POST.get("stage", "")
    result_ids = request.POST.getlist("result_ids")
    remarks = request.POST.get("remarks", "")

    redirect_url = f"{reverse('results:approval_queue')}?stage={stage_key}"

    if not result_ids:
        messages.error(request, "No results were selected.")
        return redirect(redirect_url)

    results_qs = Result.objects.filter(id__in=result_ids)
    try:
        updated = ResultWorkflowService.bulk_transition(results_qs, action, actor=request.user, remarks=remarks)
        verb = "returned for correction" if action == "return" else "updated"
        messages.success(request, f"{len(updated)} result(s) {verb}.")
    except PermissionDenied as e:
        messages.error(request, str(e))
    except ValidationError as e:
        messages.error(request, str(e))

    return redirect(redirect_url)


# ---------------------------------------------------------------------------
# Transcript — full academic statement + deliberate, auditable generation.
# ---------------------------------------------------------------------------

@login_required
def my_transcript_view(request):
    """Student's own transcript preview, with a button to generate an
    unofficial (watermarked) copy for their own use."""
    student = getattr(request.user, "student", None)
    if not student:
        return render(request, "errors/403.html", {"message": "Student profile required."})

    statement = TranscriptService.build_statement(student)
    latest_transcript = Transcript.objects.filter(student=student).first()

    return render(request, "results/student/transcript.html", {
        "student": student,
        "statement": statement,
        "latest_transcript": latest_transcript,
        "is_staff_view": False,
    })


@login_required
@require_POST
def generate_my_transcript_view(request):
    """Student self-service — always UNOFFICIAL. An official transcript
    requires deliberate registrar action (staff_generate_transcript_view)."""
    student = getattr(request.user, "student", None)
    if not student:
        return render(request, "errors/403.html", {"message": "Student profile required."})

    transcript = TranscriptService.generate_transcript(student, generated_by=request.user, is_official=False)
    return redirect("results:transcript_pdf", transcript_id=transcript.id)


@login_required
@permission_required("results.generate_official_transcript", raise_exception=True)
def staff_generate_transcript_view(request, matric_number):
    from students.models import Student
    student = get_object_or_404(Student, matric_number=matric_number)

    if request.method == "POST":
        transcript = TranscriptService.generate_transcript(student, generated_by=request.user, is_official=True)
        messages.success(request, f"Official transcript generated for {student.get_full_name()}.")
        return redirect("results:transcript_pdf", transcript_id=transcript.id)

    statement = TranscriptService.build_statement(student)
    return render(request, "results/student/transcript.html", {
        "student": student,
        "statement": statement,
        "latest_transcript": Transcript.objects.filter(student=student).first(),
        "is_staff_view": True,
    })


@login_required
def transcript_pdf_view(request, transcript_id):
    transcript = get_object_or_404(Transcript.objects.select_related("student__user"), pk=transcript_id)

    student = getattr(request.user, "student", None)
    is_owner = student is not None and student.id == transcript.student_id
    if not is_owner and not request.user.has_perm("results.generate_official_transcript"):
        return render(request, "errors/403.html", {"message": "Not permitted to view this transcript."})

    statement = TranscriptService.build_statement(transcript.student)
    pdf_bytes = build_transcript_pdf(transcript.student, transcript, statement)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="transcript_{transcript.student.matric_number}.pdf"'
    return response



# =============================================================================
# NEW VIEW — append to the end of results/views.py.
# Nothing existing in that file changes: staff_generate_transcript_view and
# transcript_pdf_view are reused exactly as they already are, unmodified.
#
# Requires these imports already present (or add if missing) at the top of
# results/views.py:
#   from students.models import Student
#   from curriculum.models import Department, Session, Semester
#   from .models import Result, Transcript
# =============================================================================

@login_required
@permission_required("results.generate_official_transcript", raise_exception=True)
def staff_transcript_list_view(request):
    """
    Staff-facing list for locating a student's transcript, filterable by
    department / session ("year") / semester.

    Transcript itself has no session/semester field — it's a deliberate
    whole-history document (see its docstring: "compiles a student's full
    academic statement", not a per-term one), so there is nothing on
    Transcript to filter by session/semester in the first place. What
    this filters instead is the student population: which students have
    at least one PUBLISHED Result in the selected session/semester,
    optionally narrowed by department. That's the well-defined match for
    "department/semester/year" that actually exists in the schema, rather
    than inventing fields Transcript doesn't have.

    For each matching student, this surfaces their most recently
    generated Transcript (if any) so staff can jump straight to
    View/Generate (staff_generate_transcript_view, unchanged) or Print
    (transcript_pdf_view, unchanged) without re-deriving any transcript
    logic here.
    """
    from students.models import Student
    from curriculum.models import Department, Session, Semester

    department_id = request.GET.get("department") or None
    session_id = request.GET.get("session") or None
    semester_id = request.GET.get("semester") or None

    result_qs = Result.objects.filter(is_published=True)
    if session_id:
        result_qs = result_qs.filter(session_id=session_id)
    if semester_id:
        result_qs = result_qs.filter(semester_id=semester_id)
    student_ids = result_qs.values_list("student_id", flat=True).distinct()

    students = Student.objects.filter(id__in=student_ids).select_related(
        "department", "level", "programme"
    )
    if department_id:
        students = students.filter(department_id=department_id)
    students = students.order_by("department__name", "matric_number")

    # Latest Transcript per student, in one query rather than N — keep the
    # first (most recent, since Transcript.Meta.ordering is -generated_at)
    # row seen for each student_id.
    latest_transcripts = {}
    for t in Transcript.objects.filter(student_id__in=list(student_ids)).select_related("student"):
        latest_transcripts.setdefault(t.student_id, t)

    # Pre-pair each student with their transcript (if any) here, rather
    # than doing a dict lookup by variable key in the template — Django
    # templates can't index a dict by a variable key without a custom
    # filter, so this keeps the template plain.
    student_rows = [
        {"student": student, "transcript": latest_transcripts.get(student.id)}
        for student in students
    ]

    context = {
        "student_rows": student_rows,
        "departments": Department.objects.all().order_by("name"),
        "sessions": Session.objects.all().order_by("-id"),
        "semesters": Semester.objects.all(),
        "selected_department_id": department_id,
        "selected_session_id": session_id,
        "selected_semester_id": semester_id,
    }
    return render(request, "results/staff/transcript_list.html", context)


"""
Views for the result approval workflow (/results/approvals/...).

Merge these into your existing results/views.py (or keep this as
results/views_approvals.py and add `from .views_approvals import *`
to views.py — either works, just pick one so urls.py has one place to
import from).

Access model:
  * The whole approvals section requires request.user.is_staff (or
    is_superuser, which implies is_staff-level access via the decorator
    below) — this is the "who can even open the page" gate.
  * Within the page, which ACTIONS a given user can take is governed
    entirely by the granular Result permissions (submit_result,
    approve_result_hod, ...) via has_perm — never by role name, never
    hardcoded. Grant those permissions to the relevant Groups (HOD,
    Dean, Registrar, ...) in Django admin.
  * Every transition is executed through ResultWorkflowService (via
    services/approvals.py), exactly like ResultAdmin's actions —
    so permission checks and ResultAuditLog entries are identical
    regardless of whether the change came from /admin/ or this UI.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ApprovalFilterForm, BulkActionForm, ReturnReasonForm
from .models import Result
from .services.approvals import (
    ACTION_LABELS,
    ACTION_PERMISSIONS,
    get_available_actions,
    bulk_transition,
    apply_transition,
)


def staff_required(view_func):
    """
    Gate for the approvals section itself. Deliberately separate from
    the per-action permission checks below — is_staff just says "you're
    allowed into the approvals workspace", it says nothing about which
    transitions you're allowed to perform once you're in it.
    """
    return login_required(
        user_passes_test(lambda u: u.is_active and u.is_staff)(view_func)
    )


def _base_queryset():
    return (
        Result.objects.select_related(
            "student", "student__user", "course", "session", "semester", "submitted_by",
        )
        .order_by("-session", "semester", "course__course_code", "student__matric_number")
    )


def _apply_filters(qs, form: ApprovalFilterForm, request):
    if form.is_valid():
        status = form.cleaned_data.get("status")
        session = form.cleaned_data.get("session")
        semester = form.cleaned_data.get("semester")
        course = form.cleaned_data.get("course")
        q = form.cleaned_data.get("q")

        if status:
            qs = qs.filter(status=status)
        elif "status" not in request.GET:
            # Default view: hide drafts (a lecturer's unsubmitted working
            # copy) unless someone explicitly asks to see them via the
            # Draft tab/filter.
            qs = qs.exclude(status=Result.Status.DRAFT)

        if session:
            qs = qs.filter(session=session)
        if semester:
            qs = qs.filter(semester=semester)
        if course:
            qs = qs.filter(course=course)
        if q:
            qs = qs.filter(
                Q(student__matric_number__icontains=q)
                | Q(student__user__first_name__icontains=q)
                | Q(student__user__last_name__icontains=q)
                | Q(course__course_code__icontains=q)
                | Q(course__title__icontains=q)
            )
    return qs


@staff_required
def approval_queue(request):
    """
    Main approval workspace: filterable, paginated table of results with
    a status tab strip and a permission-scoped bulk-action toolbar.
    """
    form = ApprovalFilterForm(request.GET or None)
    qs = _apply_filters(_base_queryset(), form, request)

    # Counts per status for the tab strip — one aggregate query, not one
    # query per tab.
    status_counts = {row["status"]: row["count"] for row in Result.objects.values("status").annotate(count=Count("id"))}

    def _tab_url(status_value):
        qs = request.GET.copy()
        qs.pop("page", None)
        if status_value:
            qs["status"] = status_value
        else:
            qs.pop("status", None)
        encoded = qs.urlencode()
        base = reverse("results:approval_queue")
        return f"{base}?{encoded}" if encoded else base

    non_draft_count = sum(count for status, count in status_counts.items() if status != Result.Status.DRAFT)
    status_tabs = [
        {
            "value": "",
            "label": "All (excl. Drafts)",
            "count": non_draft_count,
            "active": "status" not in request.GET,
            "url": _tab_url(""),
        }
    ]
    status_tabs += [
        {
            "value": value,
            "label": label,
            "count": status_counts.get(value, 0),
            "active": request.GET.get("status") == value,
            "url": _tab_url(value),
        }
        for value, label in Result.Status.choices
    ]

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    rows = [
        {"result": result, "actions": get_available_actions(result, request.user)}
        for result in page_obj.object_list
    ]

    # Only offer bulk actions the user actually holds permission for
    # anywhere — the per-row check still applies when the action runs.
    available_bulk_actions = [
        (key, label) for key, label in ACTION_LABELS.items() if request.user.has_perm(ACTION_PERMISSIONS[key])
    ]

    # Preserve current filters across pagination / bulk-action redirects.
    querystring = request.GET.copy()
    querystring.pop("page", None)

    context = {
        "filter_form": form,
        "status_tabs": status_tabs,
        "page_obj": page_obj,
        "rows": rows,
        "available_bulk_actions": available_bulk_actions,
        "querystring": querystring.urlencode(),
    }
    return render(request, "results/approval_queue.html", context)


@staff_required
@require_POST
def approval_bulk_action(request):
    """
    Applies one action to every checked result on the queue page, then
    redirects back preserving the current filters/page.
    """
    result_ids = request.POST.getlist("result_ids")
    form = BulkActionForm(
        {
            "action": request.POST.get("action"),
            "result_ids": result_ids,
            "note": request.POST.get("note", ""),
        }
    )
    redirect_qs = request.POST.get("querystring", "")
    redirect_url = reverse("results:approval_queue")
    if redirect_qs:
        redirect_url = f"{redirect_url}?{redirect_qs}"

    if not result_ids:
        messages.warning(request, "Select at least one result before choosing a bulk action.")
        return redirect(redirect_url)

    if not form.is_valid():
        for error_list in form.errors.values():
            for error in error_list:
                messages.error(request, error)
        return redirect(redirect_url)

    action = form.cleaned_data["action"]
    if not request.user.has_perm(ACTION_PERMISSIONS[action]):
        messages.error(request, f"You don't have permission to {ACTION_LABELS[action].lower()}.")
        return redirect(redirect_url)

    queryset = form.cleaned_data["result_ids"]
    succeeded, failed = bulk_transition(queryset, action, actor=request.user, note=form.cleaned_data.get("note", ""))

    if succeeded:
        messages.success(request, f"{len(succeeded)} result(s) updated: {ACTION_LABELS[action]}.")
    if failed:
        messages.error(
            request,
            f"{len(failed)} result(s) could not be updated — either not a valid transition from their "
            f"current status, or a rule in the workflow blocked it.",
        )

    return redirect(redirect_url)


@staff_required
def approval_detail(request, pk):
    """
    Single-result view: full score breakdown, workflow position, audit
    trail, and the same permission-scoped actions as the queue — useful
    when an approver wants to actually look at a result before acting on
    it rather than approving blind from the table.
    """
    result = get_object_or_404(
        Result.objects.select_related(
            "student", "student__user", "course", "session", "semester", "submitted_by", "scheme",
        ),
        pk=pk,
    )

    if request.method == "POST":
        action = request.POST.get("action")
        note = request.POST.get("note", "")

        if action not in ACTION_PERMISSIONS:
            messages.error(request, "Unknown action.")
        elif not request.user.has_perm(ACTION_PERMISSIONS[action]):
            messages.error(request, f"You don't have permission to {ACTION_LABELS[action].lower()}.")
        elif action == "return" and not note:
            messages.error(request, "Please add a note explaining what needs correcting.")
        else:
            try:
                apply_transition(result, action, actor=request.user, note=note)
                messages.success(request, f"Done: {ACTION_LABELS[action]}.")
            except Exception as exc:  # PermissionDenied / ValidationError from the service
                messages.error(request, str(exc) or "That transition isn't valid right now.")

        return redirect("results:approval_detail", pk=result.pk)

    scores = list(result.scores.select_related("component").all())
    # ResultScore doesn't carry its own max — that lives on the
    # GradingSchemeComponent link for this result's scheme snapshot
    # (see ResultScore.clean()). Attach it here for display only; this
    # doesn't touch the database.
    try:
        from .models import GradingSchemeComponent  # adjust import path if this lives elsewhere
        max_by_component = {
            link.component_id: link.max_raw_score
            for link in GradingSchemeComponent.objects.filter(scheme=result.scheme)
        }
        for score in scores:
            score.max_raw_score = max_by_component.get(score.component_id)
    except ImportError:
        for score in scores:
            score.max_raw_score = None
    # Related name assumed as `audit_logs` — adjust if ResultAuditLog
    # uses a different related_name on its FK to Result. This is purely
    # a display convenience; nothing above depends on it existing.
    audit_logs = getattr(result, "audit_logs", None)
    audit_logs = audit_logs.all().order_by("-created_at") if audit_logs is not None else []

    workflow_stages = [
        Result.Status.SUBMITTED,
        Result.Status.HOD_APPROVED,
        Result.Status.DEAN_APPROVED,
        Result.Status.REGISTRAR_APPROVED,
        Result.Status.PUBLISHED,
    ]
    current_index = workflow_stages.index(result.status) if result.status in workflow_stages else -1
    stepper = [
        {"label": Result.Status(stage).label, "done": i <= current_index, "current": i == current_index}
        for i, stage in enumerate(workflow_stages)
    ]

    available_actions = [
        {"key": action, "label": ACTION_LABELS[action]}
        for action in get_available_actions(result, request.user)
    ]

    context = {
        "result": result,
        "scores": scores,
        "audit_logs": audit_logs,
        "stepper": stepper,
        "is_returned": result.status == Result.Status.RETURNED,
        "available_actions": available_actions,
        "return_form": ReturnReasonForm(),
    }
    return render(request, "results/approval_detail.html", context)