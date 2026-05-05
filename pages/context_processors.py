from curriculum.models import SchoolIdentity
from students.models import Student

# If you use receipts later, uncomment
# from payments.models import Receipt


def school_identity(request):
    """
    Tertiary identity resolver:
    - Default school identity
    - Department-level identity override (if mapped)
    """

    # ===============================
    # 1. DEFAULT SCHOOL IDENTITY
    # ===============================
    school_info = SchoolIdentity.objects.filter(is_default=True).first() \
        or SchoolIdentity.objects.first()

    resolver_match = getattr(request, "resolver_match", None)
    student_id = None

    # ===============================
    # 2. DETECT STUDENT CONTEXT
    # ===============================
    if resolver_match:
        kwargs = resolver_match.kwargs

        # A. Student-based pages (ID card, profile, result, etc.)
        if "matric_number" in kwargs:
            student_id = kwargs.get("matric_number")

        # B. Receipt-based pages (optional future use)
        elif "receipt_id" in kwargs or "receipt_pk" in kwargs:
            receipt_id = kwargs.get("receipt_id") or kwargs.get("receipt_pk")

            # If you enable receipts later:
            # receipt = Receipt.objects.filter(pk=receipt_id).select_related(
            #     "payment__student"
            # ).first()
            # if receipt:
            #     student_id = receipt.payment.student.id

    # ===============================
    # 3. LOGGED-IN STUDENT FALLBACK
    # ===============================
    if not student_id and request.user.is_authenticated:
        if hasattr(request.user, "student"):
            student_id = request.user.student.matric_number

    # ===============================
    # 4. APPLY TERITIARY IDENTITY RULE
    # ===============================
    if student_id:
        try:
            student = Student.objects.select_related(
                "department", "programme", "level"
            ).filter(matric_number=student_id).first()

            if student and student.department:
                # 👇 TERITIARY RULE: department overrides school identity
                dept_identity = getattr(student.department, "school_identity", None)

                if dept_identity:
                    school_info = dept_identity

        except Exception:
            pass

    return {
        "school_info": school_info
    }