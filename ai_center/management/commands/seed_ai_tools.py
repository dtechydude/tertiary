from django.core.management.base import BaseCommand

from ai_center.models import (
    AIToolCategory,
    AITool
)


class Command(BaseCommand):

    help = "Load AI Tools Seed Data for a Tertiary Institution"

    def handle(self, *args, **kwargs):

        categories = {

            "General AI": "fas fa-robot",

            "Academic Research & Literature Review": "fas fa-book",

            "Presentation & Content Creation": "fas fa-chalkboard",

            "Assessment & CBT": "fas fa-clipboard-check",

            "Visual Learning & Mind Mapping": "fas fa-project-diagram",

            "Video & Media Creation": "fas fa-video",

            "Writing & Academic Integrity": "fas fa-pen-nib",

        }

        for name, icon in categories.items():

            AIToolCategory.objects.get_or_create(
                name=name,
                defaults={
                    "icon": icon
                }
            )

        tools = [

            {
                "category": "General AI",
                "name": "ChatGPT",
                "description": "Generate lecture notes, CBT questions, examinations, and administrative documents for any course or department.",
                "best_for": "Lecture Notes, CBT, Exams, Memos",
                "website_url": "https://chatgpt.com",
                "icon_class": "fas fa-comments",
                "is_featured": True,
            },

            {
                "category": "General AI",
                "name": "Gemini",
                "description": "Google's AI assistant, useful for research, drafting, and quick summaries across disciplines.",
                "best_for": "Research, Course Planning",
                "website_url": "https://gemini.google.com",
                "icon_class": "fab fa-google",
                "is_featured": True,
            },

            {
                "category": "Academic Research & Literature Review",
                "name": "NotebookLM",
                "description": "Upload lecture slides, journals, or textbooks and get an AI study companion grounded in your own material.",
                "best_for": "Literature Review, Study Materials",
                "website_url": "https://notebooklm.google.com",
                "icon_class": "fas fa-book-open",
                "is_featured": True,
            },

            {
                "category": "Academic Research & Literature Review",
                "name": "Perplexity",
                "description": "AI-powered research assistant that cites sources — useful for evidence-based research across Engineering, Medicine, Social Sciences and Management.",
                "best_for": "Research, Fact-Checking",
                "website_url": "https://www.perplexity.ai",
                "icon_class": "fas fa-search",
                "is_featured": True,
            },

            {
                "category": "Academic Research & Literature Review",
                "name": "Claude",
                "description": "Strong at long-form academic writing, literature reviews, and reasoning through technical or clinical material.",
                "best_for": "Long-form Writing, Research Synthesis",
                "website_url": "https://claude.ai",
                "icon_class": "fas fa-brain",
            },

            {
                "category": "Academic Research & Literature Review",
                "name": "Elicit",
                "description": "AI research assistant that finds, summarizes, and extracts data from academic papers.",
                "best_for": "Literature Review, Systematic Reviews",
                "website_url": "https://elicit.com",
                "icon_class": "fas fa-flask",
            },

            {
                "category": "Academic Research & Literature Review",
                "name": "Consensus",
                "description": "Search engine that surfaces findings directly from peer-reviewed research papers.",
                "best_for": "Evidence-Based Research",
                "website_url": "https://consensus.app",
                "icon_class": "fas fa-balance-scale",
            },

            {
                "category": "Presentation & Content Creation",
                "name": "Canva AI",
                "description": "Design presentation slides, posters, and departmental flyers quickly.",
                "best_for": "Presentations, Posters",
                "website_url": "https://www.canva.com",
                "icon_class": "fas fa-palette",
            },

            {
                "category": "Presentation & Content Creation",
                "name": "Gamma",
                "description": "Turn an outline or lecture topic into a polished slide deck in minutes.",
                "best_for": "Lecture Slides",
                "website_url": "https://gamma.app",
                "icon_class": "fas fa-desktop",
            },

            {
                "category": "Assessment & CBT",
                "name": "Quizizz",
                "description": "Build interactive quizzes for in-class or take-home assessment.",
                "best_for": "CBT, Formative Assessment",
                "website_url": "https://quizizz.com",
                "icon_class": "fas fa-question-circle",
            },

            {
                "category": "Assessment & CBT",
                "name": "Kahoot",
                "description": "Gamified quizzes for lecture halls and revision sessions.",
                "best_for": "Interactive Quizzes",
                "website_url": "https://kahoot.com",
                "icon_class": "fas fa-gamepad",
            },

            {
                "category": "Assessment & CBT",
                "name": "Quizlet",
                "description": "Flashcards and revision sets — useful for terminology-heavy courses like Medicine, Nursing, and Law.",
                "best_for": "Revision, Flashcards",
                "website_url": "https://quizlet.com",
                "icon_class": "fas fa-clone",
            },

            {
                "category": "Visual Learning & Mind Mapping",
                "name": "Miro",
                "description": "Collaborative whiteboard for project planning, brainstorming, and process diagrams.",
                "best_for": "Project Planning, Brainstorming",
                "website_url": "https://miro.com",
                "icon_class": "fas fa-project-diagram",
            },

            {
                "category": "Visual Learning & Mind Mapping",
                "name": "MindMeister",
                "description": "Mind mapping tool for structuring course outlines, research proposals, and thesis chapters.",
                "best_for": "Course Planning, Research Structuring",
                "website_url": "https://www.mindmeister.com",
                "icon_class": "fas fa-sitemap",
            },

            {
                "category": "Visual Learning & Mind Mapping",
                "name": "Napkin AI",
                "description": "Turns written explanations into visual diagrams — handy for engineering processes and workflows.",
                "best_for": "Diagrams, Visual Explanations",
                "website_url": "https://napkin.ai",
                "icon_class": "fas fa-lightbulb",
            },

            {
                "category": "Video & Media Creation",
                "name": "HeyGen",
                "description": "Create AI presenter videos for online courses or orientation content.",
                "best_for": "Course Videos, Orientation Content",
                "website_url": "https://www.heygen.com",
                "icon_class": "fas fa-video",
            },

            {
                "category": "Video & Media Creation",
                "name": "Synthesia",
                "description": "AI video generation, useful for staff training and induction videos.",
                "best_for": "Staff Training Videos",
                "website_url": "https://www.synthesia.io",
                "icon_class": "fas fa-film",
            },

            {
                "category": "Writing & Academic Integrity",
                "name": "Grammarly",
                "description": "Grammar, clarity, and tone checking for reports, memos, and academic writing.",
                "best_for": "Proofreading, Academic Writing",
                "website_url": "https://www.grammarly.com",
                "icon_class": "fas fa-spell-check",
            },

            {
                "category": "Writing & Academic Integrity",
                "name": "QuillBot",
                "description": "Paraphrasing and citation tool to help students and staff rework and reference written work.",
                "best_for": "Paraphrasing, Citations",
                "website_url": "https://quillbot.com",
                "icon_class": "fas fa-quote-right",
            },

        ]

        for item in tools:

            category = AIToolCategory.objects.get(
                name=item["category"]
            )

            AITool.objects.get_or_create(

                name=item["name"],

                defaults={

                    "category": category,

                    "description": item["description"],

                    "best_for": item["best_for"],

                    "website_url": item["website_url"],

                    "icon_class": item["icon_class"],

                    "is_featured": item.get(
                        "is_featured",
                        False
                    ),

                    "is_active": True,
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                "AI Tools loaded successfully."
            )
        )
