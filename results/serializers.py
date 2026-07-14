from rest_framework import serializers

from .models import Result, ResultScore


class ResultScoreSerializer(serializers.ModelSerializer):
    component_name = serializers.CharField(source="component.name", read_only=True)

    class Meta:
        model = ResultScore
        fields = ["id", "component", "component_name", "raw_score"]


class ResultSerializer(serializers.ModelSerializer):
    scores = ResultScoreSerializer(many=True, read_only=True)
    course_code = serializers.CharField(source="course.course_code", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    student_matric = serializers.CharField(source="student.matric_number", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Result
        fields = [
            "id", "student", "student_matric", "course", "course_code", "course_title",
            "session", "semester", "credit_unit", "attempt_number",
            "total_score", "grade", "grade_point", "remark",
            "status", "status_display", "is_published", "scores",
            "submitted_at", "published_at",
        ]
        read_only_fields = [
            "total_score", "grade", "grade_point", "remark",
            "status", "is_published", "submitted_at", "published_at",
        ]


class ScoreEntrySerializer(serializers.Serializer):
    """One student's set of component scores, keyed by
    AssessmentComponent id, as submitted from the lecturer score-entry
    screen."""
    student_id = serializers.IntegerField()
    scores = serializers.DictField(child=serializers.DecimalField(max_digits=6, decimal_places=2))


class BulkScoreEntrySerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    session_id = serializers.IntegerField()
    semester_id = serializers.IntegerField()
    entries = ScoreEntrySerializer(many=True)


class ResultWorkflowActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[
        "submit", "approve_hod", "approve_dean", "approve_registrar", "publish", "return",
    ])
    remarks = serializers.CharField(required=False, allow_blank=True)
