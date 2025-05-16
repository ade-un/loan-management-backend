# loan_core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('home/', views.home, name='home'),  # Modified pattern
    path('apply_for_loan/', views.apply_for_loan, name='apply_for_loan'),
    path('view_recommendations/', views.view_recommendations, name='view_recommendations'),
    path('submit-loan/', views.submit_loan_api, name='submit_loan_api'),
    path('check-application-status/', views.check_application_status, name='check_application_status'),
    path('realtime_data/', views.realtime_data, name='realtime_data'),
    ]
