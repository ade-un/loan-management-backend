from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from .forms import CustomLoginForm, LoanApplicationForm, UserRegistrationForm
from .models import LoanApplication
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist
def login_view(request):
    if request.method == 'POST':
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
                if user:
                    login(request, user)
                    return redirect('home')
                messages.error(request, 'Invalid login credentials')
            except User.DoesNotExist:
                messages.error(request, 'No user found with that email address')
    else:
        form = CustomLoginForm()
    return render(request, 'loan_core/login.html', {'form': form})

def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                messages.error(request, 'An account with that email already exists.')
                return render(request, 'loan_core/register.html', {'form': form, 'duplicate': True})
            messages.success(request, 'Account created successfully!')
            return render(request, 'loan_core/register.html', {'form': UserRegistrationForm(), 'registered': True})
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserRegistrationForm()
    return render(request, 'loan_core/register.html', {'form': form})

@login_required
def apply_for_loan(request):
    # Fetch the user's latest loan application
    latest_application = None
    try:
        latest_application = LoanApplication.objects.filter(user=request.user).latest('created_at')
    # --- ObjectDoesNotExist needs to be imported to be caught here ---
    except ObjectDoesNotExist:
        # No application found, latest_application remains None
        pass

    # --- Prepare context for the template ---
    context = {
        'form_disabled': False,
        'application': latest_application,
        'status_popup': None, # Flag to indicate which popup to show
        'redirect_url': None, # URL for JS redirect if needed
    }

    if latest_application:
        if latest_application.status == 'pending':
            context['form_disabled'] = True
            context['status_popup'] = 'pending'
            # No need for Django message here if using JS popup on load
            # messages.info(request, 'You have a pending loan application under review...')

        elif latest_application.status == 'approved':
            context['status_popup'] = 'approved'
            # Get the URL string for the redirect using redirect object's url
            context['redirect_url'] = redirect('view_recommendations').url
            # Do NOT return redirect here. We want to render the page first for the JS popup.
            # messages.success(request, 'Your loan application was approved! See your recommended options.') # Keep for non-JS fallback

        # If status is 'rejected', context remains default (form_disabled=False).
        # The form will be shown, and we can add a message if desired.
        # elif latest_application.status == 'rejected':
        #      messages.warning(request, 'Your previous loan application was rejected. You may reapply.')

    # If no application, or the latest is 'rejected', we prepare the form.
    if not context['form_disabled']: # Only create form if it's needed
        context['form'] = LoanApplicationForm(request.POST or None)

    # Render the template with the determined context
    # This view now only handles GET requests to display status or form.
    # POST requests for new applications are handled by submit_loan_api.
    if request.method == 'POST':
         # This block should theoretically not be hit if the HTML form action
         # is correctly pointing to submit_loan_api and AJAX is used.
         # However, as a safeguard or non-AJAX fallback, you could
         # process the form here if needed, but ensure it respects
         # the pending status check like submit_loan_api does.
         # For this implementation assuming AJAX to submit_loan_api:
         return HttpResponse("Method not allowed unless submitting via API.", status=405) # Or handle form post if desired


    return render(request, 'loan_core/apply_for_loan.html', context)
@login_required
@csrf_exempt # Be cautious with csrf_exempt in production, consider csrf_protect or specific handling
@require_POST
def submit_loan_api(request):
    # This view handles the AJAX POST submission of a *new* application.
    # It should check for existing pending applications before saving.

    # Check existing pending application before processing the new form
    existing_pending = LoanApplication.objects.filter(user=request.user, status="pending").first()
    if existing_pending:
        return JsonResponse({
            "status": "error",
            "message": "You already have a pending application. Please wait for processing."
        }, status=400) # Use 400 Bad Request for client error

    form = LoanApplicationForm(request.POST)
    if not form.is_valid():
        # Extract all form errors into a single message string
        error_messages = []
        for field, errors in form.errors.items():
            for error in errors:
                 error_messages.append(f"{field}: {error}") # Include field name for clarity
        message = "Form errors: " + ", ".join(error_messages) if error_messages else "Invalid form data."

        return JsonResponse({
            "status": "error",
            "message": message
        }, status=400) # Use 400 Bad Request for client error

    # If no pending application and form is valid, save the new application
    loan = form.save(commit=False)
    loan.user = request.user
    loan.status = "pending" # New applications start as pending
    loan.save()

    # Return success response
    return JsonResponse({"status": "success", "message": "Application submitted successfully!"}) # Add message to success response

@login_required
def view_recommendations(request):
    """
    View to display loan recommendations for users with approved loan applications.
    If no approved application exists, redirect to the loan application page.
    """
    try:
        # Get the user's latest loan application
        loan_application = LoanApplication.objects.filter(user=request.user).latest('created_at')
        
        # Check if the application is approved
        if loan_application.status != 'approved':
            messages.warning(
                request,
                'Your loan application is not yet approved. Please wait for approval or submit an application.'
            )
            return redirect('apply_for_loan')
            
        # If approved, calculate risk score and get recommendations
        risk_score = calculate_risk_score(loan_application)
        recommendations = get_recommendations(risk_score)
        
        # For the frontend data setup - prepare the recommendation data
        recommendation_data = []
        
        for i, rec in enumerate(recommendations):
            # Add classification details based on recommendation position
            recommendation_level = "Best Match"
            badge_class = "badge-best"
            rating_class = "best"
            
            if i == 1:
                recommendation_level = "Good Option"
                badge_class = "badge-good"
                rating_class = "good"
            elif i > 1:
                recommendation_level = "Basic Option"
                badge_class = "badge-basic"
                rating_class = "basic"
                
            # Calculate monthly payment (simple calculation)
            monthly_payment = (rec['amount'] * (1 + rec['interest_rate']/100)) / rec['term']
            
            # Create a structured recommendation object
            recommendation = {
                'productId': f"loan-{i+1}",
                'productName': rec['name'],
                'loanAmount': rec['amount'],
                'interestRate': rec['interest_rate'],
                'termMonths': rec['term'],
                'monthlyPayment': monthly_payment,
                'processingFeePercentage': 1.5,  # Example processing fee
                'recommendationLevel': recommendation_level,
                'badgeClass': badge_class,
                'ratingClass': rating_class,
                'isBestRate': i == 0,  # Best rate for first recommendation
                'features': [
                    "Quick approval process",
                    "No collateral required",
                    "Flexible repayment options",
                    "No hidden charges"
                ],
                'eligibilityRequirements': [
                    "Nigerian citizen or resident",
                    "Aged 18 years and above",
                    "Steady source of income",
                    "Valid government ID"
                ]
            }
            recommendation_data.append(recommendation)
        
        # User data for the profile section
        user_data = {
            'monthlyIncome': loan_application.monthly_income,
            'creditScore': risk_score,
            'debtToIncomeRatio': '25',  # Example value
            'bankingHistory': '3+ years',  # Example value
            'creditFactors': {
                'paymentHistory': 'Good',
                'creditUtilization': '30%',
                'creditHistoryLength': '3 years',
                'recentInquiries': 'None'
            }
        }
        
        return render(request, 'loan_core/view_recommendations.html', {
            'loan_application': loan_application,
            'risk_score': risk_score,
            'recommendations': recommendation_data,
            'user_data': user_data
        })
        
    except LoanApplication.DoesNotExist:
        messages.warning(
            request,
            'You need to submit a loan application first to get recommendations.'
        )
        return redirect('apply_for_loan')

@login_required
def home(request):
    try:
        loan = LoanApplication.objects.filter(user=request.user).latest('created_at')
        risk = calculate_risk_score(loan)
        recs = get_recommendations(risk)
    except LoanApplication.DoesNotExist:
        loan = None
        risk = 0
        recs = []

    data = {
        'firstName': request.user.first_name or '',
        'lastName': request.user.last_name or '',
        'email': request.user.email,
        'loanAmount': loan.amount if loan else 0,
        'loanPurpose': loan.purpose if loan else '',
        'monthlyIncome': loan.monthly_income if loan else 0,
        'creditScore': risk,
        'loanStatus': loan.status if loan else 'none',
        'loanApplicationDate': loan.created_at.strftime("%Y-%m-%d") if loan else '',
        'lastLogin': request.user.last_login.strftime("%Y-%m-%dT%H:%M:%S") if request.user.last_login else '',
        'location': 'Lagos, Nigeria',
'recommendedLoan': {
    'amount': recs[0].get('amount', 0) if recs else 0,
    'interestRate': recs[0].get('interest_rate', 0) if recs else 0,
    'term': recs[0].get('term', 0) if recs else 0
},
        'activities': []
    }
    return render(request, 'loan_core/home.html', {'user_data': data})

@login_required
def realtime_data(request):
    try:
        loan_application = LoanApplication.objects.filter(user=request.user).latest('created_at')
        risk_score = calculate_risk_score(loan_application)
    except LoanApplication.DoesNotExist:
        loan_application = None
        risk_score = 0

    user_data = {
        'firstName': request.user.first_name or '',
        'lastName': request.user.last_name or '',
        'email': request.user.email,
        'loanAmount': loan_application.amount if loan_application else 0,
        'loanPurpose': loan_application.purpose if loan_application else '',
        'employmentStatus': loan_application.employment_type if loan_application else '',
        'monthlyIncome': loan_application.monthly_income if loan_application else 0,
        'creditScore': risk_score,
        'loanStatus': loan_application.status if loan_application else 'none',
        'loanApplicationDate': loan_application.created_at.strftime("%Y-%m-%d") if loan_application else '',
        'lastLogin': request.user.last_login.strftime("%Y-%m-%dT%H:%M:%S") if request.user.last_login else '',
        'location': 'Lagos, Nigeria',
        'recommendedLoan': {
            'amount': 2500000,
            'interestRate': 12.5,
            'term': 24
        },
        'activities': []
    }
    return JsonResponse(user_data)

def calculate_risk_score(application):
    if not application:
        return 0

    score = 50
    scores = {'employed': 20, 'self-employed': 15, 'unemployed': -10, 'retired': 5}
    score += scores.get(application.employment_type, 0)

    inc = application.monthly_income or 0
    if inc > 500000:
        score += 15
    elif inc > 200000:
        score += 10
    elif inc > 100000:
        score += 5
    elif inc < 50000:
        score -= 10

    amt = application.amount or 0
    ratio = inc / amt if inc and amt else 0
    if ratio > 5:
        score -= 20
    elif ratio > 3:
        score -= 10
    elif ratio > 1:
        score -= 5
    else:
        score += 5

    if application.existing_debt:
        score -= 15

    return max(1, min(100, score))

def get_recommendations(risk_score):
    if risk_score >= 80:
        return [{
            "name": "Personal Loan (Low Interest Rate)",
            "amount": 5000000,
            "interest_rate": 5,
            "term": 36
        }]
    elif risk_score >= 65:
        return [{
            "name": "Small Business Loan",
            "amount": 2000000,
            "interest_rate": 10,
            "term": 24
        }]
    elif risk_score >= 50:
        return [{
            "name": "Emergency Loan",
            "amount": 1000000,
            "interest_rate": 15,
            "term": 18
        }]
    elif risk_score >= 35:
        return [{
            "name": "Micro Loan (20-25%)",
            "amount": 500000,
            "interest_rate": 22,
            "term": 12
        }]
    else:
        return [{
            "name": "Basic Micro Loan",
            "amount": 200000,
            "interest_rate": 28,
            "term": 6
        }]

@login_required
@csrf_exempt
@require_POST
def submit_loan_api(request):
    form = LoanApplicationForm(request.POST)
    if not form.is_valid():
        # pull out first error message
        message = next(iter(form.errors.values()))[0]
        return JsonResponse({
            "status": "error",
            "message": message
        }, status=400)

    # check existing pending
    existing = LoanApplication.objects.filter(user=request.user, status="pending").first()
    if existing:
        return JsonResponse({
            "status": "error",
            "message": "You already have a pending application. Please wait for approval or rejection."
        }, status=400)

    loan = form.save(commit=False)
    loan.user = request.user
    loan.status = "pending"
    loan.save()

    return JsonResponse({"status": "success"})

@login_required
def check_application_status(request):
    """
    AJAX endpoint: has the user already got a pending loan?
    """
    has_pending = LoanApplication.objects.filter(
        user=request.user, status='pending'
    ).exists()
    return JsonResponse({'already_applied': has_pending})

