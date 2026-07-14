"""
results.views
=============

Views stay thin by design: they resolve "who is asking, for what", and
delegate every calculation or state change to the services layer.
Nothing here computes a grade, a GPA, or decides the next workflow status.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404

from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from curriculum.models import Course, CourseAssignment, CourseRegistration

from .models import Result
from .permissions import IsCourseLecturer
from .serializers import BulkScoreEntrySerializer, ResultSerializer, ResultWorkflowActionSerializer
from .services.gpa import GPAService
from .services.grading import GradingService
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
        processed, skipped = [], []

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
                return Response(
                    {"error": str(e), "student_id": entry["student_id"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response({"processed": processed, "skipped_unregistered": skipped})


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


# ---------------------------------------------------------------------------
# Template views — thin; all logic delegates to services
# ---------------------------------------------------------------------------

def student_dashboard(request):
    student = getattr(request.user, "student", None)
    if not student:
        return render(request, "errors/403.html", {"message": "Student profile required."})

    results = Result.objects.filter(student=student, is_published=True).select_related("course")
    context = {
        "results": results,
        "cgpa": GPAService.calculate_cgpa(student),
        "total_courses": results.count(),
        "outstanding_courses": results.filter(grade="F").count(),
    }
    return render(request, "results/student/dashboard.html", context)


def lecturer_submit_scores(request, course_id):
    lecturer = getattr(request.user, "lecturer", None)
    if not lecturer:
        return render(request, "errors/403.html", {"message": "Lecturer profile required."})

    course = get_object_or_404(Course, pk=course_id)
    assignment = CourseAssignment.objects.filter(lecturer=lecturer, course=course).first()
    if not assignment:
        return render(request, "errors/403.html", {"message": "You are not assigned to this course."})

    registrations = CourseRegistration.objects.filter(
        course=course, session=assignment.session, semester=assignment.semester
    ).select_related("student")

    scheme = GradingService.resolve_scheme(course)
    components = list(scheme.schemecomponents.select_related("component"))

    if request.method == "POST":
        with transaction.atomic():
            for reg in registrations:
                component_scores = {
                    link.component_id: request.POST.get(f"score_{link.component_id}_{reg.student.id}", 0) or 0
                    for link in components
                }
                result, _ = Result.objects.get_or_create(
                    student=reg.student, course=course,
                    session=assignment.session, semester=assignment.semester,
                    defaults={"scheme": scheme, "credit_unit": course.credit_unit},
                )
                GradingService.record_scores(result, component_scores, actor=request.user)

        return redirect("results:lecturer_submit_scores", course_id=course_id)

    return render(request, "results/lecturer/submit_scores.html", {
        "registrations": registrations,
        "course": course,
        "assignment": assignment,
        "components": components,
    })
