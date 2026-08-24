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
    next_url = request.META.get('HTTP_REFERER', 'dashboard')
    return redirect(next_url)

# views.py
from .forms import StudentRegistrationForm  # Add this import

def register(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            grad_year = form.cleaned_data.get('graduation_year')
            
            # Save graduation year to StudentProfile
            user_profile, _ = StudentProfile.objects.get_or_create(user=new_user)
            user_profile.graduation_year = grad_year
            user_profile.save()
            
            session_key = request.session.session_key
            if session_key:
                guest_username = f"guest_{session_key}"
                try:
                    guest_user = User.objects.get(username=guest_username)
                    guest_profile = StudentProfile.objects.get(user=guest_user)
                    
                    # Transfer guest courses to the registered user profile
                    StudentCourse.objects.filter(student=guest_profile).update(student=user_profile)
                    
                    guest_profile.delete()
                    guest_user.delete()
                except (User.DoesNotExist, StudentProfile.DoesNotExist):
                    pass

            login(request, new_user)
            return redirect('courses')
    else:
        form = StudentRegistrationForm()
        
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
        
        target_grade = data.get('grade_level')
        target_semesters = data.get('semesters')
        target_is_summer = data.get('is_summer', False)

        course = Course.objects.get(course_number=course_number)
        profile = get_or_create_guest_profile(request)
        existing_student_courses = StudentCourse.objects.filter(student=profile)

        if action == 'add':
            prerecs = course.prerequisite_courses or ""
            
            if prerecs.strip() and not override:
                completed_nums = set(str(n) for n in profile.completed_courses.values_list('course_number', flat=True))
                planned_nums = set(str(n) for n in StudentCourse.objects.filter(student=profile).values_list('course__course_number', flat=True))
                all_student_courses = completed_nums.union(planned_nums)
                
                if target_grade:
                    allowed_grades = range(8, target_grade)
                    pre_check_courses = existing_student_courses.filter(grade_level__in=allowed_grades)
                
                raw_or_groups = re.findall(r"\(([^)]+)\)", prerecs)
                or_groups = [re.findall(r"\b\d{5,8}\b", g) for g in raw_or_groups if re.findall(r"\b\d{5,8}\b", g)]

                string_without_parens = re.sub(r"\([^)]+\)", "", prerecs)
                and_numbers = re.findall(r"\b\d{5,8}\b", string_without_parens)
                check_courses = pre_check_courses if target_grade else all_student_courses
                
                for group in or_groups:
                    if not any(num in check_courses for num in group):
                        missing_ors = []
                        for num in group:
                            req_course = get_object_or_404(Course, course_number=num)
                            missing_ors.append(req_course.course_name)
                        return JsonResponse({
                            'status': 'error',
                            'message': f"Cannot add {course.course_name or course_number}. You need to have taken at least one of these courses: {', '.join(course for course in missing_ors)}."
                        }, status=400)

                missing_and = [num for num in and_numbers if num not in check_courses]
                if missing_and:
                    missing_and_names = []
                    for num in missing_and:
                        req_course = get_object_or_404(Course, course_number=num)
                        missing_and_names.append(req_course.course_name)
                    
                    return JsonResponse({
                        'status': 'error',
                        'message': f"Cannot add {course.course_name or course_number}. Missing prerequisite course(s): {', '.join(missing_and_names)}"
                    }, status=400)

            course_credits = float(course.credits or "5")
            assigned_grade = None
            assigned_semesters = None
            assigned_is_summer = False

            if target_grade:
                allowed_levels = [str(g).strip() for g in str(course.grade_level or "").split(',') if g.strip()]
                
                if override or (str(target_grade) in allowed_levels):
                    assigned_grade = int(target_grade)
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': f"Cannot add {course.course_name or course_number} to Grade {target_grade}. Allowed grade level(s): {', '.join(allowed_levels) if allowed_levels else 'None'}."
                    }, status=400)
                
                assigned_semesters = '1,2' if course_credits >= 10.0 else target_semesters
                assigned_is_summer = bool(target_is_summer)
            
            else:
                for grade in range(9, 13):
                    if not override and str(grade) not in str(course.grade_level or ""):
                        continue

                    grade_courses = existing_student_courses.filter(grade_level=grade, is_summer=False)
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
                    'semesters': assigned_semesters,
                    'is_summer': assigned_is_summer,
                    'is_pre_hs': False
                }
            )

            if not created:
                student_course.grade_level = assigned_grade
                student_course.semesters = assigned_semesters
                student_course.is_summer = assigned_is_summer
                student_course.is_pre_hs = False
                student_course.save()

        elif action == 'remove':
            StudentCourse.objects.filter(student=profile, course=course).delete()
        
        elif action == 'pre-hs':
            student_course, created = StudentCourse.objects.get_or_create(
                student=profile,
                course=course,
                defaults={
                    'grade_level': 8,
                    'is_pre_hs': True,
                    'is_summer': False,
                    'semesters': None,
                }
            )
            
            if not created:
                student_course.grade_level = 8
                student_course.semesters = None
                student_course.is_summer = False
                student_course.is_pre_hs = True
                student_course.save()

        summary = profile.get_credit_summary()

        return JsonResponse({
            'status': 'success',
            'summary': summary
        })
    
    except Course.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Course not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


def courses(request):
    if request.method == 'POST':
        return toggle_course(request)
    student_profile = get_or_create_guest_profile(request)
    grad_year = student_profile.graduation_year or 2028
    all_courses = Course.objects.all()
    return render(request, 'course_catalog.html', {'courses': all_courses, 'grad_year': str(grad_year)})

def four_year_plan_view(request):
    profile = get_or_create_guest_profile(request)
    grad_year = profile.graduation_year or 2028
    student_courses = StudentCourse.objects.filter(student=profile).select_related('course')
    pre_hs_courses = [sc for sc in student_courses if sc.is_pre_hs]
    all_courses = Course.objects.all()
    years = [
        {'grade': 9, 'label': '9th grade', 'fall': [], 'spring': [], 'summer': []},
        {'grade': 10, 'label': '10th grade', 'fall': [], 'spring': [], 'summer': []},
        {'grade': 11, 'label': '11th grade', 'fall': [], 'spring': [], 'summer': []},
        {'grade': 12, 'label': '12th grade', 'fall': [], 'spring': [], 'summer': []},
    ]
    for sc in student_courses:
        if sc.grade_level in [9, 10, 11, 12]:
            idx = sc.grade_level - 9
            if sc.is_summer:
                years[idx]['summer'].append(sc)
            else:
                semesters = str(sc.semesters or '').split(',')
                if '1' in semesters:
                    years[idx]['fall'].append(sc)
                if '2' in semesters:
                    years[idx]['spring'].append(sc)
                         
    summary = profile.get_credit_summary()
    context = {
        'pre_hs_courses': pre_hs_courses,
        'years': years,
        'credits_earned': summary['total_earned'],
        'credits_required': summary['total_required'],
        'credits_remaining': summary['total_required'] - summary['total_earned'],
        'ap_honors_total': summary['total_ap_honors'],
        'grad_year': grad_year,
        'all_courses': all_courses
    }
    
    if request.method == "POST":
        return toggle_course(request)
    return render(request, 'four_year_plan.html', context)