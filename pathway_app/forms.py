from django import forms
from django.contrib.auth.forms import UserCreationForm

class StudentRegistrationForm(UserCreationForm):
    graduation_year = forms.IntegerField(
        required=True,
        min_value=2020,
        max_value=2035,
        widget=forms.NumberInput(attrs={
            'placeholder': 'e.g. 2028',
            'class': 'w-full px-4 py-2.5 rounded-xl bg-[#EFECE6] border border-[#E2DDD5] text-xs font-medium focus:outline-none focus:border-[#1A202C]'
        })
    )