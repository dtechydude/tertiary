from results.models import GradeScale, GradingSetting

class GradingService:

    @staticmethod
    def calculate_total(tma, exam, setting):
        tma_part = (tma / 100) * setting.tma_weight
        exam_part = (exam / 100) * setting.exam_weight
        return tma_part + exam_part

    @staticmethod
    def get_grade(program, total_score):
        scales = GradeScale.objects.filter(program=program)

        for scale in scales:
            if scale.min_score <= total_score <= scale.max_score:
                return scale

        return None

    @staticmethod
    def compute_result(result):
        setting = GradingSetting.objects.get(program=result.student.program)

        total = GradingService.calculate_total(
            result.tma_score,
            result.exam_score,
            setting
        )

        grade_scale = GradingService.get_grade(
            result.student.program,
            total
        )

        result.total_score = total

        if grade_scale:
            result.grade = grade_scale.grade
            result.grade_point = grade_scale.grade_point
            result.remark = grade_scale.remark

        result.save()
        return result