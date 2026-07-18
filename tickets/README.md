# Tickets App — Tertiary Refactor

## Terminology / role fixes (the actual functional bugs)
- `AUDIENCE_CHOICES`: `'teachers'` → `'lecturers'`.
- `views.ticket_list`: was checking `hasattr(user, 'teacher')`, an attribute that
  doesn't exist on this project's `User` model — so **lecturers never saw
  broadcasts addressed to them**. Fixed to `hasattr(user, 'lecturer')`.
- `context_processor.unread_tickets_count`: same fix, plus the old `else` branch
  assumed any non-student was a "teacher" — now staff/admin without a
  lecturer/student profile just see their own ticket count instead of being
  miscounted as lecturers.
- `create_ticket` email: `request.user.get_full_name` was referenced without
  calling it (`()` missing), so the notification email printed a Python method
  object instead of the sender's name. Fixed, and the hardcoded
  `http://127.0.0.1:8000/...` ticket link is now built with
  `request.build_absolute_uri()` so it resolves correctly on
  PythonAnywhere/cPanel, not just localhost.
- `admin_ticket_detail`: the template had "Assign to Me" and "Mark as Resolved"
  buttons, but the view only ever handled `close_ticket` — those two actions
  silently did nothing. Both are now wired up.
- `apps.py`: `signals.py` existed but was never imported anywhere, so its
  `post_save` receiver never actually connected. Added `ready()` to import it.

## Dependency removal (per "no complex package installation")
- `admin.py` used `django-import-export`'s `ImportExportModelAdmin` — swapped
  for plain `admin.ModelAdmin`. Nothing to `pip install`.
- All 5 templates used `{% load crispy_forms_tags %}` / `{{ form|crispy }}`,
  which needs `django-crispy-forms` **and** a configured template pack
  (e.g. `crispy-bootstrap5`) in `INSTALLED_APPS`/`CRISPY_TEMPLATE_PACK`.
  Replaced with a small reusable partial (`_form_fields.html`) that renders
  each field with its Bootstrap classes (already set directly on the widgets
  in `forms.py`) — zero extra packages.

## Tertiary-fit content
- `CATEGORY_CHOICES` expanded: added **Course Registration**, **Examinations &
  Results**, **Hostel/Accommodation**, **ID Card**, on top of the categories
  that already carried over cleanly (Academic, Financial Aid, Technical
  Support, Facilities, General Inquiry). Existing category values weren't
  renamed, just supplemented, so no data migration risk.
- Ticket detail pages now consistently show the actual name of the staff
  member who replied (tagged "Support Team"), instead of the student-facing
  view saying just "An Admin" while the admin-facing view showed the real
  name — inconsistent before, standardized now.

## Presentation refactor
- The 5 templates each repeated their own near-identical `<style>` block
  (mainly status-badge colors). Centralized into one file:
  `static/tickets/css/tickets.css`, linked from every template instead of
  duplicated inline CSS — one place to restyle going forward.
- Swapped emoji headers (🎫 📝) for Font Awesome icons for a more consistent,
  professional look in line with the rest of the portal.
- Added proper empty states (icon + message + call to action) instead of a
  bare info alert.
- Category is now shown as a column on both the student and admin ticket
  lists (was admin-only before).

## Installing
1. Copy this `tickets/` folder over your existing one (or diff it in).
2. Since `CATEGORY_CHOICES` and `AUDIENCE_CHOICES` changed, run:
   ```bash
   python manage.py makemigrations tickets
   python manage.py migrate
   ```
   This is a metadata-only change (Django stores `choices` on the field
   definition) — no data is altered, but Django will still want a migration
   for it.
3. If `django-crispy-forms` / `django-import-export` aren't used anywhere
   else in your project, you can remove them from `INSTALLED_APPS` and
   `requirements.txt` — this app no longer needs either.
4. Nothing else changes: URLs, template names, and the context processor's
   `unread_count` key are all unchanged, so nothing else in the project
   should need updating.

## Left as-is / worth knowing
- `notify_author_on_response` in `signals.py`: the actual `send_mail(...)`
  call was already commented out in the original and is left that way —
  enabling it changes production email behavior, which wasn't asked for.
  Uncomment it once `DEFAULT_FROM_EMAIL`/SMTP is confirmed working.

## Round 2 — notification bell + reply-status badges

The previous round fixed terminology and dependencies but left the actual
notification/reply-tracking logic as-is. That logic turned out to be
broken in a few connected ways:

- **The core bug**: `unread_count` only ever checked "has this user EVER
  opened this ticket" (a one-way `TicketReadStatus` flag). Once viewed, a
  ticket was considered read forever — so a brand new admin reply on a
  ticket you'd opened once before never re-triggered the bell. Replaced
  with a proper timestamp comparison (last activity vs. your last view)
  in the new `services.py`.
- **Broadcasts never marked read for non-staff**: `ticket_detail`'s old
  condition `if not ticket.is_broadcast or request.user.is_staff` meant
  a student/lecturer viewing a broadcast never got a read-status row
  created at all — broadcasts stayed permanently "unread" for every
  non-staff user, forever inflating their bell count. Fixed to mark read
  for any viewer, any ticket type.
- **`is_admin_response` was hardcoded per-view instead of per-user**: it
  was force-set `True` only in `admin_ticket_detail`, and silently
  defaulted to `False` in the plain `ticket_detail` view — so a staff
  member replying via the wrong URL would have their reply
  misclassified as a student/lecturer comment, breaking the "needs a
  reply" signal. Now set from `request.user.is_staff` in both views.
- **Missing authorization check** (found while working in this exact
  view, not part of the original ask, but worth flagging): `ticket_detail`
  had no ownership check at all — any logged-in user could view any
  other user's ticket by pk. Added a check: visible only to its author,
  staff, or (for broadcasts) users in the addressed audience.

**New: `services.py`** centralizes two distinct concepts so the bell and
the list badges agree with each other:
- `needs_reply` (ticket-level): still open, and the last comment (if any)
  was from the ticket's own author, not staff — i.e. staff hasn't
  responded yet. This is what now drives the "Needs Reply" badge and the
  staff bell count, and it does not disappear just because staff opened
  the ticket without replying.
- `has_unseen_reply` / `has_unseen_broadcast` (viewer-specific): whether
  there's new activity since this particular user last viewed it. Drives
  the "New Reply" badge and the student/lecturer bell count.

**List pages** now show a "Reply Status" (student/lecturer view) or
"Pending Response" (admin view) column with badges: New / New Reply /
Awaiting Response / Needs Reply / Replied — instead of no indicator at
all. Rows with unseen activity are also lightly highlighted.

**Base-template snippets** (outside this app's folder, so not in the
zip — see the corrected versions in the chat response): the nav's
ticket-bell dropdown had malformed/duplicated `<li>` markup, and the
dashboard "Notifications" panel used literal `**bold**` (Markdown syntax,
which does nothing in raw HTML) instead of `<strong>`.

