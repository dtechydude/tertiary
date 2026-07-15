from django import forms

from .models import Student


class StudentRegisterForm(forms.ModelForm):

    class Meta:
        model = Student
        fields = "__all__"


# TERTIARY LOGIC ======================================

class StudentUpdateForm(forms.ModelForm):
    """
    Form for Admin Staff: focuses on bio-data, contact info, and medicals.
    Excludes sensitive academic and financial fields, which only a
    superuser/registrar should be able to change (see
    SuperUserStudentUpdateForm below).

    NOTE: a ModelForm's Meta may specify EITHER `fields` OR `exclude`,
    never both — specifying both raises ImproperlyConfigured at class
    definition time, which is what was happening here before. Only
    `exclude` is needed to whitelist-by-exclusion.
    """
    class Meta:
        model = Student
        exclude = (
            "user", "matric_number", "student_status",
            "department", "programme", "level",
            "date_admitted", "fee_balance",
        )
        widgets = {
            "DOB": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }


class SuperUserStudentUpdateForm(forms.ModelForm):
    """
    Form for Registrar/Superuser: has the power to change levels,
    departments, and finances.
    """
    class Meta:
        model = Student
        exclude = ("user",)  # only exclude the User relationship itself
        widgets = {
            "DOB": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }
