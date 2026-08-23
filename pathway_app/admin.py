from django.contrib import admin
from .models import Course, StudentProfile, StudentCourse

# Register your models here.
admin.site.register(Course)
admin.site.register(StudentProfile)
admin.site.register(StudentCourse)