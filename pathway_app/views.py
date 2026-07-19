from django.shortcuts import render

# Create your views here.
def home_screen(request):
    return render(request, 'base.html')