import pandas as pd
from django.core.management.base import BaseCommand
from pathway_app.models import Course

class Command(BaseCommand):
    help = 'Imports courses from an exported XLSX file and removes outdated courses'

    def add_arguments(self, parser):
        parser.add_argument('excel_path', type=str, help='Path to the XLSX file')

    def handle(self, *args, **kwargs):
        excel_path = kwargs['excel_path']

        df = pd.read_excel(excel_path)
        df = df.fillna('')

        created_count = 0
        updated_count = 0
        excel_course_numbers = set()

        for _, row in df.iterrows():
            raw_c_num = str(row['Course Number']).strip()
            if raw_c_num.endswith('.0'):
                raw_c_num = raw_c_num[:-2]
            c_num = raw_c_num

            if not c_num or c_num.lower() == 'nan':
                continue

            raw_g_year = str(row.get('Grad Year', '')).strip()
            g_year = None
            if raw_g_year and raw_g_year.lower() != 'nan':
                try:
                    if raw_g_year.endswith('.0'):
                        raw_g_year = raw_g_year[:-2]
                    g_year = int(float(raw_g_year))
                except (ValueError, TypeError):
                    g_year = None

            excel_course_numbers.add(c_num)

            course, created = Course.objects.update_or_create(
                course_number=c_num,
                defaults={
                    'grad_year': g_year,
                    'grade_level': str(row.get('Grade Level', '')).strip(),
                    'length': str(row.get('Length', '')).strip(),
                    'essential_skills': str(row.get('Prerequisites', '')).strip(),
                    'description': str(row.get('Description', '')).strip(),
                    'work_outside_of_class': str(row.get('Work outside of Class', '')).strip(),
                    'credits': row.get('Credits', 0.0),
                    'section': str(row.get('Graduation', '')).strip(),
                    'rop': str(row.get('ROP', '')).strip(),
                    'school_site': str(row.get('School Site', '')).strip(),
                    'concurrent': row.get('Concurrent Enrollment Classes'),
                    'AP_honors': str(row.get('AP/Honors stat', '')).strip(),
                    'course_name': str(row.get('Course Name', '')).strip(),
                    'prerequisite_courses': row.get('Prerequisite Classes'),
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        deleted_count, _ = Course.objects.exclude(course_number__in=excel_course_numbers).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully imported! Created: {created_count}, "
                f"Updated: {updated_count}, Deleted: {deleted_count}"
            )
        )