from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from curriculum.models import  CourseAssignment
from .models import Result
from results.services.grading import GradingService

from results.models import Result
from results.services.gpa import GPAService



class ResultEntryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        lecturer = request.user.lecturer

        course_id = request.data.get("course")
        scores = request.data.get("scores")

        assignment = CourseAssignment.objects.filter(
            lecturer=lecturer,
            course_id=course_id
        ).first()

        if not assignment:
            return Response({"error": "Unauthorized"}, status=403)

        for item in scores:
            result, _ = Result.objects.get_or_create(
                student_id=item['student_id'],
                course_id=course_id,
                session=assignment.session,
                semester=assignment.semester,
                defaults={
                    'credit_unit': assignment.course.credit_unit
                }
            )

            result.tma_score = item['tma']
            result.exam_score = item['exam']

            GradingService.compute_result(result)

        return Response({"message": "Scores submitted"})
    


class StudentResultView(APIView):

    def get(self, request):
        student = request.user.student

        results = Result.objects.filter(student=student)

        data = []

        for r in results:
            data.append({
                "course": r.course.code,
                "title": r.course.title,
                "tma": r.tma_score,
                "exam": r.exam_score,
                "total": r.total_score,
                "grade": r.grade,
                "remark": r.remark
            })

        cgpa = GPAService.calculate_cgpa(student)

        return Response({
            "results": data,
            "cgpa": cgpa
        })
    

# testing
class TestView(APIView):
    def get(self, request):
        return Response({"message": "DRF is working!"})