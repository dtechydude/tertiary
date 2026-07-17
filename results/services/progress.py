"""
results.services.progress
===========================

Answers: "of everything this student needs to pass to graduate, what
have they passed, and what's left?"

The tricky part is that `curriculum.Course` rows are tied to a specific
Session (each academic year's offering is its own row), but a
curriculum requirement ("MTH101 is compulsory for OND1 Computer
Science") is stable across sessions. This service de-duplicates by
`course_code` so re-entering the same course every session doesn't
inflate the "total required" count — see `get_curriculum_courses`.

Nothing here computes a grade or a GPA — that's GradingService/GPAService.
This only answers the "coverage" question: required vs passed vs
outstanding, split by compulsory/elective.
"""

from curriculum.models import Course, Level

from ..models import Result


class AcademicProgressService:

    @staticmethod
    def get_curriculum_courses(student):
        """
        Every distinct course (by course_code) ever offered for this
        student's department + programme, across every level that
        programme has — i.e. the full curriculum, not just what's been
        offered in any single session. Returns the most recent Course row
        for each course_code (for title/credit_unit/course_type display),
        assuming those are stable across re-offerings of the same code.
        """
        levels = Level.objects.filter(programme=student.programme)
        courses_qs = Course.objects.filter(
            department=student.department,
            programme=student.programme,
            level__in=levels,
        ).select_related("level", "semester", "session").order_by("-session__start_date", "course_code")

        seen = {}
        for course in courses_qs:
            if course.course_code not in seen:
                seen[course.course_code] = course
        return list(seen.values())

    @classmethod
    def build_progress(cls, student, filter_session=None, filter_semester=None):
        curriculum_courses = cls.get_curriculum_courses(student)
        compulsory = [c for c in curriculum_courses if c.course_type == Course.CourseType.COMPULSORY]
        electives = [c for c in curriculum_courses if c.course_type == Course.CourseType.ELECTIVE]

        # Cumulative, published results across the student's whole
        # history — "outstanding to graduate" is inherently a whole-
        # programme question, not a single-semester one.
        all_results = Result.objects.filter(
            student=student, is_published=True
        ).select_related("course", "session", "semester")

        best_result_by_code = {}
        for result in all_results:
            code = result.course.course_code
            existing = best_result_by_code.get(code)
            # Prefer a pass over a fail if the student has multiple
            # attempts (carry-over cleared on a later sitting).
            if not existing or (result.grade_point or 0) > (existing.grade_point or 0):
                best_result_by_code[code] = result

        passed_codes = {
            code for code, r in best_result_by_code.items() if (r.grade_point or 0) > 0
        }

        def build_rows(course_list):
            rows = []
            for course in course_list:
                result = best_result_by_code.get(course.course_code)
                if course.course_code in passed_codes:
                    status = "passed"
                elif result:
                    status = "failed"
                else:
                    status = "outstanding"
                rows.append({"course": course, "status": status, "result": result})
            return rows

        compulsory_rows = build_rows(compulsory)
        elective_rows = build_rows(electives)

        total_required = len(compulsory)
        passed_required = sum(1 for c in compulsory if c.course_code in passed_codes)
        outstanding_required = total_required - passed_required

        # Optional period-specific slice, only for the "filter by
        # session/semester" view — doesn't affect the cumulative figures
        # above, since those must reflect the whole programme.
        period_results = None
        if filter_session or filter_semester:
            qs = Result.objects.filter(student=student, is_published=True)
            if filter_session:
                qs = qs.filter(session=filter_session)
            if filter_semester:
                qs = qs.filter(semester=filter_semester)
            period_results = qs.select_related("course", "session", "semester")

        return {
            "compulsory_rows": compulsory_rows,
            "elective_rows": elective_rows,
            "total_required_courses": total_required,
            "passed_required_courses": passed_required,
            "outstanding_required_courses": outstanding_required,
            "percent_complete": round((passed_required / total_required) * 100, 1) if total_required else 0,
            "period_results": period_results,
        }
