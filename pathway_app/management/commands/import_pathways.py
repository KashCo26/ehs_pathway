import os
import re
import pandas as pd
from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Imports pathways from an exported XLSX file with multiple course options in parentheses'

    def add_arguments(self, parser):
        parser.add_argument('excel_path', type=str, help='Path to the XLSX file')

    def handle(self, *args, **kwargs):
        excel_path = kwargs['excel_path']

        Pathway = apps.get_model('pathway_app', 'Pathway')
        PathwayCourse = apps.get_model('pathway_app', 'PathwayCourse')
        Course = apps.get_model('pathway_app', 'Course')

        df = pd.read_excel(excel_path)
        df = df.fillna('')

        created_count = 0
        updated_count = 0

        level_headers = [
            'Pathway Level 1',
            'Pathway Level 2',
            'Pathway Level 3',
            'Pathway Level 4'
        ]

        for _, row in df.iterrows():
            pathway_name = str(row['Pathway Name']).strip()
            description = str(row['Description']).strip()
            
            # Reads 'Image' column (or 'Image URL' if present) safely
            image_val = row.get('Image', row.get('Image URL', ''))
            image_url = str(image_val).strip()

            if not pathway_name:
                continue

            # Base defaults for updating or creating
            pathway_defaults = {
                'description': description
            }

            # If the Pathway model has an image field, set it
            if hasattr(Pathway, 'image'):
                pathway_defaults['image'] = image_url

            pathway, created = Pathway.objects.update_or_create(
                name=pathway_name,
                defaults=pathway_defaults
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

            for order, header in enumerate(level_headers, start=1):
                if header not in row:
                    continue

                raw_val = str(row[header]).strip()

                if not raw_val:
                    continue

                # Extract all 4-8 digit course numbers (handles strings like "(10101, 10102, 10103)")
                course_numbers = re.findall(r'\b\d{4,8}\b', raw_val)

                # Fallback in case course numbers are not purely digits or use simple strings
                if not course_numbers:
                    clean_val = raw_val.strip('() ')
                    if clean_val.endswith('.0'):
                        clean_val = clean_val[:-2]
                    course_numbers = [c.strip() for c in clean_val.split(',') if c.strip()]

                for num in course_numbers:
                    course = Course.objects.filter(course_number=num).first()

                    if course:
                        PathwayCourse.objects.update_or_create(
                            pathway=pathway,
                            course=course,
                            defaults={'order': order}
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Course '{num}' (from level {order}) not found for pathway '{pathway_name}'. Skipped."
                            )
                        )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported pathways! Created: {created_count}, Updated: {updated_count}")
        )