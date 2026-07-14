# Setting Up Graduation Policies & Classifications (Results App v2)

This covers the models added to answer: minimum CGPA to graduate, named
classification bands (e.g. "Upper Credit", "Second Class Upper Division"), and how
they connect to `curriculum.Programme`.

## New models

- **`GraduationPolicy`** (one per `Programme`) — `minimum_cgpa_to_graduate`
  (e.g. `2.00`, `2.50`), optionally `minimum_credit_units_to_graduate`, optionally
  `max_sessions_to_complete`.
- **`ClassificationScheme`** — a named, reusable set of bands (e.g. "Standard Degree
  Classification" or "Diploma Classification"). Mark one `is_default=True` as your
  institution-wide fallback.
- **`ClassificationBand`** — one row per named class within a scheme: `name` (e.g.
  "Upper Credit"), `min_cgpa`, `max_cgpa`, `is_graduating_class`.
- **`ProgrammeClassificationScheme`** — which scheme a given `Programme` uses. If
  unset, falls back to the scheme marked `is_default=True`.
- **`services/graduation.py` → `GraduationService`** — the only place that computes
  eligibility/classification. Nothing hardcodes a CGPA cutoff or a band name.

## Setup order

1. **Create a `ClassificationScheme`**, e.g. "Diploma Classification".
2. **Add its `ClassificationBand`s** (inline on the same admin page), e.g.:
   | name | min_cgpa | max_cgpa |
   |---|---|---|
   | Distinction | 3.50 | 4.00 |
   | Upper Credit | 3.00 | 3.49 |
   | Lower Credit | 2.50 | 2.99 |
   | Pass | 2.00 | 2.49 |

   The **lowest band's `min_cgpa`** is effectively your graduating floor for
   classification purposes — but graduation eligibility itself is governed
   separately by step 3, so a programme can require more than "reaches the lowest
   classification band" if desired (e.g. also needing enough credit units).
3. **Create a `GraduationPolicy`** for each `Programme`, setting
   `minimum_cgpa_to_graduate` to match your lowest band (`2.00` in the table above),
   or higher if you want a stricter graduation floor than your lowest named class.
4. **(Optional) Create a `ProgrammeClassificationScheme`** per programme if it
   should use a scheme other than your default one (e.g. a degree programme using
   "First Class / Second Upper / ..." while diploma programmes use "Distinction /
   Upper Credit / ...").

## Using it

```python
from results.services.graduation import GraduationService

evaluation = GraduationService.evaluate(student)
evaluation.cgpa                        # Decimal, e.g. 3.62
evaluation.is_eligible_to_graduate     # bool
evaluation.classification              # "Upper Credit", or None if not eligible
evaluation.meets_cgpa_requirement      # bool
evaluation.meets_credit_requirement    # bool
```

Or via the API: `GET /api/v1/students/<student_id>/graduation-evaluation/`
(the student can view their own; staff need the `results.publish_result` permission
to view anyone else's).

## Recommended next step (not done here — needs your say-so)

`students.GraduationRecord.remarks` is currently a free-text `CharField` ("Optional
remarks (Distinction, Upper Credit, etc.)"). Once a registrar finalises a student's
graduation, the natural flow is:

```python
evaluation = GraduationService.evaluate(student)
if evaluation.is_eligible_to_graduate:
    GraduationRecord.objects.create(
        student=student, session=current_session, programme=student.programme,
        department=student.department, level_completed=student.level,
        date_graduated=today, remarks=evaluation.classification,
    )
```

That works today with zero changes to the `students` app. If you'd like it more
strongly typed later (a proper FK from `GraduationRecord` to `ClassificationBand`
instead of a free-text remark), say so and I'll patch the `students` app the same
way — additively, with a data migration for existing records.
