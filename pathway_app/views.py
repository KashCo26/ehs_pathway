import json
import re

from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import StudentRegistrationForm
from .models import Course, StudentCourse, StudentProfile


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('four_year_plan')
    else:
        form = AuthenticationForm()
        
    return render(request, 'registration/login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    next_url = request.META.get('HTTP_REFERER', 'dashboard')
    return redirect(next_url)


def register(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            grad_year = form.cleaned_data.get('graduation_year')
            
            user_profile, _ = StudentProfile.objects.get_or_create(user=new_user)
            user_profile.graduation_year = grad_year
            user_profile.save()
            
            session_key = request.session.session_key
            if session_key:
                guest_username = f"guest_{session_key}"
                try:
                    guest_user = User.objects.get(username=guest_username)
                    guest_profile = StudentProfile.objects.get(user=guest_user)
                    
                    StudentCourse.objects.filter(student=guest_profile).update(student=user_profile)
                    
                    guest_profile.delete()
                    guest_user.delete()
                except (User.DoesNotExist, StudentProfile.DoesNotExist):
                    pass

            login(request, new_user)
            return redirect('four_year_plan')
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

def check_plan_dependencies(profile, student_courses):
    errors = []

    completed_nums = set(
        str(n) for n in profile.completed_courses.values_list('course_number', flat=True)
    )

    sorted_plan = sorted(
        student_courses,
        key=lambda sc: (
            sc.grade_level if sc.grade_level else 8,
            sc.is_summer,
            sc.semesters or ''
        )
    )

    available_courses = set(completed_nums)

    for sc in sorted_plan:
        course = sc.course
        if not course:
            continue

        course_name = course.course_name or course.course_number

        # 1. Check Grade Level Eligibility (Ignoring pre-high school courses)
        if not sc.is_pre_hs and sc.grade_level and course.grade_level:
            allowed_levels = [
                g.strip() for g in str(course.grade_level).split(',') if g.strip()
            ]
            if allowed_levels and str(sc.grade_level) not in allowed_levels:
                errors.append({
                    'course_number': course.course_number,
                    'course_name': course_name,
                    'grade_level': sc.grade_level,
                    'error_message': f"Grade level restriction: Not allowed in Grade {sc.grade_level} (allowed: {', '.join(allowed_levels)})"
                })

        # 2. Check Prerequisites
        prerecs = course.prerequisite_courses or ""
        if prerecs.strip():
            raw_or_groups = re.findall(r"\(([^)]+)\)", prerecs)
            or_groups = [re.findall(r"\b\d{5,8}\b", g) for g in raw_or_groups if re.findall(r"\b\d{5,8}\b", g)]

            for group in or_groups:
                if not any(str(num) in available_courses for num in group):
                    missing_ors = [
                        Course.objects.filter(course_number=n).first().course_name or str(n)
                        if Course.objects.filter(course_number=n).exists() else str(n)
                        for n in group
                    ]
                    errors.append({
                        'course_number': course.course_number,
                        'course_name': course_name,
                        'grade_level': sc.grade_level,
                        'error_message': f"Needs one of the following prerequisites: {', '.join(missing_ors)}"
                    })

            string_without_parens = re.sub(r"\([^)]+\)", "", prerecs)
            and_numbers = re.findall(r"\b\d{5,8}\b", string_without_parens)
            missing_and = [num for num in and_numbers if str(num) not in available_courses]

            if missing_and:
                missing_and_names = [
                    Course.objects.filter(course_number=n).first().course_name or str(n)
                    if Course.objects.filter(course_number=n).exists() else str(n)
                    for n in missing_and
                ]
                errors.append({
                    'course_number': course.course_number,
                    'course_name': course_name,
                    'grade_level': sc.grade_level,
                    'error_message': f"Missing required prerequisite(s): {', '.join(missing_and_names)}"
                })

        # 3. Check Corequisites (Concurrent Requirements)
        concurs = course.concurrent or ""
        if concurs.strip():
            same_or_prior_courses = set(available_courses)
            if sc.grade_level:
                concurrent_in_grade = [
                    str(c.course.course_number)
                    for c in student_courses
                    if c.grade_level == sc.grade_level and c.course
                ]
                same_or_prior_courses.update(concurrent_in_grade)

            raw_or_concurs = re.findall(r"\(([^)]+)\)", concurs)
            concur_ors = [re.findall(r"\b\d{5,8}\b", g) for g in raw_or_concurs if re.findall(r"\b\d{5,8}\b", g)]

            for group in concur_ors:
                if not any(str(num) in same_or_prior_courses for num in group):
                    missing_ors = [
                        Course.objects.filter(course_number=num).first().course_name or str(num)
                        if Course.objects.filter(course_number=num).exists() else str(num)
                        for num in group
                    ]
                    errors.append({
                        'course_number': course.course_number,
                        'course_name': course_name,
                        'grade_level': sc.grade_level,
                        'error_message': f"Corequisite issue: missing one of ({', '.join(missing_ors)})"
                    })

            concur_without_parens = re.sub(r"\([^)]+\)", "", concurs)
            concur_ands = re.findall(r"\b\d{5,8}\b", concur_without_parens)
            missing_concur_and = [num for num in concur_ands if str(num) not in same_or_prior_courses]

            if missing_concur_and:
                missing_and_names = [
                    Course.objects.filter(course_number=num).first().course_name or str(num)
                    if Course.objects.filter(course_number=num).exists() else str(num)
                    for num in missing_concur_and
                ]
                errors.append({
                    'course_number': course.course_number,
                    'course_name': course_name,
                    'grade_level': sc.grade_level,
                    'error_message': f"Missing required corequisite(s): {', '.join(missing_and_names)}"
                })

        available_courses.add(str(course.course_number))

    return errors

def toggle_course(request):
    try:
        data = json.loads(request.body)
        action = data.get('action')
        profile = get_or_create_guest_profile(request)
        course_number = data.get('course_number')
        override = data.get('override', False)
        course = get_object_or_404(Course, course_number=course_number)
        
        if 'mandatory' in (course.course_name or '').lower():
            if action in ['remove', 'add', 'pre-hs']:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Mandatory courses cannot be moved or removed.'
                }, status=400)
                
        existing_student_courses = StudentCourse.objects.filter(student=profile)

        if action == 'toggle_sport':
            grade_level = int(data.get('grade_level'))
            season = data.get('season')
            has_sport = data.get('has_sport', False)
            
            sports_list = profile.sports_grades or []
            
            sports_list = [
                item for item in sports_list 
                if not (isinstance(item, dict) and item.get('grade_level') == grade_level and item.get('season') == season)
            ]
            
            if has_sport:
                sports_list.append({
                    'grade_level': grade_level,
                    'season': season,
                    'has_sport': True
                })
            
            profile.sports_grades = sports_list
            profile.save()

            summary = profile.get_credit_summary()
            return JsonResponse({
                'status': 'success',
                'summary': summary
            })

        course_number = data.get('course_number')
        override = data.get('override', False)
        
        target_grade = data.get('grade_level')
        target_semesters = data.get('semesters')
        target_is_summer = data.get('is_summer', False)

        course = Course.objects.get(course_number=course_number)
        existing_student_courses = StudentCourse.objects.filter(student=profile)

        if action == 'add':
            override_reasons = []

            if course.course_number in ["SEMESTER_PE", "YEAR_PE"]:
                assigned_is_summer = True
                assigned_grade = int(target_grade) if target_grade else 9
                assigned_semesters = None
            else:
                prerecs = course.prerequisite_courses or ""
                concurs = course.concurrent or ""
                
                # Check Prerequisites
                if prerecs.strip():
                    completed_nums = set(str(n) for n in profile.completed_courses.values_list('course_number', flat=True))
                    planned_nums = set(str(n) for n in StudentCourse.objects.filter(student=profile).values_list('course__course_number', flat=True))
                    all_student_courses = completed_nums.union(planned_nums)

                    if target_grade:
                        allowed_grades = range(8, int(target_grade))
                        pre_check_courses = set(
                            str(n) for n in existing_student_courses.filter(
                                grade_level__in=allowed_grades
                            ).values_list('course__course_number', flat=True)
                        ).union(completed_nums)
                    else:
                        pre_check_courses = all_student_courses

                    raw_or_groups = re.findall(r"\(([^)]+)\)", prerecs)
                    or_groups = [re.findall(r"\b\d{5,8}\b", g) for g in raw_or_groups if re.findall(r"\b\d{5,8}\b", g)]

                    for group in or_groups:
                        if not any(str(num) in pre_check_courses for num in group):
                            missing_ors = [Course.objects.filter(course_number=n).first().course_name if Course.objects.filter(course_number=n).exists() else str(n) for n in group]
                            msg = f"Prerequisite issue: missing one of ({', '.join(missing_ors)})"
                            if override:
                                override_reasons.append(msg)
                            else:
                                return JsonResponse({'status': 'error', 'message': f"Cannot add {course.course_name or course_number}. {msg}."}, status=400)

                    string_without_parens = re.sub(r"\([^)]+\)", "", prerecs)
                    and_numbers = re.findall(r"\b\d{5,8}\b", string_without_parens)
                    missing_and = [num for num in and_numbers if str(num) not in pre_check_courses]
                    if missing_and:
                        missing_and_names = [Course.objects.filter(course_number=n).first().course_name if Course.objects.filter(course_number=n).exists() else str(n) for n in missing_and]
                        msg = f"Missing required prerequisite(s): {', '.join(missing_and_names)}"
                        if override:
                            override_reasons.append(msg)
                        else:
                            return JsonResponse({'status': 'error', 'message': f"Cannot add {course.course_name or course_number}. {msg}."}, status=400)

                if concurs.strip():
                    completed_nums = set(str(n) for n in profile.completed_courses.values_list('course_number', flat=True))
                    planned_nums = set(str(n) for n in StudentCourse.objects.filter(student=profile).values_list('course__course_number', flat=True))
                    all_student_courses = completed_nums.union(planned_nums)

                    if target_grade:
                        pre_check_courses = set(str(n) for n in existing_student_courses.filter(grade_level__in=range(8, int(target_grade))).values_list('course__course_number', flat=True))
                        concurrent_courses = set(str(n) for n in existing_student_courses.filter(grade_level=int(target_grade)).values_list('course__course_number', flat=True))
                    else:
                        pre_check_courses = all_student_courses
                        concurrent_courses = set()

                    raw_or_concurs = re.findall(r"\(([^)]+)\)", concurs)
                    concur_ors = [re.findall(r"\b\d{5,8}\b", g) for g in raw_or_concurs if re.findall(r"\b\d{5,8}\b", g)]
                    concur_without_parens = re.sub(r"\([^)]+\)", "", concurs)
                    concur_ands = re.findall(r"\b\d{5,8}\b", concur_without_parens)

                    for group in concur_ors:
                        if not any((str(num) in pre_check_courses) or (str(num) in concurrent_courses) for num in group):
                            missing_ors = [Course.objects.filter(course_number=num).first().course_name if Course.objects.filter(course_number=num).exists() else str(num) for num in group]
                            msg = f"Corequisite issue: missing one of ({', '.join(missing_ors)})"
                            if override:
                                override_reasons.append(msg)
                            else:
                                return JsonResponse({'status': 'error', 'message': f"Cannot add {course.course_name or course_number}. {msg}."}, status=400)

                    missing_concur_and = [num for num in concur_ands if str(num) not in pre_check_courses and str(num) not in concurrent_courses]
                    if missing_concur_and:
                        missing_and_names = [Course.objects.filter(course_number=num).first().course_name if Course.objects.filter(course_number=num).exists() else str(num) for num in missing_concur_and]
                        msg = f"Missing required corequisite(s): {', '.join(missing_and_names)}"
                        if override:
                            override_reasons.append(msg)
                        else:
                            return JsonResponse({'status': 'error', 'message': f"Cannot add {course.course_name or course_number}. {msg}."}, status=400)

                course_credits = float(course.credits or "5")
                assigned_grade = None
                assigned_semesters = None
                assigned_is_summer = False

                if target_grade:
                    allowed_levels = [str(g).strip() for g in str(course.grade_level or "").split(',') if g.strip()]
                    if str(target_grade) in allowed_levels:
                        assigned_grade = int(target_grade)
                    elif override:
                        assigned_grade = int(target_grade)
                        override_reasons.append(f"Grade level restriction bypassed for Grade {target_grade} (allowed: {', '.join(allowed_levels)}).")
                    else:
                        return JsonResponse({'status': 'error', 'message': f"Cannot add {course.course_name or course_number} to Grade {target_grade}."}, status=400)
                    
                    assigned_semesters = '1,2' if course_credits >= 10.0 else target_semesters
                    assigned_is_summer = bool(target_is_summer)
                else:
                    for grade in range(9, 13):
                        if not override and str(grade) not in str(course.grade_level or ""):
                            continue
                        grade_courses = existing_student_courses.filter(grade_level=grade, is_summer=False)
                        sem1_count = grade_courses.filter(semesters__contains='1').count()
                        sem2_count = grade_courses.filter(semesters__contains='2').count()

                        if course_credits >= 10.0 and sem1_count < 6 and sem2_count < 6:
                            assigned_grade = grade
                            assigned_semesters = '1,2'
                            break
                        elif course_credits < 10.0:
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
                            override_reasons.append("Placed automatically due to override with no standard open slots.")
                        else:
                            return JsonResponse({'status': 'error', 'message': "No open slots available."}, status=400)

            # Store override state & error log
            error_msg_str = " | ".join(override_reasons) if override_reasons else None
            is_ovr = bool(override and override_reasons)

            student_course, created = StudentCourse.objects.get_or_create(
                student=profile,
                course=course,
                defaults={
                    'grade_level': assigned_grade,
                    'semesters': assigned_semesters,
                    'is_summer': assigned_is_summer,
                    'is_pre_hs': False,
                    'is_overridden': is_ovr,
                    'override_error_message': error_msg_str,
                }
            )

            if not created:
                student_course.grade_level = assigned_grade
                student_course.semesters = assigned_semesters
                student_course.is_summer = assigned_is_summer
                student_course.is_pre_hs = False
                student_course.is_overridden = is_ovr
                student_course.override_error_message = error_msg_str
                student_course.save()

        elif action == 'remove':
            StudentCourse.objects.filter(student=profile, course=course).delete()

        summary = profile.get_credit_summary()
        return JsonResponse({'status': 'success', 'summary': summary})

    except Course.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Course not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def courses(request):
    if request.method == 'POST':
        return toggle_course(request)
    student_profile = get_or_create_guest_profile(request)
    grad_year = student_profile.graduation_year
    all_courses = Course.objects.all()
    return render(request, 'course_catalog.html', {'courses': all_courses, 'grad_year': str(grad_year)})

def sort_key(sc):
    is_mandatory = 'mandatory' in (sc.course.course_name or '').lower() if sc.course else False
    return (not is_mandatory, sc.course.course_name if sc.course else '')


def four_year_plan_view(request):
    profile = get_or_create_guest_profile(request)
    grad_year = profile.graduation_year
    student_courses = StudentCourse.objects.filter(student=profile).select_related('course')
    pre_hs_courses = [sc for sc in student_courses if sc.is_pre_hs]
    all_courses = Course.objects.all()
    
    overridden_errors = check_plan_dependencies(profile, student_courses)
        
    added_course_numbers = {
        str(sc.course.course_number) 
        for sc in student_courses 
        if sc.course and sc.course.course_number
    }
    
    sports_grades_raw = profile.sports_grades or []
    sports_fall_grades = []
    sports_spring_grades = []
    sports_winter_grades = []

    for item in sports_grades_raw:
        if isinstance(item, dict) and item.get('has_sport'):
            grade = int(item.get('grade_level'))
            season = item.get('season')
            if season == 'fall':
                sports_fall_grades.append(grade)
            elif season == 'spring':
                sports_spring_grades.append(grade)
            elif season == 'winter':
                sports_winter_grades.append(grade)

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
    
    for yr in years:
        yr['fall'].sort(key=sort_key)
        yr['spring'].sort(key=sort_key)
        yr['summer'].sort(key=sort_key)
        
    pre_hs_courses.sort(key=sort_key)
    
    context = {
        'pre_hs_courses': pre_hs_courses,
        'years': years,
        'credits_earned': summary['total_earned'],
        'credits_required': summary['total_required'],
        'credits_remaining': summary['total_required'] - summary['total_earned'],
        'ap_honors_total': summary['total_ap_honors'],
        'grad_year': grad_year,
        'all_courses': all_courses,
        'sports_fall_grades': sports_fall_grades,
        'sports_spring_grades': sports_spring_grades,
        'sports_winter_grades' : sports_winter_grades,
        'all_student_courses': added_course_numbers,
        'overridden_errors': overridden_errors,
    }
    
    if request.method == "POST":
        return toggle_course(request)
        
    return render(request, 'four_year_plan.html', context)


def credits_summary(request):
    profile = get_or_create_guest_profile(request)
    summary = profile.get_credit_summary()
    grad_year = profile.graduation_year
    sports_grades_raw = profile.sports_grades or []
    sports_fall_grades = []
    sports_spring_grades = []

    for item in sports_grades_raw:
        if isinstance(item, dict) and item.get('has_sport'):
            grade = int(item.get('grade_level'))
            season = item.get('season')
            if season == 'fall':
                sports_fall_grades.append(grade)
            elif season == 'spring':
                sports_spring_grades.append(grade)
                
    num_fall_sports = len(sports_fall_grades) if len(sports_fall_grades) > 0 else None
    num_spring_sports = len(sports_spring_grades) if len(sports_spring_grades) > 0 else None

    categories_list = []
    
    for cat_name, data in summary['categories'].items():
        earned = data['earned']
        required = data['required']
        course_nums = data.get('course_nums', [])
        recommended = data['recommended']
        
        courses = Course.objects.filter(course_number__in=course_nums)
        course_grades = StudentCourse.objects.filter(student=profile, course__in=courses)
        
        course_dict = {c.course_name or c.course_number: s.grade_level for c in courses for s in course_grades if s.course == c}
        course_dict = dict(sorted(course_dict.items(), key=lambda x: x[0]))
        
        percent = (earned / required * 100) if required > 0 else 0
        percent = min(percent, 100.0)

        categories_list.append({
            'name': cat_name.title().upper(),
            'earned': earned,
            'required': required,
            'remaining': max(0.0, required - earned),
            'is_complete': data['complete'],
            'percent_complete': round(percent, 1),
            'course_names': course_dict,
            'recommended': recommended
        })

    context = {
        'credits_earned': summary['total_earned'],
        'credits_required': summary['total_required'],
        'credits_remaining': max(0.0, summary['total_required'] - summary['total_earned']),
        'is_grad_eligible': summary['is_grad_eligible'],
        'categories': categories_list,
        'total_ap_honors': summary['total_ap_honors'],
        'grad_year': grad_year,
        'num_fall_sports': num_fall_sports,
        'num_spring_sports': num_spring_sports,
        'sports_fall_grades': sports_fall_grades,
        'sports_spring_grades': sports_spring_grades,
    }
    
    return render(request, 'credits.html', context)

def a_to_g_credits_summary(request):
    profile = get_or_create_guest_profile(request)
    summary = profile.get_a_to_g_summary()
    grad_year = profile.graduation_year

    categories_list = []
    
    for cat_name, data in summary['categories'].items():
        earned = data['earned']
        required = data['required']
        course_nums = data.get('course_nums', [])
        recommended = data['recommended']
        
        courses = Course.objects.filter(course_number__in=course_nums)
        course_grades = StudentCourse.objects.filter(student=profile, course__in=courses)
        
        course_dict = {c.course_name or c.course_number: s.grade_level for c in courses for s in course_grades if s.course == c}
        course_dict = dict(sorted(course_dict.items(), key=lambda x: x[0]))
        
        percent = (earned / required * 100) if required > 0 else 0
        percent = min(percent, 100.0)

        categories_list.append({
            'name': cat_name.title().upper(),
            'earned': earned,
            'required': required,
            'remaining': max(0.0, required - earned),
            'is_complete': data['complete'],
            'percent_complete': round(percent, 1),
            'course_names': course_dict,
            'recommended': recommended
        })

    context = {
        'credits_earned': summary['total_earned'],
        'credits_required': summary['total_required'],
        'credits_remaining': max(0.0, summary['total_required'] - summary['total_earned']),
        'is_a_to_g_eligible': summary['is_a_to_g_eligible'],
        'categories': categories_list,
        'total_ap_honors': summary['total_ap_honors'],
        'grad_year': grad_year
    }
    
    return render(request, 'a_to_g_credits.html', context)