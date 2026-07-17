from django.core.management.base import BaseCommand
from django.utils.text import slugify

from ai_center.models import (
    PromptCategory,
    PromptLibrary
)


class Command(BaseCommand):

    help = "Load Prompt Library for a Tertiary Institution"

    def handle(self, *args, **kwargs):

        prompts = [

            # ================= LECTURE NOTES & COURSE MATERIALS =================

            {
                "category": "Lecture Notes & Course Materials",
                "title": "Generate a Full Lecture Note",
                "school_level": "TERTIARY",
                "subject": "Any Course",
                "prompt_text": """
Act as an experienced university/college lecturer.

Generate a complete lecture note for:

Course: [COURSE CODE] - [COURSE TITLE]
Level: [LEVEL, e.g. 200L / ND2 / HND1]
Topic: [TOPIC]

Include:

1. Learning Outcomes
2. Prerequisite Knowledge
3. Introduction
4. Detailed Content (with sub-headings)
5. Diagrams/Examples Where Relevant
6. In-Class Activity or Case Study
7. Summary
8. Suggested Reading / References
"""
            },

            {
                "category": "Lecture Notes & Course Materials",
                "title": "Generate Slide-Ready Lecture Outline",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Act as a university lecturer preparing slides.

Generate a slide-by-slide outline for:

Course: [COURSE CODE] - [COURSE TITLE]
Topic: [TOPIC]
Number of Slides: [NUMBER]

For each slide, provide a heading and 3-5 bullet points.
"""
            },

            {
                "category": "Lecture Notes & Course Materials",
                "title": "Simplify a Complex Topic",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Act as a lecturer explaining a difficult concept to first-year students.

Topic: [TOPIC]
Course: [COURSE CODE]

Explain it in plain language, then provide one real-world analogy and
one worked example.
"""
            },

            # ================= CBT / OBJECTIVE QUESTIONS =================

            {
                "category": "CBT / Objective Questions",
                "title": "Generate 40 CBT Questions",
                "school_level": "TERTIARY",
                "subject": "Any Course",
                "prompt_text": """
Act as a university examiner.

Generate 40 multiple-choice (CBT) questions.

Course: [COURSE CODE] - [COURSE TITLE]
Level: [LEVEL]
Topic(s): [TOPIC]

Requirements:

- Four options A-D
- One correct answer clearly marked
- A short explanation for the correct answer
- Mix of recall, application, and analysis-level questions
"""
            },

            {
                "category": "CBT / Objective Questions",
                "title": "Generate Objective Test from Course Outline",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate 20 multiple-choice questions based on this course outline.

Course Outline:

[PASTE COURSE OUTLINE]

Provide the answer key at the end.
"""
            },

            {
                "category": "CBT / Objective Questions",
                "title": "Convert Past Questions into a CBT Bank",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Act as an exams officer.

Convert the following past exam questions into a structured CBT-ready
question bank with options A-D, correct answers, and difficulty ratings
(Easy/Medium/Hard).

Questions:

[PASTE PAST QUESTIONS]
"""
            },

            # ================= THEORY & ESSAY QUESTIONS =================

            {
                "category": "Theory & Essay Questions",
                "title": "Generate a Theory Examination Paper",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate a theory examination paper.

Course: [COURSE CODE] - [COURSE TITLE]
Level: [LEVEL]
Duration: [DURATION]

Section A: Short Answer Questions (5)
Section B: Essay Questions (3, answer any 2)

Include a marking guide with allocated marks for each part.
"""
            },

            {
                "category": "Theory & Essay Questions",
                "title": "Generate Case-Study Based Questions",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Act as a course examiner.

Generate a realistic case study relevant to [COURSE/DISCIPLINE, e.g.
Nursing, Business Administration, Civil Engineering] and 4 follow-up
questions that test application of course concepts to the case.
"""
            },

            # ================= MARKING SCHEMES & RUBRICS =================

            {
                "category": "Marking Schemes & Rubrics",
                "title": "Generate a Marking Scheme",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate a complete marking scheme for the following questions.

Course: [COURSE CODE]

Questions:

[PASTE QUESTIONS]

Allocate marks per point and show the total per question.
"""
            },

            {
                "category": "Marking Schemes & Rubrics",
                "title": "Generate an Assessment Rubric",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Create a grading rubric for the following assessment.

Assessment Type: [e.g. Group Project, Seminar Presentation, Lab Report]

Criteria to score:

Knowledge/Understanding
Application/Practical Skill
Presentation/Communication
Originality

Output as a table with 4 performance bands (Excellent, Good, Fair, Poor)
and the mark range for each.
"""
            },

            # ================= ASSIGNMENTS & PROJECTS =================

            {
                "category": "Assignments & Projects",
                "title": "Generate a Course Assignment",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate a take-home assignment.

Course: [COURSE CODE] - [COURSE TITLE]

Level: [LEVEL]

Topic: [TOPIC]

Difficulty: Medium

Include clear submission instructions and a word/page limit.
"""
            },

            {
                "category": "Assignments & Projects",
                "title": "Generate a Group Project Brief",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate a group project brief.

Course: [COURSE CODE]

Discipline: [e.g. Mechanical Engineering, Social Work, Accounting]

Include:

Objectives
Deliverables
Suggested Timeline
Assessment Criteria
"""
            },

            # ================= PRACTICAL & CLINICAL ASSESSMENT =================

            {
                "category": "Practical & Clinical Assessment",
                "title": "Generate a Laboratory/Workshop Practical Sheet",
                "school_level": "TERTIARY",
                "subject": "Engineering / Sciences",
                "prompt_text": """
Act as a laboratory instructor.

Generate a practical/lab sheet for:

Course: [COURSE CODE] - [COURSE TITLE]
Experiment/Task: [TITLE]

Include:

Aim
Apparatus/Materials
Procedure (step-by-step)
Observation Table
Post-Lab Questions
Safety Precautions
"""
            },

            {
                "category": "Practical & Clinical Assessment",
                "title": "Generate an OSCE / Clinical Skills Checklist",
                "school_level": "TERTIARY",
                "subject": "Nursing / Medicine",
                "prompt_text": """
Act as a clinical skills examiner in a School of Nursing/Medicine.

Generate an OSCE-style checklist for the procedure:

[PROCEDURE, e.g. Wound Dressing, Vital Signs Assessment, IV Cannulation]

Include:

Step-by-step checklist with Pass/Fail criteria per step
Common errors to watch for
Overall competency rating scale
"""
            },

            {
                "category": "Practical & Clinical Assessment",
                "title": "Generate an Industrial Training (SIWES) Assessment Form",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate a supervisor's assessment form for a student on industrial
attachment/SIWES.

Programme: [PROGRAMME]

Include rating scales for:

Punctuality & Discipline
Technical/Practical Skill
Initiative
Report Writing
Overall Recommendation
"""
            },

            # ================= TIMETABLE GENERATION =================

            {
                "category": "Timetable Generation",
                "title": "Generate a Departmental Lecture Timetable",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Create a weekly lecture timetable.

Department/Faculty: [DEPARTMENT]

Courses & Levels:

[LIST COURSES AND LEVELS]

Available Lecture Hours:

[HOURS]

Avoid clashes for shared courses. Output in table format.
"""
            },

            {
                "category": "Timetable Generation",
                "title": "Generate a Lecturer's Personal Timetable",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate a personal weekly timetable for a lecturer.

Lecturer Name: [NAME]

Courses Assigned:

[LIST COURSES]

Avoid clashes and leave time for office hours and research.
"""
            },

            {
                "category": "Timetable Generation",
                "title": "Generate an Examination Timetable",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Create an examination timetable.

Faculty/Department: [DEPARTMENT]

Courses to Examine:

[LIST COURSES]

Exam Period:

[DATE RANGE]

Ensure no student sits two exams at the same time, and space papers
for the same level at least one day apart where possible.
"""
            },

            # ================= COURSE OUTLINE & CURRICULUM PLANNING =================

            {
                "category": "Course Outline & Curriculum Planning",
                "title": "Generate a Semester Course Outline",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate a full-semester course outline.

Course: [COURSE CODE] - [COURSE TITLE]

Credit Units: [UNITS]

Weeks: [NUMBER, e.g. 15]

Output as a week-by-week table with Topic, Learning Outcomes, and
Suggested Reading per week.
"""
            },

            {
                "category": "Course Outline & Curriculum Planning",
                "title": "Align Course Outline to Accreditation Standard",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Act as a curriculum planning officer.

Review the course outline below against a standard accreditation
benchmark (e.g. NUC/NBTE/professional body) and suggest gaps or
missing learning outcomes.

Course Outline:

[PASTE COURSE OUTLINE]
"""
            },

            # ================= RESULT ANALYSIS =================

            {
                "category": "Result Analysis",
                "title": "Analyze Course Result Performance",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Analyze the following course result data.

Course: [COURSE CODE]

Data:

[PASTE RESULT DATA]

Provide:

Highest, Lowest, and Average Score
Pass Rate and Fail Rate
Grade Distribution (A-F)
Observations and Recommendations for the Course Coordinator
"""
            },

            {
                "category": "Result Analysis",
                "title": "Generate Departmental Performance Report",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate a departmental academic performance report.

Department: [DEPARTMENT]

Semester: [SEMESTER]

Result Data:

[PASTE SCORES/CGPA DATA]

Include a summary suitable for presentation to the Head of Department.
"""
            },

            {
                "category": "Result Analysis",
                "title": "Draft Academic Standing / Probation Comment",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Act as an academic adviser.

Draft a professional, constructive comment on a student's academic
standing.

CGPA: [CGPA]

Academic Standing: [e.g. Good Standing / Probation / Withdrawal Warning]

Attendance: [ATTENDANCE]

Provide the comment plus 2-3 specific, actionable recommendations for
the student.
"""
            },

            # ================= RESEARCH & PROJECT SUPERVISION =================

            {
                "category": "Research & Project Supervision",
                "title": "Generate Final Year Project Topic Ideas",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Act as a project supervisor.

Suggest 10 final year project topics for a student in:

Department: [DEPARTMENT, e.g. Computer Engineering, Public Health,
Business Administration]

Area of Interest: [AREA OF INTEREST]

For each topic, include a one-sentence justification of relevance.
"""
            },

            {
                "category": "Research & Project Supervision",
                "title": "Review a Project Proposal / Abstract",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Act as an academic supervisor reviewing a student's project proposal.

Proposal/Abstract:

[PASTE PROPOSAL OR ABSTRACT]

Give feedback on: clarity of problem statement, feasibility, gaps in
methodology, and suggested improvements.
"""
            },

            {
                "category": "Research & Project Supervision",
                "title": "Generate Seminar/Defense Questions",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Act as a panel member at a project/thesis defense.

Based on this project summary, generate 8 likely defense questions,
ranging from methodology to findings and implications.

Project Summary:

[PASTE SUMMARY]
"""
            },

            # ================= STUDENT COMMUNICATION =================

            {
                "category": "Student Communication",
                "title": "Draft a Class/Level Announcement",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Draft a professional announcement to students.

Audience: [e.g. 300L Nursing Students, All Engineering Finalists]

Purpose:

[PURPOSE]

Key Details:

[DATE / VENUE / DEADLINE ETC.]

Keep it concise and clear.
"""
            },

            {
                "category": "Student Communication",
                "title": "Draft a Response to a Student Complaint",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Act as a student affairs officer.

Draft a professional, empathetic response to the following student
complaint or inquiry.

Complaint/Inquiry:

[PASTE COMPLAINT]

Tone: Respectful, solution-oriented, and clear on next steps.
"""
            },

            # ================= ADMISSIONS & ENROLLMENT =================

            {
                "category": "Admissions & Enrollment",
                "title": "Generate Admission Interview Questions",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate admission/screening interview questions for prospective
students.

Programme Seeking Admission: [PROGRAMME]

Include:

Academic/Subject-Knowledge Questions
Motivation & Career-Goal Questions
Situational/Behavioural Questions
"""
            },

            {
                "category": "Admissions & Enrollment",
                "title": "Draft an Admission Offer / Regret Letter",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Draft a formal admission [OFFER/REGRET] letter.

Programme: [PROGRAMME]

Applicant Name: [NAME]

Keep the tone formal, warm, and clear on next steps (if an offer) or
respectful and encouraging (if a regret letter).
"""
            },

            # ================= INSTITUTION ADMINISTRATION =================

            {
                "category": "Institution Administration",
                "title": "Draft an Official Circular",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Draft an official institutional circular.

Topic:

[TOPIC]

Target Audience:

[STAFF / STUDENTS / ALL]

Keep it formal and unambiguous, with a clear effective date.
"""
            },

            {
                "category": "Institution Administration",
                "title": "Draft a Staff Memo",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Generate a staff memo.

Purpose:

[PURPOSE]

Department(s) Affected:

[DEPARTMENTS]

Professional tone, clearly stating any required action and deadline.
"""
            },

            {
                "category": "Institution Administration",
                "title": "Draft a Departmental Meeting Agenda",
                "school_level": "TERTIARY",
                "subject": "",
                "prompt_text": """
Draft a meeting agenda for a departmental/faculty board meeting.

Department/Faculty: [DEPARTMENT]

Meeting Date: [DATE]

Key Matters to Discuss:

[LIST MATTERS]

Output as a numbered agenda with an estimated time allocation per item.
"""
            },

        ]

        for item in prompts:

            category, created = PromptCategory.objects.get_or_create(
                name=item["category"],
                defaults={
                    "slug": slugify(item["category"])
                }
            )

            PromptLibrary.objects.update_or_create(
                title=item["title"],
                defaults={
                    "category": category,
                    "school_level": item["school_level"],
                    "subject": item["subject"],
                    "prompt_text": item["prompt_text"],
                    "is_featured": True,
                    "is_active": True,
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Tertiary Prompt Library Loaded Successfully."
            )
        )
