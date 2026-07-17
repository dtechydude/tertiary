from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render

from curriculum.models import Course

from .forms import (
    CourseMaterialForm,
    MaterialCommentForm,
    MaterialReplyForm,
    OnlineClassLinkForm,
)
from .models import CourseMaterial, MaterialComment, OnlineClassLink
from .permissions import (
    assigned_courses_for_lecturer,
    can_manage_course,
    can_view_course,
    registered_courses_for_student,
)


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------

@login_required
def my_elearning_dashboard(request):
    """
    Landing page: a student sees the courses they're registered for
    (with material + live-class counts); a lecturer/staff member sees
    the courses they're assigned to teach. Works for Engineering,
    Medicine/Nursing, Social Sciences, Management — any programme —
    since it's driven entirely by existing registrations/assignments.
    """
    user = request.user
    courses = Course.objects.none()

    student = getattr(user, "student", None)
    lecturer = getattr(user, "lecturer", None)

    if user.is_staff or user.is_superuser:
        courses = Course.objects.all().order_by("course_code")
    elif lecturer is not None:
        courses = assigned_courses_for_lecturer(lecturer).order_by("course_code")
    elif student is not None:
        courses = registered_courses_for_student(student).order_by("course_code")

    course_rows = [
        {
            "course": course,
            "material_count": course.elearning_materials.filter(is_published=True).count(),
            "live_class_count": course.online_class_links.filter(is_active=True).count(),
        }
        for course in courses
    ]

    return render(
        request,
        "elearning/dashboard.html",
        {"course_rows": course_rows, "is_manager": user.is_staff or lecturer is not None},
    )


# ---------------------------------------------------------------------
# Course material list / detail
# ---------------------------------------------------------------------

@login_required
def course_material_list(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if not can_view_course(request.user, course):
        raise PermissionDenied("You are not registered for or assigned to this course.")

    can_manage = can_manage_course(request.user, course)
    materials = course.elearning_materials.all()
    if not can_manage:
        materials = materials.filter(is_published=True)

    online_links = course.online_class_links.filter(is_active=True)

    return render(
        request,
        "elearning/material_list.html",
        {
            "course": course,
            "materials": materials,
            "online_links": online_links,
            "can_manage": can_manage,
        },
    )


@login_required
def course_material_detail(request, pk):
    material = get_object_or_404(CourseMaterial, pk=pk)
    course = material.course
    if not can_view_course(request.user, course):
        raise PermissionDenied("You are not registered for or assigned to this course.")

    if request.method == "POST" and "submit_comment" in request.POST:
        comment_form = MaterialCommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.material = material
            comment.author = request.user
            comment.save()
            return redirect("elearning:material_detail", pk=material.pk)
    else:
        comment_form = MaterialCommentForm()

    if request.method == "POST" and "submit_reply" in request.POST:
        reply_form = MaterialReplyForm(request.POST)
        comment_id = request.POST.get("comment_id")
        parent_comment = get_object_or_404(MaterialComment, pk=comment_id, material=material)
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.comment = parent_comment
            reply.author = request.user
            reply.save()
            return redirect("elearning:material_detail", pk=material.pk)
    else:
        reply_form = MaterialReplyForm()

    return render(
        request,
        "elearning/material_detail.html",
        {
            "material": material,
            "course": course,
            "comments": material.comments.all(),
            "comment_form": comment_form,
            "reply_form": reply_form,
            "can_manage": can_manage_course(request.user, course),
        },
    )


# ---------------------------------------------------------------------
# Course material create / update / delete  (lecturer / staff only)
# ---------------------------------------------------------------------

@login_required
def course_material_create(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if not can_manage_course(request.user, course):
        raise PermissionDenied("Only the assigned lecturer or an admin can add material.")

    if request.method == "POST":
        form = CourseMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.course = course
            material.uploaded_by = request.user
            material.save()
            messages.success(request, "Material uploaded.")
            return redirect("elearning:material_list", course_id=course.id)
    else:
        form = CourseMaterialForm()

    return render(
        request,
        "elearning/material_form.html",
        {"form": form, "course": course, "mode": "create"},
    )


@login_required
def course_material_update(request, pk):
    material = get_object_or_404(CourseMaterial, pk=pk)
    if not can_manage_course(request.user, material.course):
        raise PermissionDenied("Only the assigned lecturer or an admin can edit material.")

    if request.method == "POST":
        form = CourseMaterialForm(request.POST, request.FILES, instance=material)
        if form.is_valid():
            form.save()
            messages.success(request, "Material updated.")
            return redirect("elearning:material_detail", pk=material.pk)
    else:
        form = CourseMaterialForm(instance=material)

    return render(
        request,
        "elearning/material_form.html",
        {"form": form, "course": material.course, "mode": "update"},
    )


@login_required
def course_material_delete(request, pk):
    material = get_object_or_404(CourseMaterial, pk=pk)
    course = material.course
    if not can_manage_course(request.user, course):
        raise PermissionDenied("Only the assigned lecturer or an admin can delete material.")

    if request.method == "POST":
        material.delete()
        messages.success(request, "Material deleted.")
        return redirect("elearning:material_list", course_id=course.id)

    return render(
        request, "elearning/material_confirm_delete.html", {"material": material}
    )


# ---------------------------------------------------------------------
# Google Classroom / Microsoft Teams links (lecturer / staff only)
# ---------------------------------------------------------------------

@login_required
def online_class_link_create(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if not can_manage_course(request.user, course):
        raise PermissionDenied("Only the assigned lecturer or an admin can add a class link.")

    if request.method == "POST":
        form = OnlineClassLinkForm(request.POST)
        if form.is_valid():
            link = form.save(commit=False)
            link.course = course
            link.created_by = request.user
            link.save()
            messages.success(request, "Online class link added.")
            return redirect("elearning:material_list", course_id=course.id)
    else:
        form = OnlineClassLinkForm()

    return render(
        request,
        "elearning/online_link_form.html",
        {"form": form, "course": course, "mode": "create"},
    )


@login_required
def online_class_link_update(request, pk):
    link = get_object_or_404(OnlineClassLink, pk=pk)
    if not can_manage_course(request.user, link.course):
        raise PermissionDenied("Only the assigned lecturer or an admin can edit this link.")

    if request.method == "POST":
        form = OnlineClassLinkForm(request.POST, instance=link)
        if form.is_valid():
            form.save()
            messages.success(request, "Online class link updated.")
            return redirect("elearning:material_list", course_id=link.course_id)
    else:
        form = OnlineClassLinkForm(instance=link)

    return render(
        request,
        "elearning/online_link_form.html",
        {"form": form, "course": link.course, "mode": "update"},
    )


@login_required
def online_class_link_delete(request, pk):
    link = get_object_or_404(OnlineClassLink, pk=pk)
    course_id = link.course_id
    if not can_manage_course(request.user, link.course):
        raise PermissionDenied("Only the assigned lecturer or an admin can remove this link.")

    if request.method == "POST":
        link.delete()
        messages.success(request, "Online class link removed.")
        return redirect("elearning:material_list", course_id=course_id)

    return render(
        request, "elearning/online_link_confirm_delete.html", {"link": link}
    )
