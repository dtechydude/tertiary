from import_export import resources

from students.models import Student


class StudentResource(resources.ModelResource):
    """
    CSV/Excel import-export for Student records, wired into StudentsAdmin
    (see admin.py). `matric_number` is the natural key used to match
    existing rows on import, so re-importing an updated CSV updates
    existing students rather than duplicating them.
    """

    def before_import_row(self, row, **kwargs):
        # Sensible defaults for optional medical fields when a source
        # CSV doesn't include them, so import doesn't fail on blanks.
        if not row.get('blood_group'):
            row['blood_group'] = 'select'
        if not row.get('genotype'):
            row['genotype'] = 'select'
        if not row.get('health_remark'):
            row['health_remark'] = ''

    class Meta:
        model = Student
        import_id_fields = ['matric_number']
        fields = (
            'id', 'matric_number', 'middle_name', 'department', 'programme', 'level',
            'date_admitted', 'gender', 'DOB', 'student_type', 'hostel_name',
            'blood_group', 'genotype', 'health_remark',
            'guardian_name', 'guardian_phone', 'guardian_address', 'guardian_email', 'relationship',
            'student_status', 'fee_balance',
        )
        skip_unchanged = True
        report_skipped = True
