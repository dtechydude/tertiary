from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget

from .models import Examination, Question, Quiz


class AdminQuizForm(forms.ModelForm):
    """
    Used by Admin/Staff (and, per-course, by the assigned Lecturer) to
    stand up a CBT "sitting" for a Course under a given Examination.

    `session` is intentionally excluded from the form — it is always
    derived from the selected Examination in the view, so an admin can
    never accidentally mismatch a Quiz's session against its parent
    Examination.
    """

    class Meta:
        model = Quiz
        fields = [
            'examination',
            'course',
            'level',
            'semester',
            'number_of_questions',
            'time',
            'required_score_to_pass',
            'start_date',
            'end_date',
            'start_time',
            'end_time',
            'active',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if name == 'active':
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', "End date cannot be before start date.")

        if start_time and end_time and end_time <= start_time:
            self.add_error('end_time', "End time must be later than start time.")

        return cleaned_data


class QuestionForm(forms.ModelForm):

    MCQ_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
    ]

    class Meta:
        model = Question
        fields = [
            'content',
            'question_type',
            'image_url',
            'option_a',
            'option_b',
            'option_c',
            'option_d',
            'correct_answer',
        ]
        widgets = {
            'content': CKEditor5Widget(config_name='extends'),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'image_url': forms.URLInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Paste Google Drive image link (optional)',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in ['option_a', 'option_b', 'option_c', 'option_d']:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

        self.fields['correct_answer'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter correct answer',
        })

        question_type = None
        if self.instance.pk:
            question_type = self.instance.question_type
        elif self.data.get('question_type'):
            question_type = self.data.get('question_type')

        if question_type == 'MCQ':
            self.fields['correct_answer'].widget = forms.Select(
                choices=self.MCQ_CHOICES,
                attrs={'class': 'form-select'},
            )

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get('question_type')

        if question_type == 'MCQ':
            options = {
                'option_a': cleaned_data.get('option_a'),
                'option_b': cleaned_data.get('option_b'),
                'option_c': cleaned_data.get('option_c'),
                'option_d': cleaned_data.get('option_d'),
            }
            missing = [name for name, value in options.items() if not value]
            if missing:
                self.add_error(
                    missing[0],
                    "All four options are required for a Multiple Choice question.",
                )

            correct_answer = cleaned_data.get('correct_answer')
            if correct_answer and correct_answer.strip().upper() not in dict(self.MCQ_CHOICES):
                self.add_error('correct_answer', "Correct answer must be A, B, C, or D.")

        return cleaned_data


class ExaminationForm(forms.ModelForm):
    """
    Optional convenience form for lecturers/staff creating an Examination
    record directly from the CBT app rather than the Django admin.
    """

    class Meta:
        model = Examination
        fields = ['name', 'department', 'level', 'semester', 'session', 'date', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
