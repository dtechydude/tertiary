import csv

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from curriculum.models import (
    Course,
    CourseAssignment,
    CourseRegistration,
    Level,
    Semester,
    Session,
)
from staff.models import Lecturer

from .forms import AdminQuizForm, QuestionForm
from .models import Examination, Question, Quiz, QuizAttempt, QuizResult


# =====================================================================
# Helpers
# =====================================================================

def _get_lecturer_or_none(user):
    """Returns the Lecturer profile for a user, or None if they aren't one."""
    try:
        return Lecturer.objects.get(user=user)
    except Lecturer.DoesNotExist:
        return None


def _assigned_course_ids(lecturer):
    """Course IDs a lecturer is currently assigned to teach/administer CBTs for."""
    return set(
        CourseAssignment.objects.filter(lecturer=lecturer).values_list('course_id', flat=True)
    )


def _lecturer_is_authorized_for_quiz(user, quiz, lecturer=None):
    """Staff/superusers may manage any quiz; lecturers only their assigned courses."""
    if user.is_superuser or user.is_staff:
        return True
    if lecturer is None:
        lecturer = _get_lecturer_or_none(user)
    if lecturer is None:
        return False
    return CourseAssignment.objects.filter(lecturer=lecturer, course=quiz.course).exists()


# =====================================================================
# Info / guide pages
# =====================================================================

@login_required
def cbt_home(request):
    return render(request, 'cbt/cbt_home.html')


@login_required
def cbt_order(request):
    return render(request, 'cbt/cbt_order_form.html')


@login_required
def cbt_lecturer_guide(request):
    return render(request, 'cbt/cbt_lecturer_guide.html')


@login_required
def cbt_student_guide(request):
    return render(request, 'cbt/cbt_student_guide.html')


@login_required
def request_cbt_exam(request):
    """
    Lets a lecturer request that admin set up a CBT sitting for a course,
    e-mailing the school administration with the details.
    """
    if request.method == 'POST':
        lecturer_name = request.POST.get('lecturer_name')
        course = request.POST.get('course')
        level = request.POST.get('level')
        proposed_date = request.POST.get('proposed_date')
        details = request.POST.get('details')

        email_subject = f"New CBT Exam Request from {lecturer_name}"
        email_body = render_to_string('cbt/email_template.html', {
            'lecturer_name': lecturer_name,
            'course': course,
            'level': level,
            'proposed_date': proposed_date,
            'details': details,
            'user_email': request.user.email,
        })

        try:
            send_mail(
                subject=email_subject,
                message="",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],
                html_message=email_body,
            )
            messages.success(
                request,
                "Your request has been successfully submitted! The administration will contact you shortly.",
            )
        except Exception:
            messages.error(
                request,
                "An error occurred while submitting your request. Please try again or contact the administrator.",
            )

        return redirect(reverse('cbt:request-exam'))

    return render(request, 'cbt/request_exam.html')


# =====================================================================
# Candidate exam-taking flow
# =====================================================================

@login_required
def quiz_list_view(request):
    user = request.user

    today = timezone.localdate()
    now = timezone.localtime().time()

    quizzes_qs = Quiz.objects.select_related(
        'examination',
        'course',
        'examination__department',
        'level',
        'session',
    ).filter(
        active=True,
        start_date__lte=today,
        end_date__gte=today,
        start_time__lte=now,
        end_time__gte=now,
    )

    lecturer_course_ids = set()

    # ================= STUDENT =================
    if hasattr(user, 'student'):
        student_profile = user.student

        if getattr(student_profile, 'student_status', None) == 'active':
            current_session = Session.objects.filter(is_current=True).first()
            current_semester = Semester.objects.filter(is_current=True).first()

            if not current_session or not current_semester:
                quizzes = Quiz.objects.none()
            else:
                registered_courses = CourseRegistration.objects.filter(
                    student=student_profile,
                    session=current_session,
                    semester=current_semester,
                ).values_list('course_id', flat=True)

                quizzes = quizzes_qs.filter(
                    course_id__in=registered_courses,
                    session=current_session,
                    semester=current_semester.name,
                )
        else:
            quizzes = Quiz.objects.none()

    # ================= STAFF / ADMIN (non-lecturer) =================
    elif user.is_staff and not hasattr(user, 'lecturer'):
        quizzes = quizzes_qs

    # ================= LECTURER =================
    elif hasattr(user, 'lecturer'):
        lecturer = user.lecturer
        lecturer_course_ids = _assigned_course_ids(lecturer)
        quizzes = quizzes_qs.filter(course_id__in=lecturer_course_ids)

    # ================= DEFAULT FALLBACK =================
    else:
        quizzes = Quiz.objects.none()

    return render(request, 'cbt/main.html', {
        'quizzes': quizzes,
        'lecturer_course_ids': lecturer_course_ids,
    })


@login_required
def quiz_detail_view(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    return render(request, 'cbt/quiz.html', {'obj': quiz})


@login_required
def quiz_data_view(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    user = request.user

    existing_result = QuizResult.objects.filter(
        user=user, quiz=quiz, cancelled=False
    ).exists()
    if existing_result:
        return JsonResponse(
            {'error': 'You have already completed this examination.'}, status=403
        )

    attempt = QuizAttempt.objects.filter(
        user=user, quiz=quiz, completed=False, cancelled=False
    ).first()

    if not attempt:
        attempt = QuizAttempt.objects.create(user=user, quiz=quiz)

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
            } if q.question_type == 'MCQ' else None,
        })

    return JsonResponse({
        'data': questions,
        'time_left': attempt.get_time_left(),
    })


@login_required
def save_quiz_view(request, pk):
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    quiz = get_object_or_404(Quiz, pk=pk)
    user = request.user

    existing_result = QuizResult.objects.filter(
        quiz=quiz, user=user, cancelled=False
    ).exists()
    if existing_result:
        return JsonResponse({'error': 'Already submitted'}, status=400)

    if not quiz.number_of_questions:
        return JsonResponse({'error': 'This quiz has no questions configured.'}, status=400)

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
            'is_correct': is_correct,
        })

    multiplier = 100 / quiz.number_of_questions
    final_score = score * multiplier
    passed = final_score >= quiz.required_score_to_pass

    QuizResult.objects.create(
        quiz=quiz,
        user=user,
        score=final_score,
        passed=passed,
    )

    QuizAttempt.objects.filter(
        user=user, quiz=quiz, completed=False, cancelled=False
    ).update(completed=True)

    return JsonResponse({
        'passed': passed,
        'score': round(final_score, 2),
        'results': results,
    })


# =====================================================================
# Admin / staff quiz setup
# =====================================================================

@login_required
def admin_add_quiz(request):
    """
    Only accessible to superuser or staff. Stands up a Quiz ("CBT sitting")
    for a Course under a given Examination, ready for question entry.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Access Denied: Only admin/staff can create quizzes.")
        return redirect('cbt:main-view')

    if request.method == 'POST':
        form = AdminQuizForm(request.POST)

        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.session = quiz.examination.session

            quiz_obj, created = Quiz.objects.get_or_create(
                examination=quiz.examination,
                course=quiz.course,
                semester=quiz.semester,
                session=quiz.session,
                defaults={
                    'level': quiz.level,
                    'time': quiz.time,
                    'required_score_to_pass': quiz.required_score_to_pass or 50,
                    'start_date': quiz.start_date,
                    'end_date': quiz.end_date,
                    'start_time': quiz.start_time,
                    'end_time': quiz.end_time,
                    'active': quiz.active,
                    'number_of_questions': 0,
                },
            )

            if not created:
                messages.warning(
                    request,
                    "A quiz already exists for this Examination, Course, Semester, and Session. "
                    "You can continue adding questions below.",
                )
            else:
                messages.success(
                    request,
                    f"Quiz for {quiz_obj.course} created successfully! Now, add questions.",
                )

            return redirect('cbt:lecturer-add-question-quiz', quiz_id=quiz_obj.id)
    else:
        form = AdminQuizForm()

    return render(request, 'cbt/admin_add_quiz.html', {'form': form})


# =====================================================================
# Lecturer question-bank management
# =====================================================================

@login_required
def lecturer_add_question(request, quiz_id=None):
    """
    Lecturers see a filterable list of quizzes for courses they're assigned
    to and add questions to them. Staff/superusers may manage any quiz.
    """
    user = request.user
    lecturer = _get_lecturer_or_none(user)

    # 1) No quiz_id -> show quiz selection page
    if not quiz_id:
        if user.is_staff or user.is_superuser:
            quizzes = Quiz.objects.select_related('course', 'level', 'examination').all()
        elif lecturer:
            assigned_course_ids = _assigned_course_ids(lecturer)
            quizzes = Quiz.objects.select_related(
                'course', 'level', 'examination'
            ).filter(course_id__in=assigned_course_ids)
        else:
            messages.error(request, "Access Denied.")
            return redirect('cbt:main-view')

        level_id = request.GET.get('level')
        course_id = request.GET.get('course')
        semester = request.GET.get('semester')

        if level_id:
            quizzes = quizzes.filter(level_id=level_id)
        if course_id:
            quizzes = quizzes.filter(course_id=course_id)
        if semester:
            quizzes = quizzes.filter(semester=semester)

        levels = Level.objects.all()
        courses = (
            Course.objects.all()
            if (user.is_staff or user.is_superuser)
            else Course.objects.filter(id__in=_assigned_course_ids(lecturer))
        )
        semesters = Quiz._meta.get_field('semester').choices

        return render(request, 'cbt/lecturer_select_quiz.html', {
            'quizzes': quizzes,
            'levels': levels,
            'courses': courses,
            'semesters': semesters,
        })

    # 2) quiz_id provided -> go to add-question form
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if not _lecturer_is_authorized_for_quiz(user, quiz, lecturer=lecturer):
        messages.error(request, "Access Denied: You are not assigned to this course.")
        return redirect('cbt:main-view')

    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            question.save()

            Quiz.objects.filter(id=quiz.id).update(
                number_of_questions=F('number_of_questions') + 1
            )

            messages.success(request, "Question added successfully!")

            if 'add_another' in request.POST:
                return redirect('cbt:lecturer-add-question-quiz', quiz_id=quiz.id)

            return redirect('cbt:lecturer-view-questions-quiz', quiz_id=quiz.id)
    else:
        form = QuestionForm()

    return render(request, 'cbt/lecturer_add_question.html', {
        'form': form,
        'quiz': quiz,
    })


@login_required
def lecturer_view_questions(request, quiz_id=None):
    user = request.user
    lecturer = _get_lecturer_or_none(user)

    if user.is_superuser or user.is_staff:
        quizzes = Quiz.objects.all().select_related('course', 'examination', 'examination__department')
    elif lecturer:
        assigned_course_ids = _assigned_course_ids(lecturer)
        quizzes = Quiz.objects.filter(course_id__in=assigned_course_ids).select_related(
            'course', 'examination', 'examination__department'
        )
    else:
        messages.error(request, "Access Denied.")
        return redirect('cbt:main-view')

    selected_quiz = None
    questions = None

    quiz_id = quiz_id or request.GET.get('quiz_id')

    if quiz_id:
        selected_quiz = get_object_or_404(Quiz, id=quiz_id)

        if not _lecturer_is_authorized_for_quiz(user, selected_quiz, lecturer=lecturer):
            messages.error(request, "Access Denied.")
            return redirect('cbt:main-view')

        questions = selected_quiz.question_set.all()

    return render(request, 'cbt/lecturer_view_questions.html', {
        'quizzes': quizzes,
        'selected_quiz': selected_quiz,
        'questions': questions,
    })


@login_required
def export_questions(request, quiz_id, export_type):
    user = request.user
    lecturer = _get_lecturer_or_none(user)
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if not _lecturer_is_authorized_for_quiz(user, quiz, lecturer=lecturer):
        messages.error(request, "Access Denied.")
        return redirect('cbt:main-view')

    questions = quiz.question_set.all()

    # ================= CSV EXPORT =================
    if export_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{quiz.course}_questions.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Question", "Question Type", "Option A", "Option B",
            "Option C", "Option D", "Correct Answer",
        ])

        for q in questions:
            writer.writerow([
                q.content, q.question_type, q.option_a, q.option_b,
                q.option_c, q.option_d, q.correct_answer,
            ])

        return response

    # ================= PDF EXPORT =================
    elif export_type == 'pdf':
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{quiz.course}_questions.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        title = Paragraph(f"<b>{quiz.course} - {quiz.examination}</b>", styles['Heading2'])
        elements.append(title)
        elements.append(Spacer(1, 0.3 * inch))

        for index, q in enumerate(questions, start=1):
            elements.append(Paragraph(f"<b>Q{index}:</b> {q.content}", styles['Normal']))
            elements.append(Spacer(1, 0.1 * inch))

            if q.question_type == 'MCQ':
                elements.append(Paragraph(f"A. {q.option_a}", styles['Normal']))
                elements.append(Paragraph(f"B. {q.option_b}", styles['Normal']))
                elements.append(Paragraph(f"C. {q.option_c}", styles['Normal']))
                elements.append(Paragraph(f"D. {q.option_d}", styles['Normal']))
                elements.append(Spacer(1, 0.1 * inch))

            elements.append(Paragraph(f"<b>Correct Answer:</b> {q.correct_answer}", styles['Normal']))
            elements.append(Spacer(1, 0.3 * inch))

        doc.build(elements)
        return response

    return redirect('cbt:main-view')


# =====================================================================
# Results
# =====================================================================

@login_required
def lecturer_results_view(request):
    user = request.user

    if user.is_staff or user.is_superuser:
        results = QuizResult.objects.select_related(
            'user', 'quiz', 'quiz__examination', 'quiz__course', 'quiz__level'
        ).order_by('-timestamp')

        levels = Level.objects.all()
        exams = Examination.objects.all()

    else:
        lecturer = get_object_or_404(Lecturer, user=user)
        assigned_course_ids = _assigned_course_ids(lecturer)

        results = QuizResult.objects.filter(
            quiz__course_id__in=assigned_course_ids
        ).select_related(
            'user', 'quiz', 'quiz__examination', 'quiz__course', 'quiz__level'
        ).order_by('-timestamp')

        levels = Level.objects.filter(cbt_exams__course_id__in=assigned_course_ids).distinct()
        exams = Examination.objects.filter(
            quiz__course_id__in=assigned_course_ids
        ).distinct()

    exam_id = request.GET.get('examination')
    level_id = request.GET.get('level')

    if exam_id:
        results = results.filter(quiz__examination_id=exam_id)
    if level_id:
        results = results.filter(quiz__level_id=level_id)

    for res in results:
        attempt_count = QuizResult.objects.filter(user=res.user, quiz=res.quiz).count()
        res.is_retake = attempt_count > 1

    return render(request, 'cbt/lecturer_results.html', {
        'results': results,
        'exams': exams,
        'levels': levels,
    })


@login_required
def export_results_csv(request):
    examination = request.GET.get('examination')
    level = request.GET.get('level')

    results = QuizResult.objects.select_related('user', 'quiz', 'quiz__level', 'quiz__examination')

    if examination:
        results = results.filter(quiz__examination_id=examination)
    if level:
        results = results.filter(quiz__level_id=level)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_CBT_results.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Student Name', 'Username', 'Level', 'Examination', 'Semester',
        'Session', 'Course', 'Score (%)', 'Status', 'Date Taken',
    ])

    for res in results:
        writer.writerow([
            res.user.get_full_name() or res.user.username,
            res.user.username,
            res.quiz.level.name if res.quiz.level else '',
            res.quiz.examination.name if res.quiz.examination else '',
            res.quiz.semester,
            res.quiz.session.name if res.quiz.session else '',
            res.quiz.course,
            round(res.score, 1),
            'Passed' if res.passed else 'Failed',
            res.timestamp.strftime('%Y-%m-%d %H:%M'),
        ])

    return response
