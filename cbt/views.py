from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.http import JsonResponse
from .models import Quiz, Question, Answer, QuizResult, QuizAttempt, Examination
from .forms import AdminQuizForm, QuestionForm
from staff.models import Lecturer
from django.core.exceptions import PermissionDenied
import csv
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q, F
from curriculum.models import Level, Course, CourseAssignment, Semester, CourseRegistration


import csv
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import ListFlowable, ListItem
from reportlab.platypus import Table
from reportlab.platypus import TableStyle
from reportlab.platypus import KeepTogether
from reportlab.platypus import HRFlowable
from reportlab.platypus import PageBreak
from reportlab.platypus import Image
from reportlab.platypus import Frame
from reportlab.platypus import BaseDocTemplate
from reportlab.platypus import FrameBreak
from reportlab.platypus import NextPageTemplate
from reportlab.platypus import PageTemplate
from reportlab.platypus import Indenter
from reportlab.platypus import Flowable
from reportlab.platypus import Preformatted
from reportlab.platypus import XPreformatted
from reportlab.platypus import LongTable
from reportlab.platypus import ListFlowable
from reportlab.platypus import ListItem
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Spacer
from reportlab.lib.units import inch
from reportlab.platypus import Table
from reportlab.platypus import TableStyle
from reportlab.lib import colors


@login_required
def export_questions(request, quiz_id, export_type):
    user = request.user
    lecturer = None if user.is_superuser or user.is_staff else get_object_or_404(Lecturer, user=user)

    quiz = get_object_or_404(Quiz, id=quiz_id)

    # Security check
    if not (user.is_superuser or user.is_staff):
        if not CourseAssignment.objects.filter(
            lecturer=lecturer,
            course=quiz.course
            ).exists():        
        # if quiz.examination.course not in lecturer.courses_assigned.all():
            messages.error(request, "Access Denied.")
            return redirect('cbt:main-view')

    questions = quiz.question_set.all()

    # ================= CSV EXPORT =================
    if export_type == "csv":
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{quiz.course}_questions.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Question",
            "Question Type",
            "Option A",
            "Option B",
            "Option C",
            "Option D",
            "Correct Answer",
        ])

        for q in questions:
            writer.writerow([
                q.content,
                q.question_type,
                q.option_a,
                q.option_b,
                q.option_c,
                q.option_d,
                q.correct_answer,
            ])

        return response

    # ================= PDF EXPORT =================
    elif export_type == "pdf":
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{quiz.course}_questions.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        title = Paragraph(
            f"<b>{quiz.course} - {quiz.examination}</b>",
            styles['Heading2']
        )
        elements.append(title)
        elements.append(Spacer(1, 0.3 * inch))

        for index, q in enumerate(questions, start=1):
            question_text = Paragraph(f"<b>Q{index}:</b> {q.content}", styles['Normal'])
            elements.append(question_text)
            elements.append(Spacer(1, 0.1 * inch))

            if q.question_type == "MCQ":
                elements.append(Paragraph(f"A. {q.option_a}", styles['Normal']))
                elements.append(Paragraph(f"B. {q.option_b}", styles['Normal']))
                elements.append(Paragraph(f"C. {q.option_c}", styles['Normal']))
                elements.append(Paragraph(f"D. {q.option_d}", styles['Normal']))
                elements.append(Spacer(1, 0.1 * inch))

            elements.append(
                Paragraph(f"<b>Correct Answer:</b> {q.correct_answer}", styles['Normal'])
            )
            elements.append(Spacer(1, 0.3 * inch))

        doc.build(elements)
        return response

    return redirect('cbt:main-view')




# Create your views here.
@login_required
def cbt_home(request):
    return render(request, 'cbt/cbt_home.html')
@login_required
def cbt_order(request):
    return render(request, 'cbt/cbt_order_form.html')

@login_required
def cbt_lecturer_order(request):
    return render(request, 'cbt/cbt_lecturer_request.html')

@login_required
def student_cbt_home(request):
    """
    Renders the CBT student landing page.
    """
    return render(request, 'cbt/cbt_student_request.html')


@login_required
def submit_cbt_request(request):
    """
    Handles the submission of a CBT exam request form from a lecturer.
    Processes the data and sends an email to the school administration.
    """
    if request.method == 'POST':
        lecturername = request.POST.get('lecturer_name')
        course = request.POST.get('course')
        class_level = request.POST.get('class_level')
        proposed_date = request.POST.get('proposed_date')
        details = request.POST.get('details')

        email_subject = f"New CBT Exam Request from {lecturer_name}"
        email_body = render_to_string('cbt/email_template.html', {
            'lecturer_name': lecturer_name,
            'course': course,
            'class_level': class_level,
            'proposed_date': proposed_date,
            'details': details,
            'user_email': request.user.email,
        })

        try:
            # Send the email to the school administration
            send_mail(
                subject=email_subject,
                message="",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],  # Use the ADMIN_EMAIL from settings
                html_message=email_body,
            )
            messages.success(request, "Your request has been successfully submitted! The administration will contact you shortly.")
        except Exception as e:
            messages.error(request, "An error occurred while submitting your request. Please try again or contact the administrator.")

        return redirect(reverse('cbt:cbt_lecturer_order'))

    return render(request, 'cbt/request_exam.html')



# CBT Logics
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from curriculum.models import CourseAssignment, CourseRegistration, Session, Semester
from .models import Quiz


@login_required
def quiz_list_view(request):
    user = request.user
    lecturer_profile = None

    today = timezone.localdate()
    now = timezone.localtime().time()

    # ================= BASE ACTIVE QUIZ FILTER (UNCHANGED) =================
    quizzes_qs = Quiz.objects.select_related(
        'examination',
        'course',
        'examination__department',
        'session'
    ).filter(
        active=True,
        start_date__lte=today,
        end_date__gte=today,
        start_time__lte=now,
        end_time__gte=now
    )

    # ================= STUDENT =================
    if hasattr(user, 'student'):
        student_profile = user.student

        if student_profile.student_status == 'active':

            # ✅ Get current session & semester
            current_session = Session.objects.filter(is_current=True).first()
            current_semester = Semester.objects.filter(is_current=True).first()

            if not current_session or not current_semester:
                quizzes = Quiz.objects.none()
            else:
                # ✅ Get student's registered courses
                registered_courses = CourseRegistration.objects.filter(
                    student=student_profile,
                    session=current_session,
                    semester=current_semester
                ).values_list('course', flat=True)

                # ✅ Filter quizzes based on registered courses
                quizzes = quizzes_qs.filter(
                    course__in=registered_courses,
                    session=current_session,
                    course__semester=current_semester
                )
        else:
            quizzes = Quiz.objects.none()

    # ================= STAFF / ADMIN =================
    elif user.is_staff and not hasattr(user, 'lecturer'):
        quizzes = quizzes_qs

    # ================= LECTURER =================
    elif hasattr(user, 'lecturer'):
        lecturer = user.lecturer

        assigned_courses = CourseAssignment.objects.filter(
            lecturer=lecturer
        ).values_list('course', flat=True)

        quizzes = quizzes_qs.filter(
            course__in=assigned_courses
        )

    # ================= DEFAULT FALLBACK =================
    else:
        quizzes = Quiz.objects.none()

    # ================= RENDER =================
    return render(request, "quiz/quiz_list.html", {
        "quizzes": quizzes
    })



@login_required
def quiz_detail_view(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    return render(request, 'cbt/quiz.html', {'obj': quiz})



@login_required
def quiz_data_view(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    user = request.user

    # 1️⃣ Block if user already has a VALID completed result
    existing_result = QuizResult.objects.filter(
        user=user,
        quiz=quiz,
        cancelled=False
    ).exists()

    if existing_result:
        return JsonResponse(
            {'error': 'You have already completed this examination.'},
            status=403
        )

    # 2️⃣ Check for existing active attempt (not cancelled)
    attempt = QuizAttempt.objects.filter(
        user=user,
        quiz=quiz,
        completed=False,
        cancelled=False
    ).first()

    # 3️⃣ If no valid attempt exists, create a new one
    if not attempt:
        attempt = QuizAttempt.objects.create(
            user=user,
            quiz=quiz
        )

    # 4️⃣ Format the questions for the JS frontend
    questions = []
    for q in quiz.get_questions():
        questions.append({
            'id': q.id,
            'text': q.content,
            'type': q.question_type,
            'image': q.direct_image_url,
            'options': {
                'A': q.option_a,
                'B': q.option_b,
                'C': q.option_c,
                'D': q.option_d,
            } if q.question_type == 'MCQ' else None
        })

    # 5️⃣ Return data + time remaining
    return JsonResponse({
        'data': questions,
        'time_left': attempt.get_time_left(),
    })


    
@login_required
def save_quiz_view(request, pk):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        quiz = get_object_or_404(Quiz, pk=pk)
        user = request.user

        # Block if valid (non-cancelled) result already exists
        existing_result = QuizResult.objects.filter(
            quiz=quiz,
            user=user,
            cancelled=False
        ).exists()

        if existing_result:
            return JsonResponse({'error': 'Already submitted'}, status=400)

        data = request.POST
        score = 0
        results = []
        questions = quiz.get_questions()

        for q in questions:
            student_answer = data.get(str(q.id))
            is_correct = False

            if student_answer:
                if q.check_answer(student_answer):
                    score += 1
                    is_correct = True

            results.append({
                'question': q.content,
                'correct': q.correct_answer,
                'answered': student_answer if student_answer else "No Answer",
                'is_correct': is_correct
            })

        multiplier = 100 / quiz.number_of_questions
        final_score = score * multiplier
        passed = final_score >= quiz.required_score_to_pass

        # ✅ Save Result
        QuizResult.objects.create(
            quiz=quiz,
            user=user,
            score=final_score,
            passed=passed
        )

        # ✅ IMPORTANT: Mark active attempt as completed
        QuizAttempt.objects.filter(
            user=user,
            quiz=quiz,
            completed=False,
            cancelled=False
        ).update(completed=True)

        return JsonResponse({
            'passed': passed,
            'score': round(final_score, 2),
            'results': results
        })




@login_required
def admin_add_quiz(request):
    """
    Only accessible to superuser or staff.
    Admin creates quizzes for lecturers to add questions to.
    """
    # 1️⃣ Access Control
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Access Denied: Only admin/staff can create quizzes.")
        return redirect('cbt:main-view')

    if request.method == 'POST':
        form = AdminQuizForm(request.POST)

        if form.is_valid():
            quiz = form.save(commit=False)

            # Auto-fill system fields
            quiz.session = quiz.examination.session
            quiz.department = quiz.examination.department
            quiz.number_of_questions = 0  # Start at 0 questions

            # Prevent duplicates using get_or_create
            quiz_obj, created = Quiz.objects.get_or_create(
                examination=quiz.examination,
                course=quiz.course,
                term=quiz.term,
                session=quiz.session,
                defaults={
                    "required_score_to_pass": 50,
                    "active": True,
                    "deparment": quiz.department,
                    "number_of_questions": 0,
                }
            )

            if not created:
                messages.warning(
                    request,
                    "A quiz already exists for this Examination, Course, Term, and Session. "
                    "You can continue adding questions below."
                )
            else:
                messages.success(
                    request,
                    f"Quiz for {quiz_obj.course} created successfully! Now, add questions."
                )

            # Redirect to add question page (lecturer/admin can add)
            return redirect('cbt:lecturer-add-question', quiz_id=quiz_obj.id)

    else:
        form = AdminQuizForm()

    return render(request, 'cbt/admin_add_quiz.html', {
        'form': form
    })



@login_required
def lecturer_add_question(request, quiz_id=None):
    """
    Lecturers can see a list of quizzes and add questions to assigned quizzes.
    Staff and superuser can add to any quiz.
    """
    user = request.user

    # 1️⃣ No quiz_id → show quiz selection page
    if not quiz_id:
        lecturer = None
        try:
            lecturer = Lecturer.objects.get(user=user)
        except Lecturer.DoesNotExist:
            pass

        # ===== BASE QUERYSET (UNCHANGED FLOW, UPDATED LOGIC) =====
        if user.is_staff or user.is_superuser:
            quizzes = Quiz.objects.select_related(
                'course',
                'level',
                'examination'
            ).all()

        elif lecturer:
            assigned_courses = CourseAssignment.objects.filter(
                lecturer=lecturer
            ).values_list('course', flat=True)

            quizzes = Quiz.objects.select_related(
                'course',
                'level',
                'examination'
            ).filter(
                course__in=assigned_courses
            )

        else:
            messages.error(request, "Access Denied.")
            return redirect('cbt:main-view')

        # # ===== FILTER PARAMETERS =====
        # level_id = request.GET.get('level')
        # course_id = request.GET.get('course')
        # semester_id = request.GET.get('semester')

        # if level_id:
        #     quizzes = quizzes.filter(level_id=level_id)

        # if course_id:
        #     quizzes = quizzes.filter(course_id=course_id)

        # if semester_id:
        #     quizzes = quizzes.filter(semester_id=semester_id)

        # # ===== FILTER DROPDOWN DATA =====
        # levels = Level.objects.all()
        # courses = Course.objects.all()
        # semesters = Semester.objects.all()

        # ===== FILTER PARAMETERS =====
        level_id = request.GET.get('level')
        course_id = request.GET.get('course')
        semester_id = request.GET.get('semester')

        if level_id:
            quizzes = quizzes.filter(level_id=level_id)

        if course_id:
            quizzes = quizzes.filter(course_id=course_id)

        if semester_id:
            quizzes = quizzes.filter(semester_id=semester_id)

        # ===== FILTER DROPDOWN DATA =====
        levels = Level.objects.all()
        courses = Course.objects.all()
        semesters = Semester.objects.all()

        return render(request, "cbt/lecturer_select_quiz.html", {
            "quizzes": quizzes,
            "levels": levels,
            "courses": courses,
            "semesters": semesters,
        })

    # 2️⃣ quiz_id provided → go to add question form
    quiz = get_object_or_404(Quiz, id=quiz_id)

    # ===== SECURITY CHECK (UPDATED LOGIC) =====
    if not (user.is_staff or user.is_superuser):
        try:
            lecturer = Lecturer.objects.get(user=user)
        except Lecturer.DoesNotExist:
            raise PermissionDenied("You must be a registered lecturer.")

        is_authorized = CourseAssignment.objects.filter(
            lecturer=lecturer,
            course=quiz.course
        ).exists()

        if not is_authorized:
            messages.error(request, "Access Denied: You are not assigned to this course.")
            return redirect('cbt:main-view')

    # 3️⃣ Handle form submission (UNCHANGED)
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            question.save()

            # Update quiz question count
            Quiz.objects.filter(id=quiz.id).update(
                number_of_questions=F('number_of_questions') + 1
            )

            messages.success(request, "Question added successfully!")

            if 'add_another' in request.POST:
                return redirect('cbt:lecturer-add-question-quiz', quiz_id=quiz.id)

            return redirect('cbt:main-view')
    else:
        form = QuestionForm()

    return render(request, 'cbt/lecturer_add_question.html', {
        'form': form,
        'quiz': quiz,
    })




# LECTURER VIEW QUESTIONS

@login_required
def lecturer_view_questions(request, quiz_id=None):
    user = request.user
    lecturer = None if user.is_superuser or user.is_staff else get_object_or_404(Lecturer, user=user)

    # Filter quizzes based on access
    if user.is_superuser or user.is_staff:
        quizzes = Quiz.objects.all().select_related('course', 'examination', 'department')
    else:
        quizzes = Quiz.objects.filter(
            examination__deparment__in=lecturer.department_assigned.all()
        ).select_related('course', 'examination', 'department')

    selected_quiz = None
    questions = None

    # ✅ FIX: support both URL param and GET param
    quiz_id = quiz_id or request.GET.get('quiz_id')

    if quiz_id:
        selected_quiz = get_object_or_404(Quiz, id=quiz_id)

        # Restrict access for normal lecturers
        if not (user.is_superuser or user.is_staff) and \
           selected_quiz.examination.department not in lecturer.course_assigned.all():
            messages.error(request, "Access Denied.")
            return redirect('cbt:main-view')

        questions = selected_quiz.question_set.all()

    return render(request, 'cbt/lecturer_view_questions.html', {
        'quizzes': quizzes,
        'selected_quiz': selected_quiz,
        'questions': questions,
    })



@login_required
def lecturer_results_view(request):
    user = request.user

    # 1. Base queryset (staff & superuser can see everything)
    if user.is_staff or user.is_superuser:
        results = QuizResult.objects.select_related(
            'user',
            'quiz',
            'quiz__examination',
            'quiz__course'
        ).order_by('-timestamp')

        assigned_course = Level.objects.all()
        exams = Examination.objects.all()

    else:
        # 2. Normal lecturer flow (UNCHANGED logic)
        lecturer = get_object_or_404(Lecturer, user=user)

        results = QuizResult.objects.filter(
            quiz__department__in=lecturer.courses_assigned.all()
        ).select_related(
            'user',
            'quiz',
            'quiz__examination',
            'quiz__course'
        ).order_by('-timestamp')

        assigned_courses = lecturer.departments_assigned.all()
        exams = Examination.objects.filter(
            department__in=assigned_courses
        ).distinct()

    # 3. Apply filters (shared by both)
    exam_id = request.GET.get('examination')
    department_id = request.GET.get('department')

    if exam_id:
        results = results.filter(quiz__examination_id=exam_id)
    if department_id:
        results = results.filter(quiz__department_id=deparment_id)

    # ✅ 4. ADD RETAKE DETECTION (NEW ADDITION)
    for res in results:
        attempt_count = QuizResult.objects.filter(
            user=res.user,
            quiz=res.quiz
        ).count()

        res.is_retake = attempt_count > 1

    return render(request, 'cbt/lecturer_results.html', {
        'results': results,
        'exams': exams,
        'courses': assigned_coursess,
    })


# CBT Results Dwonload
@login_required
def export_results_csv(request):
    examination = request.GET.get('examination')
    department = request.GET.get('level')

    results = QuizResult.objects.select_related(
        'user', 'quiz', 'quiz__level'
    )

    # Apply same filters as the page
    if examination:
        results = results.filter(quiz__exam_id=examination)

    if department:
        results = results.filter(quiz__department_id=department)

    response = HttpResponse(
        content_type='text/csv'
    )
    response['Content-Disposition'] = 'attachment; filename="student_CBT_results.csv"'

    writer = csv.writer(response)

    # CSV Header
    writer.writerow([
        'Student Name',
        'Username',
        'Level',
        'Examination',
        'Term',
        'Session',
        'Course',
        'Score (%)',
        'Status',
        'Date Taken'
    ])

    # CSV Rows
    for res in results:
        writer.writerow([
            res.user.get_full_name() or res.user.username,
            res.user.username,
            res.quiz.level.name if res.quiz.level else '',
            res.quiz.examination.name if res.quiz.examination.name else '',
            res.quiz.term if res.quiz.term else '',
            res.quiz.session.name if res.quiz.session.name else '',


            res.quiz.course,
            round(res.score, 1),
            'Passed' if res.passed else 'Failed',
            res.timestamp.strftime('%Y-%m-%d %H:%M')
        ])

    return response