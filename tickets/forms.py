# tickets/forms.py
#
# Deliberately plain Django ModelForms with Bootstrap classes set directly
# on the widgets. The original templates rendered these with
# django-crispy-forms ({{ form|crispy }}), which needs an extra package
# (django-crispy-forms + a template pack like crispy-bootstrap5) installed
# and configured in INSTALLED_APPS/CRISPY_TEMPLATE_PACK. That's one more
# thing to get right on a constrained host (PythonAnywhere free tier /
# shared cPanel), so it's dropped here in favour of manually-styled
# widgets rendered with a small reusable template partial
# (see templates/tickets/_form_fields.html).

from django import forms
from .models import Ticket, Comment


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['title', 'category', 'priority', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Briefly describe your issue',
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Give as much detail as possible — matric/staff ID, course code, dates, etc.',
            }),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Type your response...',
            }),
        }
        labels = {'text': ''}


# Admin only broadcast form
class BroadcastTicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'audience']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'audience': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].label = "Broadcast Subject"
        self.fields['description'].label = "Message Content"
        self.fields['audience'].label = "Send To"
