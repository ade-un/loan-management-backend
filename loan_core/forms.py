# forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import LoanApplication

class UserRegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=100, required=True)
    email     = forms.EmailField(required=True)

    class Meta:
        model  = User
        fields = ['full_name','email','password1','password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        # split full_name into first & last
        full_name = self.cleaned_data['full_name']
        first, *rest = full_name.split(' ',1)
        user.first_name = first
        user.last_name  = rest[0] if rest else ''
        # use email as username
        user.username   = self.cleaned_data['email']
        user.email      = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = LoanApplication
        fields = [
          'employer_name','job_title','employment_type','monthly_income',
          'amount','duration','credit_score','credit_check','total_savings','assets',
          'collateral_type','collateral_value','existing_debt','purpose'
        ]
        widgets = {
          'credit_check': forms.CheckboxInput(),
          'existing_debt': forms.RadioSelect(choices=[(True,'Yes'),(False,'No')]),
        }
class CustomLoginForm(forms.Form):
    email    = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder':'hello@loanpal.com'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder':'Enter your password'}))
    remember_me = forms.BooleanField(required=False)
