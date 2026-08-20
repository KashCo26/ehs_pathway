from django.shortcuts import render
from .models import Course

# Create your views here.
def home_screen(request):
    return render(request, 'base.html')

def courses(request):
    courses = Course.objects.all()
    return render(request, 'course_catalog.html', {'courses': courses})