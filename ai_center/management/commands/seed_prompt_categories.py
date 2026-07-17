from django.core.management.base import BaseCommand
from django.utils.text import slugify

from ai_center.models import PromptCategory


class Command(BaseCommand):

    help = "Load Prompt Categories for a Tertiary Institution"

    def handle(self, *args, **kwargs):

        categories = [
            "Lecture Notes & Course Materials",
            "CBT / Objective Questions",
            "Theory & Essay Questions",
            "Marking Schemes & Rubrics",
            "Assignments & Projects",
            "Practical & Clinical Assessment",
            "Timetable Generation",
            "Course Outline & Curriculum Planning",
            "Result Analysis",
            "Research & Project Supervision",
            "Student Communication",
            "Admissions & Enrollment",
            "Institution Administration",
        ]

        for index, name in enumerate(categories):

            PromptCategory.objects.get_or_create(
                name=name,
                defaults={
                    "slug": slugify(name),
                    "display_order": index,
                    "is_active": True,
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Prompt Categories Loaded Successfully."
            )
        )
