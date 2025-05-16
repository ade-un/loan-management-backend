from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class LoanApplication(models.Model):
    STATUS_CHOICES = [
        ('pending','Pending'),
        ('approved','Approved'),
        ('rejected','Rejected'),
    ]
    EMPLOYMENT_CHOICES = [
        ('full-time','Full‑Time'),
        ('part-time','Part‑Time'),
        ('self-employed','Self‑Employed'),
        ('unemployed','Unemployed'),
        ('retired','Retired'),
    ]

    user             = models.ForeignKey(User, on_delete=models.CASCADE)
    employer_name    = models.CharField(max_length=100, blank=True, null=True)
    job_title        = models.CharField(max_length=100, blank=True, null=True)
    employment_type  = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES)
    monthly_income   = models.DecimalField(max_digits=12, decimal_places=2)
    amount           = models.DecimalField(max_digits=12, decimal_places=2)
    duration         = models.IntegerField(help_text="months")
    credit_score     = models.IntegerField(blank=True, null=True)
    credit_check     = models.BooleanField(default=False)
    total_savings    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    assets           = models.TextField(blank=True, null=True)

    collateral_type  = models.CharField(max_length=100, blank=True, null=True)
    collateral_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    existing_debt    = models.BooleanField(default=False)
    purpose = models.TextField(blank=True, null=True)
    status           = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} – {self.status}"
    