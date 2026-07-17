# from curriculum.models import SchoolIdentity, AcademicIdentityMapping
# from students.models import Student
# # Import your Receipt model correctly
# from payments.models import Receipt 

# def school_identity(request):
#     # 1. Default fallback
#     school_info = SchoolIdentity.objects.filter(is_default=True).first() or SchoolIdentity.objects.first()

#     resolver_match = request.resolver_match
#     student_id = None

#     if resolver_match:
#         kwargs = resolver_match.kwargs
        
#         # A. URLS WITH 'student_id' (ID Cards, Invoices)
#         if 'student_id' in kwargs:
#             student_id = kwargs.get('student_id')
        
#         # B. URLS WITH 'receipt_id' or 'receipt_pk' (Receipts)
#         elif 'receipt_id' in kwargs or 'receipt_pk' in kwargs:
#             r_id = kwargs.get('receipt_id') or kwargs.get('receipt_pk')
#             # Changed logic: Accessing student through the 'payment' relation
#             receipt = Receipt.objects.filter(pk=r_id).select_related('payment').first()
#             if receipt and receipt.payment:
#                 # Assuming the Payment model has the 'student' field
#                 student_id = receipt.payment.student.id

#     # C. LOGGED-IN STUDENT
#     if not student_id and request.user.is_authenticated:
#         if hasattr(request.user, 'student') and request.user.student:
#             student_id = request.user.student.id

#     # 4. Final ID Lookup and Identity Swap
#     if student_id:
#         try:
#             student = Student.objects.filter(pk=student_id).only('current_class').first()
#             if student and student.current_class:
#                 # Use current_class.id directly
#                 standard_id = getattr(student.current_class, 'id', student.current_class)
#                 mapping = StandardIdentity.objects.filter(standard_id=standard_id).first()
#                 if mapping:
#                     school_info = mapping.school_identity
#         except Exception:
#             pass 

#     return {'school_info': school_info}


# curriculum/context_processors.py
from .models import SchoolIdentity, AcademicIdentityMapping


def school_info(request):
    identity = None
    user = getattr(request, "user", None)

    if user and user.is_authenticated:
        profile = getattr(user, "student", None) or getattr(user, "lecturer", None)
        department = getattr(profile, "department", None) if profile else None

        if department is not None:
            mapping = (
                AcademicIdentityMapping.objects.filter(department=department).first()
                or AcademicIdentityMapping.objects.filter(faculty=department.faculty).first()
            )
            if mapping:
                identity = mapping.school_identity

    if identity is None:
        identity = SchoolIdentity.objects.filter(is_default=True).first()

    return {"school_info": identity}



# tickets/context_processors.py
from .models import Ticket, TicketReadStatus
from django.db.models import Q

def unread_tickets_count(request):
    """
    Returns the count of unread tickets for the logged-in user.
    """
    unread_count = 0
    if request.user.is_authenticated:
        read_tickets_ids = TicketReadStatus.objects.filter(user=request.user).values_list('ticket_id', flat=True)

        if request.user.is_staff:
            # Admins see all unread tickets
            all_tickets = Ticket.objects.all()
        elif hasattr(request.user, 'student'):
            # Students see their own unread tickets and relevant broadcasts
            all_tickets = Ticket.objects.filter(Q(author=request.user) | Q(is_broadcast=True, audience='students'))
        else:
            # Other users (e.g., teachers) see their own unread tickets and relevant broadcasts
            all_tickets = Ticket.objects.filter(Q(author=request.user) | Q(is_broadcast=True, audience='teachers'))

        unread_count = all_tickets.exclude(pk__in=read_tickets_ids).count()

    return {'unread_count': unread_count}