import os
import re
import pandas as pd
from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Imports academic pathways and visual diagrams from an exported XLSX file'

    def add_arguments(self, parser):
        parser.add_argument('excel_path', type=str, help='Path to the XLSX file')

    def handle(self, *args, **kwargs):
        excel_path = kwargs['excel_path']

        AcademicPathway = apps.get_model('pathway_app', 'AcademicPathway')
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
            pathway_name = str(row.get('Pathway Name', '')).strip()
            
            # Read Image 1 and Image 2 columns from Excel
            image1_url = str(row.get('Image 1', '')).strip()
            image2_url = str(row.get('Image 2', '')).strip()

            if not pathway_name:
                continue

            pathway_defaults = {
                'image1': image1_url,
                'image2': image2_url,
            }

            pathway, created = AcademicPathway.objects.update_or_create(
                name=pathway_name,
                defaults=pathway_defaults
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully imported Academic Pathways! Created: {created_count}, Updated: {updated_count}"
            )
        )