# Results App v2 — What Changed and Why

## Bugs fixed in the old app (worth knowing even if you'd already found them)

1. **`views.py` imported a class that didn't exist.** `from .services.grading import GradingService`
   but `services/grading.py` only defined a function, `process_student_result`. Same mismatch in the
   commented-out `admin.py`. The lecturer score-submission flow and the admin `save_model` hook were
   both broken.
2. **`services/gpa.py` referenced `Result.credit_unit`**, but migration `0004_remove_result_credit_unit`
   had removed that field from `Result`. GPA/CGPA calculation was throwing `AttributeError` at runtime.
3. **`services/result_processing.py` had two bad imports**: `from result.models import Result` (wrong
   app name) and `from .models import CourseRegistration, CourseAssignment` (those live in
   `curriculum.models`, not `results.models`). This file could not have run.
4. **`Examination.__str__` referenced `self.promgramme`** (typo) instead of `self.programme`.
5. **DRF object-level permission never actually ran.** `IsCourseLecturer.has_object_permission` existed,
   but `ResultEntryView.post` looped over scores manually and never called
   `self.check_object_permissions(request, result)` — so the per-object lecturer check was dead code.
6. `serializers.py` was empty; the API built raw dicts by hand instead of using DRF serializers.

## Architectural changes

| Old | New | Why |
|---|---|---|
| `GradingSetting` (tma_weight/exam_weight per Programme) | `GradingScheme` + `GradingSchemeComponent` + `AssessmentComponent` | Your spec requires configurable component *names*, weights, and max scores (Assignment, Quiz, Test, Practical, Mid-Semester, Examination — any mix), not a fixed two-part split. A scheme is now reusable across programmes instead of being locked 1:1 to one. |
| `GradeScale` (scoped to Programme) | `GradeBoundary` (scoped to `GradingScheme`) | Multiple programmes sharing a scheme now share its grade boundaries automatically; boundaries also self-validate against overlaps. |
| `Result.tma_score` / `Result.exam_score` (fixed columns) | `ResultScore` (one row per `AssessmentComponent`, FK to `Result`) | Adding a new component (e.g. "Practical") no longer needs a schema migration. |
| `Result.is_submitted` (single boolean) | `Result.status` (`draft → submitted → hod_approved → dean_approved → registrar_approved → published`, plus `returned`) + `is_published` | Matches the required Lecturer → HOD → Dean → Registrar → Published workflow instead of a single flag. |
| No audit trail | `ResultAuditLog` | Every workflow transition and every score edit is now logged (actor, from/to status, timestamp, remarks) — satisfies the project's audit requirement. If/when your shared `audit` app is finalised, have `ResultWorkflowService.log()` also write there instead of/alongside this table. |
| No scheme resolution | `ProgrammeGradingScheme`, `CourseGradingScheme` + `GradingService.resolve_scheme()` | Course-level override → Programme default → global default. A course never needs a grading scheme hand-picked unless it's actually different from its programme's norm. |
| `results.Curriculum` model (program/level/semester/course/is_core) | **Removed** | This duplicated fields already on `curriculum.Course` (which has `programme`, `level`, `semester`, `department` directly) and doesn't belong in the results app. If you need a "core vs elective" flag, add it to `curriculum.Course` itself. |
| `results.Examination` model | **Removed from this app** | You already have a dedicated `examinations` app in your project's module list — exam scheduling/timetabling belongs there, not in `results`, which should only own outcomes. Happy to scaffold that app next if it doesn't exist yet. |
| Two-quotes-per-source... n/a, ignore | — | — |

## New permissions (Django Groups & Permissions — no hardcoded roles)

`Result.Meta.permissions` now declares:

- `results.submit_result`
- `results.approve_result_hod`
- `results.approve_result_dean`
- `results.approve_result_registrar`
- `results.publish_result`
- `results.return_result`

After migrating, assign these via Django admin (`Groups`) to your existing role groups, e.g.:

- **Lecturer** group → `submit_result` *(optional — see note below)*
- **Head of Department** group → `approve_result_hod`, `return_result`
- **Dean** group → `approve_result_dean`, `return_result`
- **Registrar** group → `approve_result_registrar`, `publish_result`, `return_result`

`ResultWorkflowService.transition()` checks these with `actor.has_perm(...)` — nothing in the code
checks `request.user.groups.filter(name="HOD")` or any other hardcoded role string.

**`submit_result` is a fallback, not a requirement.** A lecturer can submit a course's results
without holding this permission at all, as long as they're the `CourseAssignment` owner for that
exact course/session/semester (which the submit view already verifies before it ever reaches the
workflow check) — being assigned to teach the course is itself sufficient authorization to submit
its scores. The Django permission still works as an override for edge cases (e.g. a coordinator
submitting on behalf of a lecturer who isn't formally assigned yet), but you no longer need to
remember to grant it to every lecturer just for the common case to work. HOD/Dean/Registrar/Publish/
Return remain strictly permission-gated, since those are genuinely separate roles not tied to
teaching a specific course.

## Migrating existing data

Because the shape of grading data changed fundamentally (fixed columns → configurable components),
this needs a **data migration**, not just a schema migration. Rough shape (adapt to your actual
current DB state — run `python manage.py makemigrations results` first to get the schema migration,
then add a data migration like this one):

```python
# results/migrations/0005_migrate_grading_data.py
from django.db import migrations
from decimal import Decimal

def forwards(apps, schema_editor):
    GradingSetting = apps.get_model("results", "GradingSetting")   # old model, if still present
    GradeScale = apps.get_model("results", "GradeScale")
    Result = apps.get_model("results", "Result")

    AssessmentComponent = apps.get_model("results", "AssessmentComponent")
    GradingScheme = apps.get_model("results", "GradingScheme")
    GradingSchemeComponent = apps.get_model("results", "GradingSchemeComponent")
    GradeBoundary = apps.get_model("results", "GradeBoundary")
    ResultScore = apps.get_model("results", "ResultScore")
    ProgrammeGradingScheme = apps.get_model("results", "ProgrammeGradingScheme")

    ca_component, _ = AssessmentComponent.objects.get_or_create(
        code="ca", defaults={"name": "Continuous Assessment"}
    )
    exam_component, _ = AssessmentComponent.objects.get_or_create(
        code="exam", defaults={"name": "Examination"}
    )

    for setting in GradingSetting.objects.all():
        scheme = GradingScheme.objects.create(
            name=f"{setting.programme.name} Legacy Scheme",
        )
        GradingSchemeComponent.objects.create(
            scheme=scheme, component=ca_component,
            weight_percentage=setting.tma_weight, max_raw_score=setting.tma_weight,
        )
        GradingSchemeComponent.objects.create(
            scheme=scheme, component=exam_component,
            weight_percentage=setting.exam_weight, max_raw_score=setting.exam_weight,
        )
        for gs in GradeScale.objects.filter(programme=setting.programme):
            GradeBoundary.objects.create(
                scheme=scheme, grade=gs.grade, min_score=gs.min_score,
                max_score=gs.max_score, grade_point=gs.grade_point, remark=gs.remark,
            )
        ProgrammeGradingScheme.objects.create(programme=setting.programme, scheme=scheme)

        for result in Result.objects.filter(student__programme=setting.programme):
            result.scheme_id = scheme.id
            result.credit_unit = result.course.credit_unit
            result.save(update_fields=["scheme", "credit_unit"])
            ResultScore.objects.create(result=result, component=ca_component, raw_score=result.tma_score)
            ResultScore.objects.create(result=result, component=exam_component, raw_score=result.exam_score)


class Migration(migrations.Migration):
    dependencies = [("results", "0004_remove_result_credit_unit")]  # adjust to your real last migration
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
```

Run this **before** dropping the old `tma_score`/`exam_score`/`GradingSetting`/`GradeScale` columns
in a later migration, so there's no window where data is lost.

## Templates

`results/templates/results/lecturer/submit_scores.html` and `.../student/dashboard.html` will need
updating: the score-entry form should now loop over `components` (each with its own input named
`score_{component_id}_{student_id}`) instead of two fixed `tma_`/`exam_` inputs, and the student
dashboard should read `result.grade`, `result.total_score` etc. — same field names as before on
`Result`, so only the lecturer entry form template actually needs a rewrite. Say the word and I'll
do that next.

## Finance integration (added after initial delivery)

`AssessmentComponent` now has an `is_exam_component` boolean (default `False` — purely
additive, no prompt on migrate). Set it `True` on your "Examination" component only.
`GradingService.record_scores()` now checks `finance.services.exam_eligibility.ExamEligibilityService`
before accepting a score for any component flagged this way, and raises if the student
has outstanding mandatory fees for that course/semester. This means the `finance` app
must be installed and migrated before `results` for this check to import successfully
— see the finance app's own README for setup order.

## Suggested next steps

1. Run `makemigrations`/`migrate`, wire the data migration above to your real state.
2. Create the Django Groups (Lecturer, HOD, Dean, Registrar) and assign the new permissions.
3. Update `submit_scores.html` for the component-based form.
4. If you want, scaffold the `examinations` app for exam scheduling (separate from this app's outcome
   tracking) and/or wire `ResultAuditLog` into the shared `audit` app once that model exists.
