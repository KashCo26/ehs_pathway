from django.db import models

# Create your models here.
# myapp/models.py
from django.db import models

class Course(models.Model):
    course_number = models.CharField(max_length=20, unique=True, primary_key=True)
    course_name = models.CharField(max_length=None, blank=True, null=True)
    grade_level = models.CharField(max_length=50, blank=True, null=True)
    credits = models.CharField(max_length=None, blank=True, null=True)
    length = models.CharField(max_length=50, blank=True, null=True)
    essential_skills = models.TextField(max_length=None, blank=True, null=True)
    prerequisite_courses = models.TextField(max_length=None, blank=True, null=True)
    concurrent = models.TextField(max_length=None, blank=True, null=True)
    AP_honors = models.TextField(max_length=None, blank=True, null=True)
    section = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    work_outside_of_class = models.TextField(blank=True, null=True)
    rop = models.TextField(blank=True, null=True)
    school_site = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.course_number}"