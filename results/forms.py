from django import forms

from .models import Result
from .services.approvals import ACTION_LABELS

# If your app already has a forms.py, merge this content into it rather
# than overwriting the existing file.


class ApprovalFilterForm(forms.Form):
    """
    Filters for the approval queue. All fields are optional — an empty
    form just shows everything the user is allowed to act on/see.
    """
    # STATUS_CHOICES = (("", "All statuses"),) + Result.Status.choices
    STATUS_CHOICES = [("", "All statuses")] + list(Result.Status.choices)

    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False)
    session = forms.ModelChoiceField(queryset=None, required=False, empty_label="All sessions")
    semester = forms.ModelChoiceField(queryset=None, required=False, empty_label="All semesters")
    course = forms.ModelChoiceField(queryset=None, required=False, empty_label="All courses")
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={"placeholder": "Matric number, student name, or course code"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Imported lazily and assigned here (rather than as class-level
        # querysets) so this form doesn't trigger a DB query at import
        # time and always reflects current data.
        from curriculum.models import Session, Semester,Course # adjust import path to match your project layout

        self.fields["session"].queryset = Session.objects.all().order_by("-id")
        self.fields["semester"].queryset = Semester.objects.all()
        self.fields["course"].queryset = Course.objects.all().order_by("course_code")

        for name, field in self.fields.items():
            css = "form-select form-select-sm" if isinstance(field, forms.ModelChoiceField) or name == "status" else "form-control form-control-sm"
            field.widget.attrs.setdefault("class", css)


class BulkActionForm(forms.Form):
    """
    Validates the action selected in the approval queue's bulk toolbar
    and the checkboxes ticked in the results table. The actual
    permission check for the chosen action happens in the view, since
    it depends on request.user.
    """
    ACTION_CHOICES = [(key, ACTION_LABELS[key]) for key in ACTION_LABELS]

    action = forms.ChoiceField(choices=ACTION_CHOICES)
    result_ids = forms.ModelMultipleChoiceField(queryset=Result.objects.all())
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Reason for returning these results (optional but recommended)"}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("action") == "return" and not cleaned.get("note"):
            self.add_error("note", "Please add a short note explaining what needs correcting.")
        return cleaned


class ReturnReasonForm(forms.Form):
    """Standalone reason form used on the single-result detail page."""
    note = forms.CharField(
        label="Reason for returning this result",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )