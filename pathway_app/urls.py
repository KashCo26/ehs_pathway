from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views

# Define a list of url patterns
urlpatterns = [
    path('', views.home_screen, name='home')
]