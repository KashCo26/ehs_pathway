import pandas as pd
from django.core.management.base import BaseCommand
from pathway_app.models import Course

class Command(BaseCommand):
    help = 'Imports courses from an exported XLSX file'

    def add_arguments(self, parser):
        parser.add_argument('excel_path', type=str, help='Path to the XLSX file')

    def handle(self, *args, **kwargs):
        excel_path = kwargs['excel_path']

        df = pd.read_excel(excel_path)
        
        df = df.fillna('')

        created_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            course, created = Course.objects.update_or_create(
                course_number=str(row['Course Number']).strip(),
                defaults={
                    'grade_level': row['Grade Level'],
                    'length': row['Length'].strip(),
                    'essential_skills': row['Prerequisites'].strip(),
                    'description': row['Description'].strip(),
                    'work_outside_of_class': row['Work outside of Class'].strip(),
                    'credits': row['Credits'],
                    'section': row['Graduation'].strip(),
                    'rop': row['ROP'].strip(),
                    'school_site': row['School Site'].strip(),
                    'concurrent': row['Concurrent Enrollment Classes'],
                    'AP_honors': row['AP/Honors stat'].strip(),
                    'course_name': row['Course Name'].strip(),
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported! Created: {created_count}, Updated: {updated_count}")
        )