from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

class Course(models.Model):
    course_number = models.CharField(max_length=20, unique=True, primary_key=True)
    course_name = models.CharField(max_length=100, blank=True, null=True)
    grade_level = models.CharField(max_length=50, blank=True, null=True)
    credits = models.CharField(max_length=10, default="5")
    length = models.CharField(max_length=50, blank=True, null=True)
    essential_skills = models.TextField(blank=True, null=True)
    prerequisite_courses = models.CharField(max_length=200, blank=True, null=True)
    concurrent = models.TextField(blank=True, null=True)
    AP_honors = models.TextField(blank=True, null=True)
    section = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    work_outside_of_class = models.TextField(blank=True, null=True)
    rop = models.TextField(blank=True, null=True)
    school_site = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.course_number}"


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    graduation_year = models.IntegerField(default=datetime.now().year + 4)
    completed_courses = models.ManyToManyField(Course, through='StudentCourse', blank=True)

    def get_credit_summary(self):
        requirements = {
            'ENGLISH': 40.0,
            'WORLD HISTORY': 10.0,
            'US HISTORY': 10.0,
            'CIVICS/ECONOMICS': 10.0,
            'MATH': 20.0,
            'LIFE SCIENCE': 10.0,
            'PHYSICAL SCIENCE': 10.0,
            'WORLD LANGUAGE': 20.0,
            'PHYSICAL EDUCATION': 20.0,
            'HEALTH': 5.0,
            'VISUAL/PERFORMING ARTS': 10.0,
            'ELECTIVE': 65.0,
        }

        earned_credits = {key: 0.0 for key in requirements.keys()}
        courses_detail = []

        student_courses = StudentCourse.objects.filter(student=self, grade_level__gt = 8).select_related('course')
        ap_honors = 0

        for sc in student_courses:
            course = sc.course
            sec = (course.section or 'ELECTIVE').strip().upper()
            
            if course.AP_honors == "Yes":
                ap_honors += 1
            
            try:
                val = float(course.credits)
            except (ValueError, TypeError):
                val = 5.0

            courses_detail.append({
                'course_number': course.course_number,
                'course_name': course.course_name,
                'credits': val,
                'section': sec,
                'grade_level': sc.grade_level,
                'semesters': sc.semesters
            })

            if sec in earned_credits:
                if earned_credits[sec] + val <= requirements[sec]:
                    earned_credits[sec] += val
                else:
                    if sec != 'ELECTIVE':
                        overflow = (earned_credits[sec] + val) - requirements[sec]
                        earned_credits[sec] = requirements[sec]
                        earned_credits['ELECTIVE'] += overflow
                    else:
                        earned_credits['ELECTIVE'] += val
            else:
                earned_credits['ELECTIVE'] += val

        total_earned = sum(earned_credits.values())

        return {
            'categories': {
                cat: {
                    'earned': earned_credits[cat],
                    'required': req,
                    'complete': earned_credits[cat] >= req
                }
                for cat, req in requirements.items()
            },
            'total_earned': total_earned,
            'total_required': 230.0,
            'is_grad_eligible': total_earned >= 230.0,
            'completed_courses': courses_detail,
            'total_ap_honors': ap_honors
        }


class StudentCourse(models.Model):
    GRADE_LEVEL_CHOICES = [
        (9, '9th Grade'),
        (10, '10th Grade'),
        (11, '11th Grade'),
        (12, '12th Grade'),
    ]

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    grade_level = models.IntegerField(choices=GRADE_LEVEL_CHOICES, default=9, null=True)
    semesters = models.CharField(max_length=10, blank=True, null=True, default='1')
    is_pre_hs = models.BooleanField(null=True, default=False)
    is_summer = models.BooleanField(null=True, default=False)

    class Meta:
        unique_together = ('student', 'course')