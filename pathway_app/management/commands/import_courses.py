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
            c_num = str(row['Course Number']).strip()
            g_year = row['Grad Year'] or None

            excel_course_numbers.add(c_num)

            course, created = Course.objects.update_or_create(
                course_number=c_num,
                defaults={
                    'grad_year': g_year,
                    'grade_level': row['Grade Level'],
                    'length': str(row['Length']).strip(),
                    'essential_skills': str(row['Prerequisites']).strip(),
                    'description': str(row['Description']).strip(),
                    'work_outside_of_class': str(row['Work outside of Class']).strip(),
                    'credits': row['Credits'],
                    'section': str(row['Graduation']).strip(),
                    'rop': str(row['ROP']).strip(),
                    'school_site': str(row['School Site']).strip(),
                    'concurrent': row['Concurrent Enrollment Classes'],
                    'AP_honors': str(row['AP/Honors stat']).strip(),
                    'course_name': str(row['Course Name']).strip(),
                    'prerequisite_courses': row['Prerequisite Classes'],
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