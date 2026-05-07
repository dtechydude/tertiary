from results.models import Result


class GPAService:

    @staticmethod
    def calculate_gpa(student, session, semester):
        results = Result.objects.filter(
            student=student,
            session=session,
            semester=semester
        )

        total_points = 0
        total_units = 0

        for r in results:
            total_points += r.grade_point * r.credit_unit
            total_units += r.credit_unit

        if total_units == 0:
            return 0

        return round(total_points / total_units, 2)


    @staticmethod
    def calculate_cgpa(student):
        results = Result.objects.filter(student=student)

        total_points = 0
        total_units = 0

        for r in results:
            total_points += r.grade_point * r.credit_unit
            total_units += r.credit_unit

        if total_units == 0:
            return 0

        return round(total_points / total_units, 2)