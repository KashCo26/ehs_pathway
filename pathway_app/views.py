from django.shortcuts import render, redirect, get_object_or_404
from .models import Course, StudentProfile, StudentCourse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
import json
import re

# Create your views here.

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('courses')
    else:
        form = AuthenticationForm()
        
    return render(request, 'registration/login.html', {'form': form})

@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({'status': 'success'})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            
            session_key = request.session.session_key
            if session_key:
                guest_username = f"guest_{session_key}"
                try:
                    guest_user = User.objects.get(username=guest_username)
                    guest_profile = StudentProfile.objects.get(user=guest_user)
                    
                    user_profile, _ = StudentProfile.objects.get_or_create(user=new_user)
                    
                    StudentCourse.objects.filter(student=guest_profile).update(student=user_profile)
                    
                    guest_profile.delete()
                    guest_user.delete()
                except (User.DoesNotExist, StudentProfile.DoesNotExist):
                    pass

            login(request, new_user)
            return redirect('courses')
    else:
        form = UserCreationForm()
        
    return render(request, 'registration/register.html', {'form': form})

def get_or_create_guest_profile(request):
    if request.user.is_authenticated:
        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        return profile

    if not request.session.session_key:
        request.session.create()

    session_key = request.session.session_key
    
    guest_username = f"guest_{session_key}"
    guest_user, _ = User.objects.get_or_create(username=guest_username)
    profile, _ = StudentProfile.objects.get_or_create(user=guest_user)
    
    return profile

def toggle_course(request):
    try:
        data = json.loads(request.body)
        course_number = data.get('course_number')
        action = data.get('action')
        override = data.get('override', False)

        course = Course.objects.get(course_number=course_number)
        profile = get_or_create_guest_profile(request)

        if action == 'add':
            prerecs = course.prerequisite_courses or ""
            print(prerecs)
            
            if prerecs.strip() and not override:
                completed_nums = set(str(n) for n in profile.completed_courses.values_list('course_number', flat=True))
                planned_nums = set(str(n) for n in StudentCourse.objects.filter(student=profile).values_list('course__course_number', flat=True))
                all_student_courses = completed_nums.union(planned_nums)

                raw_or_groups = re.findall(r"\(([^)]+)\)", prerecs)
                or_groups = [re.findall(r"\b\d{5,8}\b", g) for g in raw_or_groups if re.findall(r"\b\d{5,8}\b", g)]

                string_without_parens = re.sub(r"\([^)]+\)", "", prerecs)
                and_numbers = re.findall(r"\b\d{5,8}\b", string_without_parens)

                for group in or_groups:
                    if not any(num in all_student_courses for num in group):
                        missing_ors = []
                        for num in group:
                            course = get_object_or_404(Course, course_number=num)
                            missing_ors.append(course.course_name)
                        return JsonResponse({
                            'status': 'error',
                            'message': f"Cannot add {course.course_name or course_number}. Missing prerequisite(s) {missing_ors}."
                        }, status=400)

                missing_and = [num for num in and_numbers if num not in all_student_courses]
                if missing_and:
                    missing_and_names = []
                    for num in missing_and:
                        course = get_object_or_404(Course, course_number = num)
                        missing_and_names.append(course.course_name)
                    missing_names = [name for name in missing_and_names]
                    
                    return JsonResponse({
                        'status': 'error',
                        'message': f"Cannot add {course.course_name or course_number}. Missing required prerequisite course(s): {', '.join(missing_names)}"
                    }, status=400)

            course_credits = float(course.credits or "5")
            assigned_grade = None
            assigned_semesters = None

            existing_student_courses = StudentCourse.objects.filter(student=profile)

            for grade in range(9, 13):
                if not override and str(grade) not in str(course.grade_level or ""):
                    continue

                grade_courses = existing_student_courses.filter(grade_level=grade)
                sem1_count = grade_courses.filter(semesters__contains='1').count()
                sem2_count = grade_courses.filter(semesters__contains='2').count()

                if course_credits >= 10.0:
                    if sem1_count < 6 and sem2_count < 6:
                        assigned_grade = grade
                        assigned_semesters = '1,2'
                        break
                else:
                    if sem1_count < 6:
                        assigned_grade = grade
                        assigned_semesters = '1'
                        break
                    elif sem2_count < 6:
                        assigned_grade = grade
                        assigned_semesters = '2'
                        break

            if not assigned_grade:
                if override:
                    assigned_grade = 12
                    assigned_semesters = '1,2' if course_credits >= 10.0 else '1'
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': f"Cannot add {course.course_name or course_number}. No available open schedule slots found for allowed grade levels ({course.grade_level})."
                    }, status=400)

            student_course, created = StudentCourse.objects.get_or_create(
                student=profile,
                course=course,
                defaults={
                    'grade_level': assigned_grade,
                    'semesters': assigned_semesters
                }
            )

            if not created:
                student_course.grade_level = assigned_grade
                student_course.semesters = assigned_semesters
                student_course.save()

        elif action == 'remove':
            StudentCourse.objects.filter(student=profile, course=course).delete()

        summary = profile.get_credit_summary()

        return JsonResponse({
            'status': 'success',
            'summary': summary
        })
    
    except Course.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Course not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def home_screen(request):
    student_profile = get_or_create_guest_profile(request)
    grad_year = student_profile.graduation_year or 2028
    return render(request, 'base.html', {'grad_year': str(grad_year)})


def courses(request):
    if request.method == 'POST':
        return toggle_course(request)
    student_profile = get_or_create_guest_profile(request)
    grad_year = student_profile.graduation_year or 2028
    all_courses = Course.objects.all()
    return render(request, 'course_catalog.html', {'courses': all_courses, 'grad_year': str(grad_year)})