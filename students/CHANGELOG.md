# Students App — Refactor Changelog

This documents every change made to align this app with the `curriculum`, `finance`,
and `results` apps, plus every real bug found and fixed along the way. Nothing was
rewritten from scratch except where noted — existing working logic (hostel management,
ID cards, search, distribution views) was left untouched.

## Crash bugs fixed (these would raise, not just render wrong)

1. **`forms.py` — `from tkinter import Widget`**: an unused import that crashes on any
   headless server without a display/Tk installed (most Linux production servers).
   Removed.
2. **`forms.py` — `StudentUpdateForm.Meta` specified both `fields = '__all__'` and
   `exclude = (...)`**: Django raises `ImproperlyConfigured` the moment this class is
   imported — a ModelForm can only specify one. Fixed by keeping only `exclude`, and
   removed references to `faculty`/`current_semester`/`graduated`, none of which exist
   on `Student` (Django silently ignores unknown names in `exclude`, so this wasn't
   crashing, just dead weight).
3. **`urls.py` — `alumni_list.html` calls `{% url 'students:readmit_student' %}`, but
   that URL was commented out**: `NoReverseMatch` on every visit to the alumni list
   page. Re-enabled the URL (the view itself was already correct).
4. **`views.py` — `course_registration_view` called `redirect('course-registration')`**
   without the `students:` namespace prefix, and separately called
   `redirect('pages:portal_home')` (underscore) while every other reference in this app
   uses `pages:portal-home` (hyphen). Both fixed.
5. **`views.py` — `promote_students_view` referenced `Level.objects.order_by('rank')`,
   `Level.filter(rank__gt=...)`, and `Student.filter(current_level=...)`** — `Level`
   has no `rank` field and `Student` has no `current_level` field (it's just `level`).
   This view could not have run without raising `FieldError`. Rewritten to have staff
   explicitly pick both the source and target level (no attempt to guess "next level"
   from an ordering that doesn't exist in the schema) — also fixed the accompanying
   `promote_students.html`, which additionally referenced `student.current_level`
   (doesn't exist) and had **no target-level selector in its POST form at all**.
6. **`views.py` — duplicate `export_students_csv` definitions**: the first (dead,
   shadowed) version referenced `s.last_name`, `s.first_name`, and
   `s.graduated_session` directly on `Student` — none of which exist (names live on
   `s.user`; there's no `graduated_session` field). It was never actually called
   (Python just used the second definition), but left as a landmine for future edits.
   Removed the dead version.
7. **`resources.py` — `AppBModelResource`** referenced `attribute='form_teacher'`,
   a field that doesn't exist on `Student`, and wasn't even wired into `admin.py`
   (`StudentsAdmin` never set `resource_class`, so it silently did nothing). Replaced
   with a working `StudentResource` using real fields, and wired it in.
8. **`views.py` — `student_archive`'s session filter was a literal no-op**
   (`if session_filter... : pass`) — the dropdown looked functional but filtered
   nothing. Fixed using the real `GraduationRecord` relation (`graduation_records`),
   since `Student` has no direct session FK — that history lives in `GraduationRecord`.
9. **`views.py` — `MyTeacherDetailView.template_name = 'student/my_teacher_detail.html'`**
   (singular `student/`) — the actual file is at `students/my_teacher_detail.html`.
   Would raise `TemplateDoesNotExist` the one time this view is reached.

## Template field mismatches fixed (rendered silently blank/wrong, not crashes)

Django templates swallow `AttributeError` on missing attributes (resolving to empty
string), so these didn't crash — but they were rendering wrong or fabricated data:

- `student_detail.html` / `student_self_detail.html`: `student.faculty` →
  `student.department.faculty` (Faculty is only reachable through Department);
  `student.current_semester`, `student.phone_number`, `student.address`,
  `student.is_registered`, `student.get_registration_status_display`,
  `student.guardian_relationship` — **none of these fields exist on `Student`**.
  Removed the fabricated ones, replaced the real ones with actual context data.
- `archive.html`: `s.graduated_session` → doesn't exist; replaced with
  `s.graduation_records.all|first` (uses the now-`prefetch_related`'d relation, so
  this doesn't reintroduce an N+1 query across a paginated list).
- `student_self_detail.html` had **mismatched `<div>` nesting** (verified by counting
  open/close tags across every template in this app — this was the only one off).
  Rewritten cleanly rather than patched.

## New integration with curriculum / finance / results

### `course_registration_view`
- Validates the selected total credit units against `curriculum.RegistrationPolicy`
  (via `curriculum.services.registration.validate_unit_load`) **before** touching the
  database — a student can no longer register above/below their programme or level's
  configured unit limits.
- After creating each `CourseRegistration`, calls
  `finance.services.payments.FinanceService.ensure_course_fee_item()` — this is what
  actually bills the student for that course (previously, registering a course never
  created any billable record at all).
- Displays the resolved unit policy (min/max units) and a fee-clearance banner
  (`finance.ExamEligibilityService`) directly on the registration page, so a student
  understands *before* submitting why a course might not end up exam-eligible.

### `StudentSelfDetailView` ("My Profile") and `StudentDetailView` (staff view)
Both now share `students.services.dashboard.build_student_dashboard_context()`, which
pulls:
- Current semester's registered courses, each with live exam eligibility
  (`finance.ExamEligibilityService`).
- Fee clearance summary — every billable item, cleared or not, and whether the
  student is fully cleared for exams overall.
- Published results, semester GPA, and CGPA (`results.services.gpa.GPAService`) —
  unpublished/in-progress results are never shown, matching the results app's own
  publish gate.
- Recent successful payments, each linking to its printable HTML receipt.

Using the **same service** for both the student's own view and the staff view means
there's exactly one place this logic lives — not two slightly-different copies.

### New service: `students/services/dashboard.py`
Deliberately defensive: if `FeeAssignment`/`GradingScheme` data doesn't exist yet for
a given session/semester, these functions return an empty-but-valid structure rather
than raising — a profile page should never 500 just because a student hasn't been
billed or graded yet.

## Dependency note

`students/views.py` now imports from `finance.services` and `curriculum.services` at
module load time (and `results` lazily inside the dashboard service). Make sure
`finance` and `curriculum` apps are migrated and in `INSTALLED_APPS` before `students`
is exercised — if you're following the build order from earlier in this project,
you're already there.

## Left untouched (out of scope, no evidence of a bug)

Hostel management (`hostel_dashboard`, `assign_room`), ID card generation
(`StudentIDCardView`, `BulkStudentIDCardView`), student search/distribution views, and
`context_processors.py` — all reviewed, no issues found, no changes made.
