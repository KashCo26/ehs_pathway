from collections import defaultdict

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
    sports_grades = models.JSONField(default=list, blank=True)

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
        recommended = {
            'WORLD HISTORY': "1 year required",
            "US HISTORY": "1 year required",
            'CIVICS/ECONOMICS': "1 year required",
            'ENGLISH': "4 years required",
            'MATH': "2 years required",
            'WORLD LANGUAGE': "2 years required",
            'LIFE SCIENCE': "1 year required",
            'PHYSICAL SCIENCE': "1 year required",
            'PHYSICAL EDUCATION': "2 years required",
            'HEALTH': "1 year required",
            'VISUAL/PERFORMING ARTS': "1 year required",
            'ELECTIVE': "6 years of elective courses as well as 5 extra credits from Contemporary Health required",
        }

        earned_credits = {key: 0.0 for key in requirements.keys()}
        course_nums = {key: [] for key in requirements.keys()}
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
                    course_nums[sec].append(course.course_number)
                else:
                    if sec != 'ELECTIVE':
                        overflow = (earned_credits[sec] + val) - requirements[sec]
                        earned_credits[sec] = requirements[sec]
                        earned_credits['ELECTIVE'] += overflow
                        course_nums['ELECTIVE'].append(course.course_number)
                        course_nums[sec].append(course.course_number)
                    else:
                        earned_credits['ELECTIVE'] += val
                        course_nums['ELECTIVE'].append(course.course_number)
            else:
                earned_credits['ELECTIVE'] += val
                course_nums['ELECTIVE'].append(course.course_number)
                

        for sport_entry in self.sports_grades or []:
            if isinstance(sport_entry, dict) and sport_entry.get('has_sport', False):
                grade = sport_entry.get('grade_level')
                season = sport_entry.get('season', 'sport')
                
                earned_credits['PHYSICAL EDUCATION'] += 5
                course_nums['PHYSICAL EDUCATION'].append(f"SPORTS_{grade}_{season.upper()}")

        minimized_credits = {cat: min(earned_credits[cat], req) for cat, req in requirements.items()}
        raw_total_earned = sum(minimized_credits.values())
        total_required = 230.0

        total_earned = min(raw_total_earned, total_required)

        return {
            'categories': {
                cat: {
                    'earned': earned_credits[cat],
                    'required': req,
                    'complete': earned_credits[cat] >= req,
                    'course_nums': course_nums[cat],
                    'recommended': recommended[cat] if cat in recommended else ""
                }
                for cat, req in requirements.items()
            },
            'total_earned': total_earned,
            'total_required': total_required,
            'is_grad_eligible': raw_total_earned >= total_required,
            'completed_courses': courses_detail,
            'total_ap_honors': ap_honors
        }
        
    def get_a_to_g_summary(self):
        requirements = {
            'A. HISTORY/SOCIAL SCIENCE': 20.0,
            'B. ENGLISH': 40.0,
            'C. MATH': 30.0,
            'D. LABORATORY SCIENCE': 20.0,
            'E. LANGUAGE OTHER THAN ENGLISH': 20.0,
            'F. VISUAL AND PERFORMING ARTS': 10.0,
            'G. COLLEGE PREPARATORY ELECTIVE': 10.0,
        }
        
        recommended = {
            'A. HISTORY/SOCIAL SCIENCE': "2 years required",
            'B. ENGLISH': "4 years required",
            'C. MATH': "3 years required, 4 years strongly recommended",
            'E. LANGUAGE OTHER THAN ENGLISH': "2 years required, 3 years strongly recommended",
            'D. LABORATORY SCIENCE': "2 years required, 3 years strongly recommended",
            'F. VISUAL AND PERFORMING ARTS': "1 year required",
            'G. COLLEGE PREPARATORY ELECTIVE': "1 year required",
        }

        earned_credits = {key: 0.0 for key in requirements.keys()}
        course_nums = {key: [] for key in requirements.keys()}
        courses_detail = []

        student_courses = StudentCourse.objects.filter(student=self, grade_level__gt = 8).select_related('course')
        ap_honors = 0

        for sc in student_courses:
            course = sc.course
            sec = (course.section or 'ELECTIVE').strip().upper()
            if sec == 'US HISTORY' or sec == 'CIVICS/ECONOMICS' or sec == 'WORLD HISTORY':
                sec = 'A. HISTORY/SOCIAL SCIENCE'
            elif sec == 'LIFE SCIENCE' or sec == 'PHYSICAL SCIENCE':
                sec = 'D. LABORATORY SCIENCE'
            elif sec == 'MATH':
                sec = 'C. MATH'
            elif sec == 'ENGLISH':
                sec = 'B. ENGLISH'
            elif sec == 'WORLD LANGUAGE':
                sec = 'E. LANGUAGE OTHER THAN ENGLISH'
            elif sec == 'VISUAL/PERFORMING ARTS':
                sec = 'F. VISUAL AND PERFORMING ARTS'
            elif sec == 'ELECTIVE':
                sec = 'G. COLLEGE PREPARATORY ELECTIVE'
            
            
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
                    course_nums[sec].append(course.course_number)
                else:
                    if sec != 'ELECTIVE':
                        overflow = (earned_credits[sec] + val) - requirements[sec]
                        earned_credits[sec] = requirements[sec]
                        earned_credits['G. COLLEGE PREPARATORY ELECTIVE'] += overflow
                        course_nums['G. COLLEGE PREPARATORY ELECTIVE'].append(course.course_number)
                        course_nums[sec].append(course.course_number)
                    else:
                        earned_credits['G. COLLEGE PREPARATORY ELECTIVE'] += val
                        course_nums['G. COLLEGE PREPARATORY ELECTIVE'].append(course.course_number)
            else:
                earned_credits['G. COLLEGE PREPARATORY ELECTIVE'] += val
                course_nums['G. COLLEGE PREPARATORY ELECTIVE'].append(course.course_number)

        minimized_credits = {cat: min(earned_credits[cat], req) for cat, req in requirements.items()}
        raw_total_earned = sum(minimized_credits.values())
        total_required = 150.0

        total_earned = min(raw_total_earned, total_required)

        return {
            'categories': {
                cat: {
                    'earned': earned_credits[cat],
                    'required': req,
                    'complete': earned_credits[cat] >= req,
                    'course_nums': course_nums[cat],
                    'recommended': recommended[cat] if cat in recommended else ""
                }
                for cat, req in requirements.items()
            },
            'total_earned': total_earned,
            'total_required': total_required,
            'is_a_to_g_eligible': raw_total_earned >= total_required,
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
    is_overridden = models.BooleanField(default=False)
    override_error_message = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('student', 'course')
        
class Pathway(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    course_sequence = models.JSONField(
        default=list, 
        help_text="Ordered list of course numbers for this pathway"
    )

    def __str__(self):
        return self.name

    def get_courses(self):
        """Fetch course objects matching the sequence."""
        from .models import Course
        
        courses_dict = {
            c.course_number: c 
            for c in Course.objects.filter(course_number__in=self.course_sequence)
        }
        return [courses_dict[num] for num in self.course_sequence if num in courses_dict]
    

class Pathway(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    courses = models.ManyToManyField('Course',through='PathwayCourse',related_name='pathways')
    image = models.ImageField(upload_to='pathway_images/', blank=True, null=True)

    def __str__(self):
        return self.name

    def get_ordered_courses(self):
        """Returns the course objects in sequence based on their order."""
        return [pc.course for pc in self.pathway_courses.select_related('course').order_by('order')]
    
    def get_grouped_courses(self):
        """Groups pathway courses by their order level."""
        grouped = defaultdict(list)
        for pc in self.pathway_courses.select_related('course').order_by('order'):
            grouped[pc.order].append(pc.course)
        return sorted(grouped.items())


class PathwayCourse(models.Model):
    pathway = models.ForeignKey(Pathway, on_delete=models.CASCADE, related_name='pathway_courses')
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='pathway_links')
    order = models.PositiveIntegerField(help_text="Position of the course in this pathway (e.g., Level 1, Level 2)")

    class Meta:
        ordering = ['order']
        unique_together = ('pathway', 'course')

    def __str__(self):
        return f"{self.pathway.name} - Level {self.order}: {self.course.course_number}"
    
    
class AcademicPathway(models.Model):
    name = models.CharField(max_length=200, unique=True)
    image1 = models.CharField(max_length=500, blank=True, null=True)
    image2 = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        return self.name