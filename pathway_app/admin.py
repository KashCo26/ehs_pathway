from django.contrib import admin
from .models import Course, StudentProfile, StudentCourse, Pathway, PathwayCourse, AcademicPathway

# Register your models here.
admin.site.register(Course)
admin.site.register(StudentProfile)
admin.site.register(StudentCourse)
admin.site.register(Pathway)
admin.site.register(PathwayCourse)
admin.site.register(AcademicPathway)