# Tertiary E-Learning App

An independent, self-contained Django app for e-learning across a tertiary
institution's schools/faculties — Engineering, Medicine/Nursing, Social
Sciences, Management, and any other programme. Extracted and rebuilt from
the K-12 curriculum app's e-learning module, redesigned around your
existing tertiary academic structure instead of "Standard/Class".

## What changed vs. the K-12 version

| K-12 concept | Tertiary replacement |
|---|---|
| `Level` (a class, e.g. JSS1) + `ELearningSubject` (a subject in that class) | `curriculum.Course` — already carries Programme, Department, Level, Session, Semester, so no second "subject" layer is needed |
| `Lesson` | `CourseMaterial` — a lecture note, slide deck, video, or link attached to a `Course` |
| `Comment` / `Reply` | `MaterialComment` / `MaterialReply` — unchanged in spirit, just renamed |
| Rich text editor / embed_video dependencies | Removed. Plain `TextField` for descriptions and a plain `URLField` for videos, with a best-effort YouTube embed in the template — nothing to install or configure on a restricted host |
| (none) | `OnlineClassLink` — new model for Google Classroom / Microsoft Teams links |

Nothing in your existing `curriculum` app was modified. This app only
references `curriculum.Course` (and, through it, `CourseAssignment` /
`CourseRegistration`) via standard Django foreign keys.

## Files

```
tertiary_elearning/
├── models.py          # CourseMaterial, OnlineClassLink, MaterialComment, MaterialReply
├── forms.py            # CourseMaterialForm, OnlineClassLinkForm, comment/reply forms
├── views.py             # dashboard, list/detail, create/update/delete, class-link CRUD
├── permissions.py       # who can view/manage a course's e-learning content
├── urls.py               # url routes, namespaced "tertiary_elearning"
├── admin.py               # Django admin registration
├── templates/tertiary_elearning/   # simple Bootstrap-5 templates (CDN, no build step)
└── migrations/             # empty — run makemigrations after install (see below)
```

## Installation

1. Copy the `tertiary_elearning/` folder into your Django project root
   (next to `curriculum`, `students`, `staff`, etc.).

2. Add to `INSTALLED_APPS` in `settings.py`:
   ```python
   INSTALLED_APPS = [
       ...
       "curriculum",
       "students",
       "staff",
       "tertiary_elearning",
   ]
   ```

3. Include the URLs in your project's root `urls.py`:
   ```python
   urlpatterns = [
       ...
       path("elearning/", include("tertiary_elearning.urls")),
   ]
   ```

4. Make sure `MEDIA_URL` / `MEDIA_ROOT` are configured (for file uploads —
   slides, PDFs) and, in production, that your root `urls.py` serves media
   correctly for your host (see the PythonAnywhere/cPanel notes below).

5. Run migrations:
   ```bash
   python manage.py makemigrations tertiary_elearning
   python manage.py migrate
   ```

6. Visit `/elearning/` while logged in as a student, lecturer, or staff.

## Access rules (no new roles needed)

- **Manage** (add/edit/delete material, add class links): Django staff/
  superuser, or a lecturer with a `curriculum.CourseAssignment` row for
  that course.
- **View**: anyone who can manage, plus a student with a
  `curriculum.CourseRegistration` row for that course.

This means access automatically follows your existing registration and
course-assignment records — no separate "enrol in e-learning" step.

## Connecting to Google Classroom (free, Education tier)

No API keys, no OAuth — just a link:

1. In Google Classroom, open the class → **Settings** → copy the
   **Invite link** (and note the class code shown on the Stream page).
2. In the e-learning app, open a course → **Add Class Link** → choose
   **Google Classroom** → paste the invite link (and optionally the
   class code) → Save.
3. Students see a **Join** button that opens Google Classroom directly.

## Connecting to Microsoft Teams (Teams for Education, free tier)

1. In Teams, open the class team → **Get link to team** (or, for a
   specific meeting, **Copy meeting link**).
2. In the e-learning app, **Add Class Link** → choose **Microsoft
   Teams** → paste the link → Save.

Both integrations are intentionally "static link" based rather than API
based — this keeps the app deployable on constrained/free hosting without
credentials, webhooks, or background jobs, while still giving students a
one-click join experience.

## Hosting notes — PythonAnywhere (free tier) / cPanel Python App

- **No extra third-party packages required** beyond Django itself — the
  app deliberately avoids rich-text-editor and video-embed packages that
  can be awkward to install on shared/free hosting.
- **Media files**: on PythonAnywhere free tier, set `MEDIA_ROOT` to a
  path under your home directory and add a static/media file mapping in
  the **Web** tab (`/media/` → `/home/<username>/<project>/media`). On
  cPanel, point the equivalent alias in your Python App's static file
  mappings.
- **Static files** (Bootstrap, etc.) are loaded from a CDN in the
  provided templates, so there is no `collectstatic`/build step required
  for the UI to render — useful on hosts with restricted outbound pip
  installs.
- File upload size: both PythonAnywhere free tier and typical shared
  cPanel plans cap request/file sizes and total storage — keep lecture
  slides/PDFs reasonably sized, or use the `video_url` / `external_link`
  fields to link out to Google Drive/YouTube instead of uploading large
  video files directly.
