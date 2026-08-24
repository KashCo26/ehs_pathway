from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views

# Define a list of url patterns
urlpatterns = [
    path('', views.four_year_plan_view, name='four_year_plan'),
    path('courses/', views.courses, name='courses'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]