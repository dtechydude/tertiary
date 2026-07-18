# from curriculum.models import SchoolIdentity
# from students.models import Student

# # If you use receipts later, uncomment
# # from payments.models import Receipt


# def school_identity(request):
#     """
#     Tertiary identity resolver:
#     - Default school identity
#     - Department-level identity override (if mapped)
#     """

#     # ===============================
#     # 1. DEFAULT SCHOOL IDENTITY
#     # ===============================
#     school_info = SchoolIdentity.objects.filter(is_default=True).first() \
#         or SchoolIdentity.objects.first()

#     resolver_match = getattr(request, "resolver_match", None)
#     student_id = None

#     # ===============================
#     # 2. DETECT STUDENT CONTEXT
#     # ===============================
#     if resolver_match:
#         kwargs = resolver_match.kwargs

#         # A. Student-based pages (ID card, profile, result, etc.)
#         if "matric_number" in kwargs:
#             student_id = kwargs.get("matric_number")

#         # B. Receipt-based pages (optional future use)
#         elif "receipt_id" in kwargs or "receipt_pk" in kwargs:
#             receipt_id = kwargs.get("receipt_id") or kwargs.get("receipt_pk")

#             # If you enable receipts later:
#             # receipt = Receipt.objects.filter(pk=receipt_id).select_related(
#             #     "payment__student"
#             # ).first()
#             # if receipt:
#             #     student_id = receipt.payment.student.id

#     # ===============================
#     # 3. LOGGED-IN STUDENT FALLBACK
#     # ===============================
#     if not student_id and request.user.is_authenticated:
#         if hasattr(request.user, "student"):
#             student_id = request.user.student.matric_number

#     # ===============================
#     # 4. APPLY TERITIARY IDENTITY RULE
#     # ===============================
#     if student_id:
#         try:
#             student = Student.objects.select_related(
#                 "department", "programme", "level"
#             ).filter(matric_number=student_id).first()

#             if student and student.department:
#                 # 👇 TERITIARY RULE: department overrides school identity
#                 dept_identity = getattr(student.department, "school_identity", None)

#                 if dept_identity:
#                     school_info = dept_identity

#         except Exception:
#             pass

#     return {
#         "school_info": school_info
#     }




# # curriculum/context_processors.py
# from curriculum.models import SchoolIdentity, AcademicIdentityMapping


# def school_info(request):
#     identity = None
#     user = getattr(request, "user", None)

#     if user and user.is_authenticated:
#         profile = getattr(user, "student", None) or getattr(user, "lecturer", None)
#         department = getattr(profile, "department", None) if profile else None

#         if department is not None:
#             mapping = (
#                 AcademicIdentityMapping.objects.filter(department=department).first()
#                 or AcademicIdentityMapping.objects.filter(faculty=department.faculty).first()
#             )
#             if mapping:
#                 identity = mapping.school_identity

#     if identity is None:
#         identity = SchoolIdentity.objects.filter(is_default=True).first()

#     return {"school_info": identity}


# # curriculum/context_processors.py
# """
# Resolves the school's branding/contact identity for the current request.

# Returns BOTH `school_info` and `school_identity` pointing at the SAME
# resolved SchoolIdentity object. Several existing templates were written
# against one name or the other (the ID card templates use
# `school_identity`; most other pages — help center, contact support,
# e-learning — use `school_info`). Previously these were two separate
# context processors, each recomputing independently: wasteful (duplicate
# queries every request), and fragile — since both returned a `school_info`
# key, whichever was listed later in TEMPLATES['OPTIONS']['context_processors']
# silently won, with no error to indicate the other one's logic was being
# ignored entirely.

# Resolution order:
#   1. If the URL resolved a `matric_number` kwarg — an ID card / result
#      page rendering a *specific* student, who may not be the logged-in
#      user at all (e.g. staff viewing/printing someone else's ID card) —
#      resolve from THAT student's department/faculty mapping.
#   2. Otherwise, resolve from the logged-in user's own student/lecturer
#      profile's department/faculty mapping.
#   3. Fall back to the default SchoolIdentity, then to any identity that
#      exists, so a page never renders with no identity at all.
# """

# from curriculum.models import AcademicIdentityMapping, SchoolIdentity


# def _mapped_identity_for_department(department):
#     """Department-specific identity if mapped, else its faculty's, else None."""
#     if department is None:
#         return None
#     mapping = (
#         AcademicIdentityMapping.objects.select_related("school_identity")
#         .filter(department=department)
#         .first()
#         or AcademicIdentityMapping.objects.select_related("school_identity")
#         .filter(faculty=department.faculty)
#         .first()
#     )
#     return mapping.school_identity if mapping else None


# def school_info(request):
#     identity = None

#     # 1. A specific student is being rendered via the URL (may not be the
#     #    logged-in user — e.g. an admin viewing/printing another
#     #    student's ID card).
#     resolver_match = getattr(request, "resolver_match", None)
#     matric_number = resolver_match.kwargs.get("matric_number") if resolver_match else None

#     if matric_number:
#         # Local import: avoids a hard module-load-time dependency between
#         # curriculum and students (context processors load at Django
#         # startup via settings.py, before it's guaranteed every app's
#         # models are ready — a lazy import here sidesteps that risk
#         # entirely regardless of how the two apps happen to reference
#         # each other elsewhere).
#         from students.models import Student

#         target_student = (
#             Student.objects.select_related("department__faculty")
#             .filter(matric_number=matric_number)
#             .first()
#         )
#         if target_student:
#             identity = _mapped_identity_for_department(target_student.department)

#     # 2. Otherwise, the logged-in user's own department (student or lecturer).
#     if identity is None and request.user.is_authenticated:
#         profile = getattr(request.user, "student", None) or getattr(request.user, "lecturer", None)
#         department = getattr(profile, "department", None)
#         identity = _mapped_identity_for_department(department)

#     # 3. Fall back to the default identity, then to any identity at all.
#     if identity is None:
#         identity = SchoolIdentity.objects.filter(is_default=True).first() or SchoolIdentity.objects.first()

#     return {"school_info": identity, "school_identity": identity}


# pages/context_processors.py
#
# Lives in `pages`, not `curriculum` — curriculum only holds the shared
# resolver (curriculum/utils/identity.py); this is the actual context
# processor registered in settings.py.
"""
Resolves the school's branding/contact identity for the current request,
reusing the single canonical resolver in curriculum.utils.identity so
this logic only ever lives in one place.

Resolution order:
  1. If the URL resolved a `matric_number` kwarg — an ID card / result
     page rendering a *specific* student, who may not be the logged-in
     user (e.g. staff viewing/printing another student's card) — resolve
     from THAT student's department.
  2. Otherwise, the logged-in user's own student/lecturer department.
  get_school_identity_for_department() already falls back to the default
  identity (then any identity at all) internally, so this function is
  guaranteed to return something as long as at least one SchoolIdentity
  row exists.
"""

from curriculum.utils.identity import get_school_identity_for_department


def school_info(request):
    resolver_match = getattr(request, "resolver_match", None)
    matric_number = resolver_match.kwargs.get("matric_number") if resolver_match else None

    if matric_number:
        # Local import: context processors load at Django startup via
        # settings.py, before every app is guaranteed ready — a lazy
        # import here sidesteps any circular-import risk between the
        # pages/curriculum/students apps.
        from students.models import Student

        target_student = (
            Student.objects.select_related("department__faculty")
            .filter(matric_number=matric_number)
            .first()
        )
        if target_student:
            identity = get_school_identity_for_department(target_student.department)
            return {"school_info": identity, "school_identity": identity}

    department = None
    if request.user.is_authenticated:
        profile = getattr(request.user, "student", None) or getattr(request.user, "lecturer", None)
        department = getattr(profile, "department", None)

    identity = get_school_identity_for_department(department)
    return {"school_info": identity, "school_identity": identity}