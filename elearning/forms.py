from django import forms

from .models import CourseMaterial, MaterialComment, MaterialReply, OnlineClassLink


class CourseMaterialForm(forms.ModelForm):
    class Meta:
        model = CourseMaterial
        fields = (
            "title",
            "material_type",
            "week_number",
            "description",
            "video_url",
            "file",
            "external_link",
            "is_published",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Introduction to Cell Biology"}),
            "material_type": forms.Select(attrs={"class": "form-select"}),
            "week_number": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 5, "placeholder": "Lecture summary / notes (plain text)"}
            ),
            "video_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://youtube.com/..."}),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "external_link": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not any(
            [
                cleaned_data.get("description"),
                cleaned_data.get("video_url"),
                cleaned_data.get("file"),
                cleaned_data.get("external_link"),
            ]
        ):
            raise forms.ValidationError(
                "Add at least one of: description, video link, file, or external link."
            )
        return cleaned_data


class OnlineClassLinkForm(forms.ModelForm):
    class Meta:
        model = OnlineClassLink
        fields = ("platform", "label", "join_link", "class_code", "is_active")
        widgets = {
            "platform": forms.Select(attrs={"class": "form-select"}),
            "label": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Weekly Lecture"}),
            "join_link": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://classroom.google.com/c/..."}),
            "class_code": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. ab12cd3 (optional)"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class MaterialCommentForm(forms.ModelForm):
    class Meta:
        model = MaterialComment
        fields = ("body",)
        labels = {"body": "Ask a question / leave a note"}
        widgets = {
            "body": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Type your comment..."}
            ),
        }


class MaterialReplyForm(forms.ModelForm):
    class Meta:
        model = MaterialReply
        fields = ("body",)
        labels = {"body": "Reply"}
        widgets = {
            "body": forms.Textarea(
                attrs={"class": "form-control", "rows": 2, "placeholder": "Type your reply..."}
            ),
        }
