
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
import re

from .models import *
from .forms import (
    DoctorProfileForm, ResearcherProfileForm, PatientProfileForm
)
from django.conf import settings



# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
import json
from datetime import datetime, timedelta

from .models import User
from .forms import  ProfileForm
from .decorators import is_approved_user, role_required
from .utils import log_event














# Utility functions
def is_admin(user):
    return user.is_authenticated and (user.role == settings.ROLE_ADMIN or user.is_superuser or user.is_staff)



def get_role_based_form(user):
    if user.is_doctor():
        return DoctorProfileForm
    elif user.is_researcher():
        return ResearcherProfileForm
    else:
        return PatientProfileForm

# Helper function for password validation
def validate_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if not re.search(r'[A-Za-z]', password):
        return "Password must contain at least one letter"
    if not re.search(r'\d', password):
        return "Password must contain at least one number"
    return None

# API Login View
@csrf_exempt
@require_POST
def api_login(request):
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', '').strip()
        
        if not username or not password or not role:
            return JsonResponse({
                'success': False,
                'error': 'All fields are required'
            }, status=400)
        
        user = authenticate(username=username, password=password)
        
        if user is not None:
            # Check if user role matches requested role
            # Admin role check includes superusers/staff
            if role == 'admin':
                if not user.is_admin():
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid credentials for admin access'
                    }, status=401)
            elif user.role != role:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid role selection. Your account is registered as {user.get_role_display()}'
                }, status=401)
            
            # Check approval status (skip for superusers/staff)
            if not user.is_superuser and not user.is_staff and not user.is_approved():
                log_event(
                    action='LOGIN',
                    user=user,
                    details={'status': 'pending_approval', 'attempted_role': role},
                    request=request
                )
                return JsonResponse({
                    'success': False,
                    'error': 'Your account is pending admin approval. Please wait for approval email.'
                }, status=403)
            
            login(request, user)
            log_event(
                action='LOGIN',
                user=user,
                details={'status': 'success', 'role': role},
                request=request
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Login successful',
                'user': {
                    'username': user.username,
                    'role': user.role,
                    'full_name': user.full_name
                }
            })
        else:
            # Log failed login attempt
            log_event(
                action='LOGIN',
                user=None,
                details={'status': 'failed', 'username': username, 'role': role},
                request=request
            )
            return JsonResponse({
                'success': False,
                'error': 'Invalid username or password'
            }, status=401)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

# API Registration Views
@csrf_exempt
@require_POST
def api_register_patient(request):
    try:
        data = json.loads(request.body)
        
        # Basic validation
        required_fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }, status=400)
        
        username = data['username'].strip()
        email = data['email'].strip()
        first_name = data['first_name'].strip()
        last_name = data['last_name'].strip()
        password1 = data['password1']
        password2 = data['password2']
        
        # Check if passwords match
        if password1 != password2:
            return JsonResponse({
                'success': False,
                'error': 'Passwords do not match'
            }, status=400)
        
        # Validate password strength
        password_error = validate_password(password1)
        if password_error:
            return JsonResponse({
                'success': False,
                'error': password_error
            }, status=400)
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            return JsonResponse({
                'success': False,
                'error': 'Username already exists'
            }, status=400)
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False,
                'error': 'Email already registered'
            }, status=400)
        
        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                role=settings.ROLE_PATIENT,
                status='pending'
            )
            
            # Add patient-specific fields
            user.date_of_birth = data.get('date_of_birth')
            user.phone = data.get('phone', '')
            user.address = data.get('address', '')
            user.save()
            
            log_event(
                action='REGISTER',
                user=user,
                details={'role': 'patient'},
                request=request
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Patient account created successfully! Awaiting admin approval.',
                'user_id': user.id
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Registration failed: {str(e)}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

@csrf_exempt
@require_POST
def api_register_doctor(request):
    try:
        data = json.loads(request.body)
        
        # Basic validation
        required_fields = ['username', 'email', 'first_name', 'last_name', 'specialization', 'license_number', 'password1', 'password2']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }, status=400)
        
        username = data['username'].strip()
        email = data['email'].strip()
        first_name = data['first_name'].strip()
        last_name = data['last_name'].strip()
        specialization = data['specialization'].strip()
        license_number = data['license_number'].strip()
        password1 = data['password1']
        password2 = data['password2']
        
        # Check if passwords match
        if password1 != password2:
            return JsonResponse({
                'success': False,
                'error': 'Passwords do not match'
            }, status=400)
        
        # Validate password strength
        password_error = validate_password(password1)
        if password_error:
            return JsonResponse({
                'success': False,
                'error': password_error
            }, status=400)
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            return JsonResponse({
                'success': False,
                'error': 'Username already exists'
            }, status=400)
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False,
                'error': 'Email already registered'
            }, status=400)
        
        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                role=settings.ROLE_DOCTOR,
                status='pending'
            )
            
            # Add doctor-specific fields
            user.specialization = specialization
            # Note: Add license_number field to User model if needed
            # For now, store in details or create separate model
            user.save()
            
            log_event(
                action='REGISTER',
                user=user,
                details={
                    'role': 'doctor',
                    'specialization': specialization,
                    'license_number': license_number
                },
                request=request
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Doctor account created successfully! Awaiting admin approval.',
                'user_id': user.id
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Registration failed: {str(e)}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

@csrf_exempt
@require_POST
def api_register_researcher(request):
    try:
        data = json.loads(request.body)
        
        # Basic validation - removed 'credentials' from required fields
        required_fields = ['username', 'email', 'first_name', 'last_name', 'institution', 'research_area', 'password1', 'password2']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }, status=400)
        
        username = data['username'].strip()
        email = data['email'].strip()
        first_name = data['first_name'].strip()
        last_name = data['last_name'].strip()
        institution = data['institution'].strip()
        research_area = data['research_area'].strip()
        password1 = data['password1']
        password2 = data['password2']
        
        # Check if passwords match
        if password1 != password2:
            return JsonResponse({
                'success': False,
                'error': 'Passwords do not match'
            }, status=400)
        
        # Validate password strength
        password_error = validate_password(password1)
        if password_error:
            return JsonResponse({
                'success': False,
                'error': password_error
            }, status=400)
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            return JsonResponse({
                'success': False,
                'error': 'Username already exists'
            }, status=400)
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False,
                'error': 'Email already registered'
            }, status=400)
        
        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                role=settings.ROLE_RESEARCHER,
                status='pending'
            )
            
            # Add researcher-specific fields
            user.institution = institution
            # Note: Add research_area field to User model if needed
            user.save()
            
            log_event(
                action='REGISTER',
                user=user,
                details={
                    'role': 'researcher',
                    'institution': institution,
                    'research_area': research_area,
                },
                request=request
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Researcher account created successfully! Awaiting admin approval.',
                'user_id': user.id
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Registration failed: {str(e)}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)
    
    
# Unified registration endpoint
@csrf_exempt
@require_POST
def api_register(request, role):
    if role == 'patient':
        return api_register_patient(request)
    elif role == 'doctor':
        return api_register_doctor(request)
    elif role == 'researcher':
        return api_register_researcher(request)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Invalid role specified'
        }, status=400)

# Check username availability
@csrf_exempt
@require_POST
def check_username(request):
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        
        if not username:
            return JsonResponse({'available': False, 'error': 'Username is required'}, status=400)
        
        if User.objects.filter(username=username).exists():
            return JsonResponse({'available': False, 'error': 'Username already taken'})
        
        return JsonResponse({'available': True})
        
    except json.JSONDecodeError:
        return JsonResponse({'available': False, 'error': 'Invalid JSON data'}, status=400)

# Check email availability
@csrf_exempt
@require_POST
def check_email(request):
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        
        if not email:
            return JsonResponse({'available': False, 'error': 'Email is required'}, status=400)
        
        if User.objects.filter(email=email).exists():
            return JsonResponse({'available': False, 'error': 'Email already registered'})
        
        return JsonResponse({'available': True})
        
    except json.JSONDecodeError:
        return JsonResponse({'available': False, 'error': 'Invalid JSON data'}, status=400)

# Main views (keeping your existing views)
def login_view(request):
    """Main login view - redirects to unified auth page"""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    return render(request, 'base_auth.html')

def logout_view(request):
    if request.user.is_authenticated:
        log_event(
            action='LOGOUT',
            user=request.user,
            details={},
            request=request
        )
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')

# Keep your existing registration views for backward compatibility
def register_doctor_view(request):
    """Register a new doctor account"""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        # Create user with doctor role
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Doctor specific fields
        specialization = request.POST.get('specialization')
        license_number = request.POST.get('license_number')
        
        # Validation
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register_doctor.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'register_doctor.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'register_doctor.html')
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                role='doctor',
                status='pending'
            )
            
            # Save doctor specific fields
            user.specialization = specialization
            # Save license number in details or separate field
            user.save()
            
            log_event(
                action='REGISTER',
                user=user,
                details={'role': 'doctor', 'specialization': specialization},
                request=request
            )
            
            messages.success(request, 'Doctor registration successful! Please wait for admin approval.')
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'register_doctor.html')
    
    return render(request, 'register_doctor.html')

def register_researcher_view(request):
    """Register a new researcher account"""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        # Create user with researcher role
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Researcher specific fields
        institution = request.POST.get('institution')
        research_area = request.POST.get('research_area')
        credentials = request.POST.get('credentials')
        
        # Validation
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register_researcher.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'register_researcher.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'register_researcher.html')
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                role='researcher',
                status='pending'
            )
            
            # Save researcher specific fields
            user.institution = institution
            user.save()
            
            log_event(
                action='REGISTER',
                user=user,
                details={'role': 'researcher', 'institution': institution},
                request=request
            )
            
            messages.success(request, 'Researcher registration successful! Please wait for admin approval.')
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'register_researcher.html')
    
    return render(request, 'register_researcher.html')

def register_patient_view(request):
    """Register a new patient account"""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        # Create user with patient role
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Patient specific fields
        date_of_birth = request.POST.get('date_of_birth')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        # Validation
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register_patient.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'register_patient.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'register_patient.html')
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                role='patient',
                status='pending'
            )
            
            # Save patient specific fields
            user.date_of_birth = date_of_birth
            user.phone = phone
            user.address = address
            user.save()
            
            log_event(
                action='REGISTER',
                user=user,
                details={'role': 'patient'},
                request=request
            )
            
            messages.success(request, 'Patient registration successful! Please wait for admin approval.')
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'register_patient.html')
    
    return render(request, 'register_patient.html')












































from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Avg, F
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.db import transaction
import json
import re
import uuid
import joblib
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import logging

from .models import *
from .forms import *
from .utils import (
    log_event, send_approval_email, send_welcome_email,
    encrypt_data, decrypt_data, calculate_fuzzy_risk,
    query_ollama, ml_predict, similarity_search
)
from .decorators import role_required, is_approved_user

logger = logging.getLogger(__name__)

# ============================================
# AUTHENTICATION VIEWS (KEEPING EXISTING)
# ============================================

# [Keep all your existing authentication views exactly as they are]
# api_login, api_register_*, check_username, check_email, etc.
# These remain UNCHANGED

# ============================================
# DASHBOARD VIEWS
# ============================================

@login_required
@is_approved_user
def dashboard_redirect(request):
    """Redirect to role-specific dashboard"""
    if request.user.is_admin():
        return redirect('admin_dashboard')
    elif request.user.is_doctor():
        return redirect('doctor_dashboard')
    elif request.user.is_researcher():
        return redirect('researcher_dashboard')
    elif request.user.is_patient():
        return redirect('patient_dashboard')
    return redirect('login')

# ============================================
# ADMIN DASHBOARD
# ============================================

@login_required
@role_required('admin')
def admin_dashboard(request):
    """Admin main dashboard"""
    # Statistics
    total_users = User.objects.count()
    pending_users = User.objects.filter(status='pending').count()
    approved_users = User.objects.filter(status='approved').count()
    
    role_counts = {
        'doctor': User.objects.filter(role='doctor', status='approved').count(),
        'patient': User.objects.filter(role='patient', status='approved').count(),
        'researcher': User.objects.filter(role='researcher', status='approved').count(),
    }
    
    # Recent activity
    recent_users = User.objects.all().order_by('-date_joined')[:5]
    recent_logs = AuditLog.objects.all().order_by('-timestamp')[:10]
    
    # System metrics
    total_records = MedicalRecord.objects.count()
    total_chats = ChatHistory.objects.count()
    total_predictions = AuditLog.objects.filter(action='PREDICTION').count()
    
    # Risk distribution
    risk_distribution = {
        'low': User.objects.filter(risk_level='low').count(),
        'medium': User.objects.filter(risk_level='medium').count(),
        'high': User.objects.filter(risk_level='high').count(),
        'critical': User.objects.filter(risk_level='critical').count(),
    }
    
    # Notifications
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    context = {
        'total_users': total_users,
        'pending_users': pending_users,
        'approved_users': approved_users,
        'role_counts': role_counts,
        'recent_users': recent_users,
        'recent_logs': recent_logs,
        'total_records': total_records,
        'total_chats': total_chats,
        'total_predictions': total_predictions,
        'risk_distribution': risk_distribution,
        'unread_notifications': unread_notifications,
    }
    
    log_event('DASHBOARD_ACCESS', request.user, {'dashboard': 'admin'}, request)
    return render(request, 'admin/dashboard.html', context)

@login_required
@role_required('admin')
def admin_user_approval(request):
    """Approve pending users"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        
        try:
            user = User.objects.get(id=user_id)
            if action == 'approve':
                user.status = 'approved'
                user.save()
                
                # Send approval email
                send_approval_email(user)
                
                # Create notification for user
                Notification.create_notification(
                    user=user,
                    title='Account Approved',
                    message='Your account has been approved by the administrator.',
                    notification_type='success',
                    action_url='/dashboard/'
                )
                
                messages.success(request, f'User {user.username} has been approved.')
                
            elif action == 'reject':
                user.status = 'rejected'
                user.save()
                
                # Send rejection email
                send_mail(
                    'Account Registration Rejected',
                    f'Dear {user.get_full_name()},\n\nYour account registration has been rejected.',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                
                messages.warning(request, f'User {user.username} has been rejected.')
            
            log_event('USER_APPROVAL', request.user, {
                'target_user': user.username,
                'action': action,
                'role': user.role
            }, request)
            
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
    
    pending_users = User.objects.filter(status='pending').order_by('date_joined')
    return render(request, 'admin/user_approval.html', {'pending_users': pending_users})

@login_required
@role_required('admin')
def admin_user_management(request):
    """Manage all users"""
    users = User.objects.all().order_by('-date_joined')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        
        try:
            user = User.objects.get(id=user_id)
            if action == 'activate':
                user.is_active = True
                user.save()
                messages.success(request, f'User {user.username} activated.')
            elif action == 'deactivate':
                user.is_active = False
                user.save()
                messages.warning(request, f'User {user.username} deactivated.')
            
            log_event('USER_MANAGEMENT', request.user, {
                'target_user': user.username,
                'action': action
            }, request)
            
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
    
    context = {
        'users': users,
        'total_users': users.count(),
    }
    return render(request, 'admin/user_management.html', context)

@login_required
@role_required('admin')
def admin_audit_logs(request):
    """View audit logs"""
    logs = AuditLog.objects.all().order_by('-timestamp')
    
    # Filter by action type if specified
    action_type = request.GET.get('action_type')
    if action_type:
        logs = logs.filter(action=action_type)
    
    # Filter by date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)
    
    context = {
        'logs': logs[:100],  # Limit to 100 most recent
        'action_types': AuditLog.ACTION_CHOICES,
    }
    return render(request, 'admin/audit_logs.html', context)


@login_required
@role_required('admin')
def admin_user_detail(request, user_id):
    """View single user details"""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('admin_user_management')

    context = {
        'user_obj': user,
    }

    log_event('USER_DETAIL_VIEW', request.user, {
        'target_user': user.username
    }, request)

    return render(request, 'admin/user_detail.html', context)






















# ============================================
# DOCTOR DASHBOARD
# ============================================

@login_required
@role_required('doctor')
def doctor_dashboard(request):
    """Doctor main dashboard"""
    # Get doctor's patients
    patients = User.objects.filter(role='patient', status='approved').order_by('-last_analysis')
    
    # Get recent medical records created by this doctor
    recent_records = MedicalRecord.objects.filter(
        created_by=request.user
    ).order_by('-created_at')[:5]
    
    # Statistics
    total_patients = patients.count()
    high_risk_patients = patients.filter(risk_level__in=['high', 'critical']).count()
    recent_analyses = patients.filter(last_analysis__isnull=False).count()
    
    # Get unread notifications
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    context = {
        'total_patients': total_patients,
        'high_risk_patients': high_risk_patients,
        'recent_analyses': recent_analyses,
        'patients': patients[:10],  # Show first 10
        'recent_records': recent_records,
        'notifications': notifications,
        'symptom_form': SymptomsForm(),
        # Add patient list for dropdowns
        'patient_list': patients[:20],
    }
    
    log_event('DASHBOARD_ACCESS', request.user, {'dashboard': 'doctor'}, request)
    return render(request, 'doctor/dashboard.html', context)

@login_required
@role_required('doctor')
def doctor_chat(request):
    """Doctor chat with AI assistant"""
    # Get doctor's patients for the patient context dropdown
    patients = User.objects.filter(role='patient', status='approved').order_by('-last_analysis')
    
    # Get chat history
    chat_history = ChatHistory.objects.filter(
        user=request.user,
        role='doctor'
    ).order_by('-created_at')[:10]
    
    context = {
        'patients': patients[:20],
        'chat_history': chat_history,
    }
    return render(request, 'doctor/chat.html', context)

@login_required
@role_required('doctor')
def doctor_patients(request):
    """View and manage patients"""
    patients = User.objects.filter(role='patient', status='approved').order_by('-last_analysis')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        patients = patients.filter(
            Q(username__icontains=search_query) |
            Q(full_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Filter by risk level
    risk_filter = request.GET.get('risk_level', '')
    if risk_filter:
        patients = patients.filter(risk_level=risk_filter)
    
    # Count high risk patients
    high_risk_patients = patients.filter(risk_level__in=['high', 'critical']).count()
    
    context = {
        'patients': patients,
        'search_query': search_query,
        'risk_filter': risk_filter,
        'high_risk_patients': high_risk_patients,
        'risk_levels': User.RISK_LEVEL_CHOICES,
    }
    return render(request, 'doctor/patients.html', context)

@login_required
@role_required('doctor')
def doctor_patient_detail(request, patient_id):
    """View patient details and medical history"""
    patient = get_object_or_404(User, id=patient_id, role='patient')
    medical_records = MedicalRecord.objects.filter(patient=patient).order_by('-created_at')
    
    # Get patient's medical statistics
    total_records = medical_records.count()
    
    context = {
        'patient': patient,
        'medical_records': medical_records,
        'total_records': total_records,
    }
    return render(request, 'doctor/patient_detail.html', context)

@login_required
@role_required('doctor')
@require_POST
def doctor_add_medical_record(request, patient_id):
    """Add a new medical record for a patient"""
    patient = get_object_or_404(User, id=patient_id, role='patient')
    
    try:
        # Get form data
        symptoms_data = request.POST.get('symptoms', '{}')
        diagnosis = request.POST.get('diagnosis', '')
        treatment = request.POST.get('treatment', '')
        notes = request.POST.get('notes', '')
        risk_level = request.POST.get('risk_level', 'low')
        
        # Encrypt the data
        encrypted_symptoms = encrypt_data(symptoms_data)
        encrypted_diagnosis = encrypt_data(diagnosis)
        encrypted_treatment = encrypt_data(treatment)
        encrypted_notes = encrypt_data(notes)
        
        # Create medical record
        medical_record = MedicalRecord.objects.create(
            patient=patient,
            encrypted_data=encrypted_notes,
            encrypted_symptoms=encrypted_symptoms,
            encrypted_diagnosis=encrypted_diagnosis,
            encrypted_treatment=encrypted_treatment,
            created_by=request.user,
            risk_level=risk_level,
            confidence_score=float(request.POST.get('confidence_score', 0.0))
        )
        
        # Update patient's last analysis timestamp
        patient.last_analysis = timezone.now()
        patient.save()
        
        messages.success(request, 'Medical record added successfully.')
        log_event('MEDICAL_RECORD_CREATE', request.user, {
            'patient': patient.username,
            'record_id': str(medical_record.record_id)
        }, request)
        
    except Exception as e:
        messages.error(request, f'Error creating medical record: {str(e)}')
        logger.error(f"Error creating medical record: {e}")
    
    return redirect('doctor_patient_detail', patient_id=patient_id)

@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_ml_analysis(request):
    """Perform ML analysis on symptoms"""
    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        symptoms = data.get('symptoms', [])
        
        if not symptoms:
            return JsonResponse({
                'success': False,
                'error': 'Symptoms data is required'
            })
        
        # Get patient if provided
        patient = None
        if patient_id:
            try:
                patient = User.objects.get(id=patient_id, role='patient')
            except User.DoesNotExist:
                patient = None
        
        # Convert symptoms to feature vector
        symptoms_dict = {symptom: 1 for symptom in symptoms}
        
        # Perform ML prediction
        result = ml_predict(symptoms)
        
        if result['success']:
            # Create chat history entry
            ChatHistory.objects.create(
                user=request.user,
                role='doctor',
                query=json.dumps(symptoms_dict),
                response=json.dumps(result),
                confidence_score=result.get('confidence', 0.0)
            )
            
            # If patient exists, update their record
            if patient:
                # Create a medical record from the analysis
                MedicalRecord.objects.create(
                    patient=patient,
                    encrypted_symptoms=encrypt_data(json.dumps(symptoms_dict)),
                    encrypted_diagnosis=encrypt_data(result.get('prediction', 'Unknown')),
                    created_by=request.user,
                    risk_level=result.get('risk_level', 'low'),
                    confidence_score=result.get('confidence', 0.0)
                )
                
                # Update patient's risk level and confidence
                patient.risk_level = result.get('risk_level', 'low')
                patient.ml_confidence_score = result.get('confidence', 0.0)
                patient.last_analysis = timezone.now()
                patient.save()
            
            # Log the prediction
            log_event('ML_PREDICTION', request.user, {
                'symptoms_count': len(symptoms),
                'prediction': result.get('prediction'),
                'confidence': result.get('confidence'),
                'risk_level': result.get('risk_level'),
                'patient': patient.username if patient else None
            }, request)
            
            return JsonResponse({
                'success': True,
                'result': result
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Prediction failed')
            })
            
    except Exception as e:
        logger.error(f"ML analysis error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_chat_assistant(request):
    """Doctor chat with medical assistant"""
    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        
        if not question:
            return JsonResponse({'success': False, 'error': 'Question is required'})
        
        # Construct prompt for doctor
        prompt = f"""
        You are a medical AI assistant for doctors. 
        Provide professional, evidence-based medical information.
        Use clinical language and be concise.
        Do not provide final diagnoses without proper examination.
        
        Doctor's Question: {question}
        
        Response:
        """
        
        # Query Ollama
        response = query_ollama(prompt)
        
        # Save to chat history
        chat_entry = ChatHistory.objects.create(
            user=request.user,
            role='doctor',
            query=question,
            response=response
        )
        
        # Log the chat
        log_event('CHAT_INTERACTION', request.user, {
            'role': 'doctor',
            'question_length': len(question),
            'chat_id': str(chat_entry.id)
        }, request)
        
        return JsonResponse({
            'success': True,
            'response': response,
            'chat_id': chat_entry.id
        })
        
    except Exception as e:
        logger.error(f"Doctor chat error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@role_required('doctor')
def doctor_medical_history(request):
    """View medical history and analysis"""
    # Get all medical records created by this doctor
    medical_records = MedicalRecord.objects.filter(
        created_by=request.user
    ).order_by('-created_at')
    
    # Get doctor's patients for filter dropdown
    patients = User.objects.filter(role='patient', status='approved')
    
    # Statistics
    total_records = medical_records.count()
    high_risk_records = medical_records.filter(risk_level__in=['high', 'critical']).count()
    
    # Get recent predictions
    recent_predictions = AuditLog.objects.filter(
        user=request.user,
        action='ML_PREDICTION'
    ).order_by('-timestamp')[:10]
    
    context = {
        'medical_records': medical_records[:50],  # Limit to 50
        'total_records': total_records,
        'high_risk_records': high_risk_records,
        'recent_predictions': recent_predictions,
        'patients': patients,
    }
    return render(request, 'doctor/medical_history.html', context)

@login_required
@role_required('doctor')
def doctor_patient_analysis(request, patient_id):
    """Analyze specific patient symptoms"""
    patient = get_object_or_404(User, id=patient_id, role='patient')
    
    # Get patient's recent medical records
    recent_records = MedicalRecord.objects.filter(
        patient=patient
    ).order_by('-created_at')[:5]
    
    context = {
        'patient': patient,
        'recent_records': recent_records,
    }
    return render(request, 'doctor/patient_analysis.html', context)

@login_required
@role_required('doctor')
def doctor_symptom_analyzer(request):
    """Symptom analyzer page"""
    patients = User.objects.filter(role='patient', status='approved').order_by('-last_analysis')
    
    context = {
        'patients': patients,
        'symptom_form': SymptomsForm(),
    }
    return render(request, 'doctor/symptom_analyzer.html', context)

@login_required
@role_required('doctor')
def doctor_emr_analysis(request):
    """EMR analysis page"""
    patients = User.objects.filter(role='patient', status='approved').order_by('-last_analysis')
    
    context = {
        'patients': patients,
    }
    return render(request, 'doctor/emr_analysis.html', context)

@login_required
@role_required('doctor')
def doctor_tools(request):
    """Medical tools page"""
    return render(request, 'doctor/tools.html', context={})

@login_required
@role_required('doctor')
def doctor_appointments(request):
    """Appointments management"""
    # Mock appointments data
    appointments = [
        {
            'id': 1,
            'patient_name': 'John Smith',
            'patient_id': 'P-2024-001',
            'date': '2024-01-15',
            'time': '10:00',
            'type': 'Follow-up',
            'status': 'confirmed'
        },
        {
            'id': 2,
            'patient_name': 'Sarah Johnson',
            'patient_id': 'P-2024-101',
            'date': '2024-01-15',
            'time': '11:30',
            'type': 'Initial Consultation',
            'status': 'pending'
        },
        {
            'id': 3,
            'patient_name': 'Michael Brown',
            'patient_id': 'P-2024-202',
            'date': '2024-01-16',
            'time': '14:00',
            'type': 'Emergency',
            'status': 'confirmed'
        },
    ]
    
    context = {
        'appointments': appointments,
        'today_appointments': [a for a in appointments if a['date'] == '2024-01-15'],
        'upcoming_appointments': [a for a in appointments if a['date'] > '2024-01-15'],
    }
    return render(request, 'doctor/appointments.html', context)

@login_required
@role_required('doctor')
def doctor_reports(request):
    """Reports and analytics"""
    # Get statistics for reports
    patients = User.objects.filter(role='patient', status='approved')
    total_patients = patients.count()
    
    # Risk distribution
    risk_distribution = {
        'low': patients.filter(risk_level='low').count(),
        'medium': patients.filter(risk_level='medium').count(),
        'high': patients.filter(risk_level='high').count(),
        'critical': patients.filter(risk_level='critical').count(),
    }
    
    # Recent activities
    recent_activities = AuditLog.objects.filter(
        user=request.user
    ).order_by('-timestamp')[:10]
    
    context = {
        'total_patients': total_patients,
        'risk_distribution': risk_distribution,
        'recent_activities': recent_activities,
    }
    return render(request, 'doctor/reports.html', context)

@login_required
@role_required('doctor')
def doctor_export_data(request):
    """Export patient data"""
    patients = User.objects.filter(role='patient', status='approved')
    
    if request.method == 'POST':
        # Handle export request
        export_type = request.POST.get('export_type', 'csv')
        patient_ids = request.POST.getlist('patients')
        
        # Process export
        # This would typically generate and return a file
        messages.success(request, f'Export request submitted for {len(patient_ids)} patients.')
        return redirect('doctor_export_data')
    
    context = {
        'patients': patients,
    }
    return render(request, 'doctor/export_data.html', context)

# Helper function for ML prediction
def ml_predict(symptoms):
    """
    Perform ML prediction based on symptoms
    In production, this would call your ML model
    """
    try:
        # Mock ML prediction logic
        # This should be replaced with actual ML model call
        
        # Common conditions mapping
        condition_mapping = {
            ('fever', 'cough', 'fatigue'): 'Upper Respiratory Infection',
            ('headache', 'nausea', 'fever'): 'Migraine',
            ('chest_pain', 'shortness_of_breath'): 'Cardiac Concern',
            ('abdominal_pain', 'nausea', 'vomiting'): 'Gastrointestinal Issue',
            ('joint_pain', 'fever', 'rash'): 'Inflammatory Condition',
        }
        
        # Find best match
        best_match = None
        best_score = 0
        
        for condition_symptoms, condition in condition_mapping.items():
            match_count = len(set(symptoms) & set(condition_symptoms))
            if match_count > best_score:
                best_score = match_count
                best_match = condition
        
        if best_match:
            # Calculate confidence (simplified)
            confidence = min(100, (best_score / max(len(symptoms), 1)) * 100)
            
            # Determine risk level based on condition
            risk_level = 'medium'
            if best_match in ['Cardiac Concern', 'Critical Condition']:
                risk_level = 'high'
            elif best_match in ['Upper Respiratory Infection', 'Migraine']:
                risk_level = 'low'
            
            return {
                'success': True,
                'prediction': best_match,
                'confidence': confidence,
                'risk_level': risk_level,
                'symptoms_analyzed': len(symptoms),
                'explanation': f'Based on the symptoms provided, the most likely condition is {best_match}. This is based on pattern matching of common symptom clusters.',
                'recommendations': [
                    'Consider appropriate diagnostic tests',
                    'Monitor symptom progression',
                    'Consult relevant specialists if needed'
                ]
            }
        else:
            return {
                'success': True,
                'prediction': 'Unspecified Medical Condition',
                'confidence': 65.0,
                'risk_level': 'medium',
                'symptoms_analyzed': len(symptoms),
                'explanation': 'Symptoms do not match common patterns. Further evaluation recommended.',
                'recommendations': [
                    'Comprehensive medical examination',
                    'Basic lab work (CBC, metabolic panel)',
                    'Consider specialist referral'
                ]
            }
            
    except Exception as e:
        logger.error(f"ML prediction error: {e}")
        return {
            'success': False,
            'error': str(e)
        }




















# ============================================
# PATIENT DASHBOARD
# ============================================

@login_required
@role_required('patient')
def patient_dashboard(request):
    """Patient main dashboard"""
    # Get patient's medical info
    medical_records = MedicalRecord.objects.filter(
        patient=request.user
    ).order_by('-created_at')
    
    # Get recent chat history
    recent_chats = ChatHistory.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    # Get notifications
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    context = {
        'medical_records': medical_records[:5],
        'recent_chats': recent_chats,
        'notifications': notifications,
        'risk_level': request.user.risk_level or 'Not assessed',
        'last_analysis': request.user.last_analysis,
        'confidence_score': request.user.ml_confidence_score or 0.0,
    }
    
    log_event('DASHBOARD_ACCESS', request.user, {'dashboard': 'patient'}, request)
    return render(request, 'patient/dashboard.html', context)

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_symptom_checker(request):
    """Patient symptom checker with ML"""
    try:
        data = json.loads(request.body)
        symptom_codes = data.get('symptoms', [])
        
        if not symptom_codes:
            return JsonResponse({
                'success': False,
                'error': 'Please select at least one symptom'
            })
        
        # Convert to symptom dictionary (all symptoms as 0, selected as 1)
        all_symptoms = SymptomsForm.SYMPTOM_CHOICES
        symptom_dict = {}
        for code, name in all_symptoms:
            symptom_dict[code] = 1 if code in symptom_codes else 0
        
        # Perform ML prediction
        result = ml_predict(symptom_codes)
        
        if result['success']:
            # Update patient's medical info
            request.user.risk_level = result.get('risk_level', 'low')
            request.user.ml_confidence_score = result.get('confidence', 0.0)
            request.user.last_analysis = timezone.now()
            request.user.save()
            
            # Create medical record
            encrypted_symptoms = encrypt_data(json.dumps(symptom_dict))
            MedicalRecord.objects.create(
                patient=request.user,
                encrypted_symptoms=encrypted_symptoms,
                risk_level=result.get('risk_level', 'low'),
                confidence_score=result.get('confidence', 0.0)
            )
            
            # Log the prediction
            log_event('PATIENT_SELF_CHECK', request.user, {
                'symptoms_count': len(symptom_codes),
                'prediction': result.get('prediction'),
                'risk_level': result.get('risk_level'),
                'confidence': result.get('confidence')
            }, request)
            
            return JsonResponse({
                'success': True,
                'result': result
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Analysis failed')
            })
            
    except Exception as e:
        logger.error(f"Patient symptom checker error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_health_assistant(request):
    """Patient health assistant chat"""
    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        
        if not question:
            return JsonResponse({'success': False, 'error': 'Question is required'})
        
        # Construct prompt for patient
        prompt = f"""
        You are a healthcare assistant for patients.
        Use simple, clear language that anyone can understand.
        Provide general health information and advice.
        Do NOT provide medical diagnoses.
        Always encourage consulting with a real doctor for medical concerns.
        
        Patient's Question: {question}
        
        Important: If the question involves symptoms or medical conditions,
        remind them to see a doctor.
        
        Response:
        """
        
        # Query Ollama
        response = query_ollama(prompt)
        
        # Save to chat history
        chat_entry = ChatHistory.objects.create(
            user=request.user,
            role='patient',
            query=question,
            response=response
        )
        
        # Log the chat
        log_event('CHAT_INTERACTION', request.user, {
            'role': 'patient',
            'question_length': len(question),
            'chat_id': str(chat_entry.id)
        }, request)
        
        return JsonResponse({
            'success': True,
            'response': response,
            'chat_id': chat_entry.id
        })
        
    except Exception as e:
        logger.error(f"Patient chat error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@role_required('patient')
def patient_medical_history(request):
    """View personal medical history"""
    medical_records = MedicalRecord.objects.filter(
        patient=request.user
    ).order_by('-created_at')
    
    # Get chat history
    chat_history = ChatHistory.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    context = {
        'medical_records': medical_records,
        'chat_history': chat_history,
        'total_records': medical_records.count(),
    }
    return render(request, 'patient/medical_history.html', context)

@login_required
@role_required('patient')
def patient_doctors_list(request):
    """View list of approved doctors"""
    doctors = User.objects.filter(
        role='doctor',
        status='approved',
        is_active=True
    ).order_by('specialization')
    
    # Group by specialization
    specializations = {}
    for doctor in doctors:
        spec = doctor.specialization or 'General'
        if spec not in specializations:
            specializations[spec] = []
        specializations[spec].append(doctor)
    
    context = {
        'doctors': doctors,
        'specializations': specializations,
    }
    return render(request, 'patient/doctors_list.html', context)














# ============================================
# RESEARCHER DASHBOARD
# ============================================

# researcher/views.py
import json
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Avg
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import User, MedicalRecord, ResearchData, ChatHistory, AuditLog, Notification
from core.utils import (
    log_event, query_ollama, encrypt_data, decrypt_data, 
    calculate_fuzzy_risk, similarity_search, ml_predict
)

logger = logging.getLogger(__name__)


@login_required
def researcher_dashboard(request):
    """Researcher main dashboard with comprehensive analytics"""
    try:
        # Basic statistics
        total_analyses = MedicalRecord.objects.count()
        total_patients = User.objects.filter(role='patient', status='approved').count()
        
        # Risk distribution
        risk_distribution = {
            'low': MedicalRecord.objects.filter(risk_level='low').count(),
            'medium': MedicalRecord.objects.filter(risk_level='medium').count(),
            'high': MedicalRecord.objects.filter(risk_level='high').count(),
            'critical': MedicalRecord.objects.filter(risk_level='critical').count(),
        }
        
        # Average confidence score
        avg_confidence = MedicalRecord.objects.aggregate(
            avg_conf=Avg('confidence_score')
        )['avg_conf'] or 0.0
        
        # Get anonymized research data (latest 10)
        research_data = ResearchData.objects.all().order_by('-created_at')[:10]
        
        # Get top predictions (group by prediction)
        top_predictions = ResearchData.objects.values('prediction').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Get recent research activities
        recent_activities = AuditLog.objects.filter(
            Q(user=request.user) | Q(action__in=['RESEARCH_QUERY', 'ENCRYPTED_SEARCH'])
        ).order_by('-timestamp')[:5]
        
        # Get available studies/counts
        total_studies = ResearchData.objects.values('prediction').distinct().count()
        
        context = {
            'total_analyses': total_analyses,
            'total_patients': total_patients,
            'avg_confidence': avg_confidence,
            'risk_distribution': risk_distribution,
            'research_data': research_data,
            'top_predictions': top_predictions,
            'recent_activities': recent_activities,
            'total_studies': total_studies,
        }
        
        log_event('DASHBOARD_ACCESS', request.user, {'dashboard': 'researcher'}, request)
        return render(request, 'researcher/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Researcher dashboard error: {e}")
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return render(request, 'researcher/dashboard.html', {})


@login_required
def researcher_data_explorer(request):
    """Explore anonymized research data with advanced filtering"""
    try:
        # Get all research data
        research_data = ResearchData.objects.all().order_by('-created_at')
        
        # Apply filters from GET parameters
        prediction_filter = request.GET.get('prediction', '')
        risk_filter = request.GET.get('risk_level', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        if prediction_filter:
            research_data = research_data.filter(prediction__icontains=prediction_filter)
        
        if risk_filter:
            research_data = research_data.filter(risk_level=risk_filter)
        
        if date_from:
            research_data = research_data.filter(created_at__date__gte=date_from)
        
        if date_to:
            research_data = research_data.filter(created_at__date__lte=date_to)
        
        # Get unique values for filters
        unique_predictions = ResearchData.objects.values_list(
            'prediction', flat=True
        ).distinct().order_by('prediction')
        
        # Risk levels from model
        risk_levels = [
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ]
        
        # Calculate statistics
        total_records = research_data.count()
        avg_confidence = research_data.aggregate(
            avg_conf=Avg('confidence')
        )['avg_conf'] or 0.0
        
        # Pagination
        paginator = Paginator(research_data, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'research_data': page_obj,
            'total_records': total_records,
            'avg_confidence': avg_confidence,
            'unique_predictions': unique_predictions,
            'risk_levels': risk_levels,
            'prediction_filter': prediction_filter,
            'risk_filter': risk_filter,
            'date_from': date_from,
            'date_to': date_to,
        }
        
        log_event('DATA_EXPLORER_ACCESS', request.user, {
            'filters': {'prediction': prediction_filter, 'risk': risk_filter}
        }, request)
        
        return render(request, 'researcher/data_explorer.html', context)
        
    except Exception as e:
        logger.error(f"Data explorer error: {e}")
        messages.error(request, f"Error loading data explorer: {str(e)}")
        return render(request, 'researcher/data_explorer.html', {})


@csrf_exempt
@login_required
@require_POST
def researcher_analytics_query(request):
    """Perform advanced analytics queries on research data"""
    try:
        data = json.loads(request.body)
        query_type = data.get('query_type', '')
        parameters = data.get('parameters', {})
        
        if not query_type:
            return JsonResponse({'success': False, 'error': 'Query type is required'})
        
        result = {}
        
        if query_type == 'correlation_analysis':
            # Perform correlation analysis
            result = perform_correlation_analysis(parameters)
            
        elif query_type == 'trend_analysis':
            # Perform trend analysis
            result = perform_trend_analysis(parameters)
            
        elif query_type == 'demographic_analysis':
            # Perform demographic analysis
            result = perform_demographic_analysis(parameters)
            
        elif query_type == 'cluster_analysis':
            # Perform cluster analysis
            result = perform_cluster_analysis(parameters)
            
        elif query_type == 'predictive_modeling':
            # Perform predictive modeling
            result = perform_predictive_modeling(parameters)
        
        # Log the query
        log_event('RESEARCH_QUERY', request.user, {
            'query_type': query_type,
            'parameters': parameters,
            'result_size': len(str(result))
        }, request)
        
        return JsonResponse({
            'success': True,
            'result': result,
            'query_type': query_type
        })
        
    except Exception as e:
        logger.error(f"Analytics query error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def perform_correlation_analysis(parameters):
    """Perform correlation analysis between variables"""
    try:
        # Get variables to analyze
        var_x = parameters.get('variable_x', 'confidence')
        var_y = parameters.get('variable_y', 'risk_level')
        analysis_type = parameters.get('analysis_type', 'pearson')
        
        # Sample correlation calculation (simplified)
        # In production, use actual statistical calculations
        
        # Get relevant data
        if var_x == 'confidence' and var_y == 'risk_level':
            # Analyze confidence vs risk level
            data = ResearchData.objects.values('risk_level').annotate(
                avg_confidence=Avg('confidence')
            )
            
            correlation_data = {}
            for item in data:
                risk = item['risk_level']
                confidence = item['avg_confidence']
                correlation_data[risk] = confidence
            
            # Calculate correlation coefficient (simplified)
            # This should be replaced with actual statistical calculation
            if len(correlation_data) >= 2:
                # Mock correlation calculation
                if analysis_type == 'pearson':
                    correlation_coefficient = 0.78
                    p_value = 0.001
                elif analysis_type == 'spearman':
                    correlation_coefficient = 0.82
                    p_value = 0.001
                else:
                    correlation_coefficient = 0.75
                    p_value = 0.002
            else:
                correlation_coefficient = 0.0
                p_value = 1.0
            
            result = {
                'correlation_coefficient': correlation_coefficient,
                'p_value': p_value,
                'analysis_type': analysis_type,
                'variables': {
                    'x': var_x,
                    'y': var_y
                },
                'interpretation': {
                    'strength': 'strong' if abs(correlation_coefficient) > 0.7 else 'moderate',
                    'direction': 'positive' if correlation_coefficient > 0 else 'negative',
                    'significance': 'significant' if p_value < 0.05 else 'not significant'
                },
                'data_points': len(data),
                'raw_data': list(data)
            }
            
            return result
            
    except Exception as e:
        logger.error(f"Correlation analysis error: {e}")
        return {'error': str(e)}
    
    return {'error': 'Invalid parameters'}


def perform_trend_analysis(parameters):
    """Perform trend analysis over time"""
    try:
        # Get parameters
        time_period = parameters.get('time_period', 'monthly')
        metric = parameters.get('metric', 'risk_level')
        start_date = parameters.get('start_date')
        end_date = parameters.get('end_date')
        
        # Set date range
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            if time_period == 'weekly':
                start_date = end_date - timedelta(days=30)
            elif time_period == 'monthly':
                start_date = end_date - timedelta(days=90)
            else:  # quarterly
                start_date = end_date - timedelta(days=180)
        
        # Generate time series data
        trends = []
        current_date = start_date
        
        while current_date <= end_date:
            # Count records for this time period
            if metric == 'risk_level':
                # Get risk level distribution for this date
                count = ResearchData.objects.filter(
                    created_at__date=current_date
                ).count()
                
                # Get risk breakdown
                risk_breakdown = ResearchData.objects.filter(
                    created_at__date=current_date
                ).values('risk_level').annotate(count=Count('id'))
                
                trends.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'value': count,
                    'risk_breakdown': list(risk_breakdown)
                })
            
            elif metric == 'confidence':
                # Get average confidence for this date
                avg_confidence = ResearchData.objects.filter(
                    created_at__date=current_date
                ).aggregate(avg_conf=Avg('confidence'))['avg_conf'] or 0.0
                
                trends.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'value': avg_confidence,
                    'type': 'confidence'
                })
            
            # Move to next date
            if time_period == 'daily':
                current_date += timedelta(days=1)
            elif time_period == 'weekly':
                current_date += timedelta(days=7)
            else:  # monthly
                # Approximate month addition
                current_date = current_date.replace(day=28) + timedelta(days=4)
                current_date = current_date.replace(day=1)
        
        # Calculate trend statistics
        if trends:
            values = [t['value'] for t in trends]
            avg_value = sum(values) / len(values)
            
            # Simple trend detection
            if len(values) >= 2:
                first_half = values[:len(values)//2]
                second_half = values[len(values)//2:]
                avg_first = sum(first_half) / len(first_half)
                avg_second = sum(second_half) / len(second_half)
                
                trend_direction = 'upward' if avg_second > avg_first else 'downward' if avg_second < avg_first else 'stable'
                trend_magnitude = abs((avg_second - avg_first) / avg_first * 100) if avg_first > 0 else 0
            else:
                trend_direction = 'insufficient data'
                trend_magnitude = 0
        
        result = {
            'time_period': time_period,
            'metric': metric,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'trends': trends,
            'statistics': {
                'average': avg_value if trends else 0,
                'total_points': len(trends),
                'trend_direction': trend_direction if trends else 'unknown',
                'trend_magnitude': trend_magnitude if trends else 0
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Trend analysis error: {e}")
        return {'error': str(e)}


def perform_demographic_analysis(parameters):
    """Perform demographic analysis"""
    try:
        demographic_var = parameters.get('demographic_variable', 'age_group')
        health_metric = parameters.get('health_metric', 'risk_level')
        statistical_test = parameters.get('statistical_test', 'chi_square')
        
        # Get demographic data from research data
        if demographic_var == 'age_group':
            demographic_data = ResearchData.objects.values('age_group').annotate(
                total=Count('id'),
                avg_confidence=Avg('confidence')
            ).order_by('age_group')
        elif demographic_var == 'gender':
            demographic_data = ResearchData.objects.values('gender').annotate(
                total=Count('id'),
                avg_confidence=Avg('confidence')
            ).order_by('gender')
        else:  # region
            demographic_data = ResearchData.objects.values('region').annotate(
                total=Count('id'),
                avg_confidence=Avg('confidence')
            ).order_by('region')
        
        # Analyze health metric by demographic
        analysis_results = []
        for item in demographic_data:
            demographic_value = item.get(demographic_var, 'Unknown')
            
            if health_metric == 'risk_level':
                # Get risk level distribution for this demographic
                risk_distribution = ResearchData.objects.filter(
                    **{demographic_var: demographic_value}
                ).values('risk_level').annotate(count=Count('id'))
                
                analysis_results.append({
                    'demographic': demographic_value,
                    'total': item['total'],
                    'avg_confidence': item['avg_confidence'],
                    'risk_distribution': list(risk_distribution)
                })
        
        # Calculate statistical significance (simplified)
        # In production, use actual statistical tests
        chi_square_stat = 24.78
        p_value = 0.0001
        
        result = {
            'demographic_variable': demographic_var,
            'health_metric': health_metric,
            'statistical_test': statistical_test,
            'demographic_analysis': analysis_results,
            'statistical_results': {
                'chi_square_statistic': chi_square_stat,
                'p_value': p_value,
                'degrees_of_freedom': 4,
                'significance': 'highly significant' if p_value < 0.001 else 'significant' if p_value < 0.05 else 'not significant'
            },
            'insights': [
                f"Significant association found between {demographic_var} and {health_metric}",
                "Middle-aged groups show highest condition prevalence",
                "Regional variations in healthcare access may influence outcomes"
            ]
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Demographic analysis error: {e}")
        return {'error': str(e)}


def perform_cluster_analysis(parameters):
    """Perform cluster analysis on research data"""
    try:
        # Simplified cluster analysis
        # In production, use actual clustering algorithms like K-means
        
        # Get sample clusters based on prediction and risk
        clusters = {}
        
        # Group by prediction and risk
        for record in ResearchData.objects.all()[:100]:  # Limit for performance
            key = f"{record.prediction}_{record.risk_level}"
            if key not in clusters:
                clusters[key] = {
                    'prediction': record.prediction,
                    'risk_level': record.risk_level,
                    'count': 0,
                    'avg_confidence': 0,
                    'age_groups': {},
                    'genders': {}
                }
            
            clusters[key]['count'] += 1
            clusters[key]['avg_confidence'] += record.confidence
            
            # Track demographics
            if record.age_group:
                clusters[key]['age_groups'][record.age_group] = \
                    clusters[key]['age_groups'].get(record.age_group, 0) + 1
            
            if record.gender:
                clusters[key]['genders'][record.gender] = \
                    clusters[key]['genders'].get(record.gender, 0) + 1
        
        # Calculate averages and prepare results
        cluster_results = []
        for key, data in clusters.items():
            if data['count'] > 0:
                data['avg_confidence'] = data['avg_confidence'] / data['count']
                
                cluster_results.append({
                    'cluster_id': key,
                    'cluster_label': f"{data['prediction']} ({data['risk_level']})",
                    'size': data['count'],
                    'avg_confidence': round(data['avg_confidence'], 2),
                    'demographics': {
                        'age_distribution': data['age_groups'],
                        'gender_distribution': data['genders']
                    }
                })
        
        # Sort by cluster size
        cluster_results.sort(key=lambda x: x['size'], reverse=True)
        
        result = {
            'total_clusters': len(cluster_results),
            'total_data_points': sum(c['size'] for c in cluster_results),
            'clusters': cluster_results[:10],  # Top 10 clusters
            'cluster_statistics': {
                'largest_cluster': cluster_results[0]['size'] if cluster_results else 0,
                'smallest_cluster': cluster_results[-1]['size'] if cluster_results else 0,
                'avg_cluster_size': sum(c['size'] for c in cluster_results) / len(cluster_results) if cluster_results else 0
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Cluster analysis error: {e}")
        return {'error': str(e)}


def perform_predictive_modeling(parameters):
    """Perform predictive modeling"""
    try:
        # Simplified predictive modeling
        # In production, use actual ML models
        
        target_variable = parameters.get('target_variable', 'risk_level')
        features = parameters.get('features', ['confidence', 'age_group', 'gender'])
        algorithm = parameters.get('algorithm', 'logistic_regression')
        
        # Mock model training results
        model_results = {
            'algorithm': algorithm,
            'target_variable': target_variable,
            'features': features,
            'model_performance': {
                'accuracy': 0.85,
                'precision': 0.82,
                'recall': 0.87,
                'f1_score': 0.84,
                'auc_roc': 0.89
            },
            'feature_importance': [
                {'feature': 'confidence', 'importance': 0.45},
                {'feature': 'age_group', 'importance': 0.28},
                {'feature': 'gender', 'importance': 0.15},
                {'feature': 'region', 'importance': 0.12}
            ],
            'confusion_matrix': {
                'true_positive': 85,
                'false_positive': 12,
                'true_negative': 120,
                'false_negative': 8
            },
            'predictions_sample': [
                {'actual': 'low', 'predicted': 'low', 'confidence': 0.92},
                {'actual': 'medium', 'predicted': 'medium', 'confidence': 0.78},
                {'actual': 'high', 'predicted': 'high', 'confidence': 0.85},
                {'actual': 'critical', 'predicted': 'critical', 'confidence': 0.91}
            ]
        }
        
        return model_results
        
    except Exception as e:
        logger.error(f"Predictive modeling error: {e}")
        return {'error': str(e)}


@csrf_exempt
@login_required
@require_POST
def researcher_encrypted_search(request):
    """Perform encrypted similarity search on medical data"""
    try:
        data = json.loads(request.body)
        query_vector = data.get('query_vector', [])
        threshold = float(data.get('threshold', 0.7))
        max_results = int(data.get('max_results', 10))
        
        if not query_vector:
            return JsonResponse({
                'success': False, 
                'error': 'Query vector is required'
            })
        
        # Convert query vector if it's in string format
        if isinstance(query_vector, str):
            try:
                query_vector = json.loads(query_vector)
            except:
                # Try comma-separated format
                query_vector = [float(x.strip()) for x in query_vector.split(',') if x.strip()]
        
        # Perform similarity search (simplified version)
        # In production, use actual encrypted similarity search
        similar_cases = perform_similarity_search(query_vector, threshold, max_results)
        
        # Create anonymized research data from results
        for case in similar_cases:
            try:
                ResearchData.objects.create(
                    encrypted_features=encrypt_data(json.dumps(query_vector)),
                    prediction=case.get('prediction', 'Unknown'),
                    confidence=case.get('confidence', 0.0),
                    risk_level=case.get('risk_level', 'low'),
                    age_group=case.get('age_group', ''),
                    gender=case.get('gender', ''),
                    region=case.get('region', '')
                )
            except Exception as e:
                logger.error(f"Error saving research data: {e}")
                continue
        
        # Log the search
        log_event('ENCRYPTED_SEARCH', request.user, {
            'query_vector_length': len(query_vector),
            'threshold': threshold,
            'max_results': max_results,
            'results_found': len(similar_cases)
        }, request)
        
        return JsonResponse({
            'success': True,
            'results': similar_cases,
            'total_found': len(similar_cases)
        })
        
    except Exception as e:
        logger.error(f"Encrypted search error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def perform_similarity_search(query_vector, threshold=0.7, max_results=10):
    """Perform similarity search on research data"""
    try:
        # Get all research data for comparison
        research_data = ResearchData.objects.all()[:100]  # Limit for performance
        
        similar_cases = []
        
        for data in research_data:
            try:
                # Decrypt features (in real system, this would be homomorphic comparison)
                encrypted_features = data.encrypted_features
                
                # Simplified similarity calculation
                # In production, use actual vector similarity
                similarity_score = calculate_similarity_score(query_vector, data)
                
                if similarity_score >= threshold:
                    similar_cases.append({
                        'data_id': str(data.data_id)[:8],
                        'similarity_score': similarity_score,
                        'prediction': data.prediction,
                        'risk_level': data.risk_level,
                        'confidence': data.confidence,
                        'age_group': data.age_group or 'Unknown',
                        'gender': data.gender or 'Unknown',
                        'region': data.region or 'Unknown',
                        'created_at': data.created_at.strftime('%Y-%m-%d')
                    })
                    
                    if len(similar_cases) >= max_results:
                        break
                        
            except Exception as e:
                logger.error(f"Error processing research data {data.id}: {e}")
                continue
        
        # Sort by similarity score
        similar_cases.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return similar_cases
        
    except Exception as e:
        logger.error(f"Similarity search error: {e}")
        return []


def calculate_similarity_score(query_vector, research_data):
    """Calculate similarity score between query and research data"""
    try:
        # Simplified similarity calculation
        # In production, use proper vector similarity metrics
        
        # Base similarity based on prediction match
        prediction_similarity = 0.5  # Base value
        
        # Adjust based on risk level
        risk_weights = {'low': 0.1, 'medium': 0.3, 'high': 0.6, 'critical': 0.9}
        risk_similarity = risk_weights.get(research_data.risk_level, 0.3)
        
        # Adjust based on confidence
        confidence_similarity = research_data.confidence / 100.0
        
        # Combine factors
        similarity = (prediction_similarity * 0.3 + 
                     risk_similarity * 0.3 + 
                     confidence_similarity * 0.4)
        
        # Add some randomness for demo purposes
        import random
        similarity += random.uniform(-0.1, 0.1)
        
        # Ensure within bounds
        similarity = max(0.1, min(0.99, similarity))
        
        return similarity
        
    except Exception as e:
        logger.error(f"Similarity calculation error: {e}")
        return 0.5


@csrf_exempt
@login_required
@require_POST
def researcher_chat_assistant(request):
    """Real-time researcher chat with AI assistant using Ollama"""
    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        
        if not question:
            return JsonResponse({'success': False, 'error': 'Question is required'})
        
        # Get researcher context
        researcher = request.user
        research_stats = get_researcher_statistics(researcher)
        
        # Construct comprehensive prompt for Ollama
        prompt = f"""
        You are a medical research AI assistant specialized in healthcare data analysis, 
        epidemiology, and clinical research methodology.
        
        Researcher Context:
        - Name: {researcher.get_full_name()}
        - Institution: {researcher.institution or 'Not specified'}
        - Research Area: {researcher.research_area or 'Medical Research'}
        
        Research Statistics:
        - Total Analyses: {research_stats.get('total_analyses', 0)}
        - Total Patients: {research_stats.get('total_patients', 0)}
        - Recent Predictions: {research_stats.get('recent_predictions', 0)}
        
        Current Date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Instructions:
        1. Provide evidence-based, scientifically accurate information
        2. Cite relevant studies and methodologies when appropriate
        3. Focus on statistical analysis, research design, and data interpretation
        4. Suggest appropriate statistical tests for different research questions
        5. Discuss limitations and ethical considerations
        6. Provide actionable research recommendations
        7. Use academic tone but remain accessible
        
        Researcher's Question: {question}
        
        Provide a comprehensive response addressing:
        1. Key concepts and background
        2. Relevant methodologies and statistical approaches
        3. Potential challenges and solutions
        4. Recommended next steps for research
        5. References to key studies (if applicable)
        
        Response:
        """
        
        # Query Ollama for real-time response
        response = query_ollama(prompt, max_tokens=1000, temperature=0.7)
        
        # If Ollama returns empty response, provide fallback
        if not response or len(response.strip()) < 10:
            response = generate_fallback_response(question, research_stats)
        
        # Save to chat history
        chat_entry = ChatHistory.objects.create(
            user=researcher,
            role='researcher',
            query=question,
            response=response,
            confidence_score=0.9  # High confidence for research responses
        )
        
        # Create notification
        Notification.create_notification(
            user=researcher,
            title='Research Assistant Response',
            message=f'Response generated for your query: {question[:50]}...',
            notification_type='info',
            action_url=f'/researcher/chat-history/'
        )
        
        # Log the chat
        log_event('RESEARCH_CHAT', researcher, {
            'question_length': len(question),
            'response_length': len(response),
            'chat_id': str(chat_entry.id)
        }, request)
        
        return JsonResponse({
            'success': True,
            'response': response,
            'chat_id': chat_entry.id,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Researcher chat error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'fallback_response': generate_fallback_response("Error occurred", {})
        })


def get_researcher_statistics(researcher):
    """Get researcher-specific statistics"""
    try:
        # Calculate time periods
        today = timezone.now().date()
        last_week = today - timedelta(days=7)
        last_month = today - timedelta(days=30)
        
        return {
            'total_analyses': MedicalRecord.objects.count(),
            'total_patients': User.objects.filter(role='patient', status='approved').count(),
            'research_data_count': ResearchData.objects.count(),
            'recent_analyses': MedicalRecord.objects.filter(
                created_at__date__gte=last_week
            ).count(),
            'high_risk_cases': MedicalRecord.objects.filter(
                risk_level__in=['high', 'critical']
            ).count(),
            'avg_confidence': MedicalRecord.objects.aggregate(
                avg_conf=Avg('confidence_score')
            )['avg_conf'] or 0.0,
        }
    except Exception as e:
        logger.error(f"Error getting researcher statistics: {e}")
        return {}


def generate_fallback_response(question, research_stats):
    """Generate fallback response when Ollama is unavailable"""
    import random
    
    fallback_responses = [
        f"""Based on your query about "{question}", here are research considerations:

Methodological Approaches:
1. Consider longitudinal study design for temporal analysis
2. Use multivariate regression for confounding control
3. Implement propensity score matching for observational data
4. Consider mixed-effects models for hierarchical data

Statistical Considerations:
- Sample size calculation required (power > 0.8)
- Adjust for multiple comparisons if applicable
- Consider bootstrapping for confidence intervals
- Validate models using cross-validation

Ethical Considerations:
- Ensure proper anonymization of medical data
- Obtain necessary IRB approvals
- Consider data sharing agreements
- Address potential biases in data collection

Recommended Next Steps:
1. Conduct systematic literature review
2. Develop detailed research protocol
3. Perform pilot study for feasibility
4. Apply for ethical approval""",
        
        f"""For research on "{question}", consider these evidence-based approaches:

Research Design Options:
1. Randomized Controlled Trial (RCT) - highest evidence level
2. Cohort Study - good for risk factor identification
3. Case-Control Study - efficient for rare outcomes
4. Cross-Sectional Study - for prevalence estimation

Data Analysis Methods:
- Use intention-to-treat analysis for RCTs
- Consider survival analysis for time-to-event data
- Apply machine learning for pattern recognition
- Use meta-analysis for evidence synthesis

Quality Assessment:
- Follow CONSORT guidelines for RCT reporting
- Use STROBE checklist for observational studies
- Apply PRISMA guidelines for systematic reviews
- Consider GRADE for evidence quality rating

Implementation Considerations:
- Ensure adequate sample size
- Plan for missing data handling
- Consider subgroup analyses
- Plan sensitivity analyses"""
    ]
    
    # Select random fallback or create custom response
    if "statistic" in question.lower() or "analysis" in question.lower():
        return random.choice(fallback_responses)
    else:
        return f"I've analyzed your query about '{question}' from a research perspective. Based on available data ({research_stats.get('total_analyses', 0)} analyses), I recommend: 1) Systematic literature review, 2) Hypothesis formulation, 3) Study design selection, 4) Statistical power calculation, 5) Ethical approval process."


@login_required
def researcher_export_data(request):
    """Export research data in various formats"""
    try:
        if request.method == 'POST':
            export_format = request.POST.get('export_format', 'csv')
            data_selection = request.POST.get('data_selection', 'filtered')
            include_metadata = request.POST.get('include_metadata', False)
            
            # Get data based on selection
            if data_selection == 'all':
                data = ResearchData.objects.all()
            elif data_selection == 'recent':
                data = ResearchData.objects.filter(
                    created_at__gte=timezone.now() - timedelta(days=30)
                )
            else:  # filtered
                # Get current filters from session or request
                filters = request.session.get('research_filters', {})
                data = ResearchData.objects.all()
                
                if filters.get('prediction'):
                    data = data.filter(prediction__icontains=filters['prediction'])
                if filters.get('risk_level'):
                    data = data.filter(risk_level=filters['risk_level'])
            
            # Create export
            export_result = create_data_export(data, export_format, include_metadata)
            
            # Create notification
            Notification.create_notification(
                user=request.user,
                title='Data Export Complete',
                message=f'Research data exported in {export_format.upper()} format',
                notification_type='success'
            )
            
            log_event('DATA_EXPORT', request.user, {
                'format': export_format,
                'records': data.count(),
                'selection': data_selection
            }, request)
            
            messages.success(request, f'Export completed. {data.count()} records exported.')
            
            # In production, this would return a file download
            return redirect('researcher_data_explorer')
        
        # GET request - show export form
        total_records = ResearchData.objects.count()
        recent_records = ResearchData.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        context = {
            'total_records': total_records,
            'recent_records': recent_records,
            'export_formats': [
                ('csv', 'CSV (Comma Separated Values)'),
                ('json', 'JSON (JavaScript Object Notation)'),
                ('excel', 'Excel Spreadsheet'),
                ('parquet', 'Parquet (Columnar Storage)')
            ]
        }
        
        return render(request, 'researcher/export_data.html', context)
        
    except Exception as e:
        logger.error(f"Export data error: {e}")
        messages.error(request, f'Error exporting data: {str(e)}')
        return redirect('researcher_data_explorer')


def create_data_export(data, format_type, include_metadata):
    """Create data export in specified format"""
    # In production, implement actual export logic
    # This is a placeholder implementation
    
    export_info = {
        'format': format_type,
        'record_count': data.count(),
        'created_at': timezone.now().isoformat(),
        'metadata_included': include_metadata
    }
    
    return export_info


@login_required
def researcher_chat_history(request):
    """View chat history with AI assistant"""
    chat_history = ChatHistory.objects.filter(
        user=request.user,
        role='researcher'
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(chat_history, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'chat_history': page_obj,
        'total_chats': chat_history.count()
    }
    
    return render(request, 'researcher/chat_history.html', context)


@login_required
def researcher_tools(request):
    """Research tools and utilities"""
    # Get available ML models
    from core.models import MLModel
    ml_models = MLModel.objects.filter(is_active=True)
    
    # Get research statistics
    stats = {
        'total_data_points': ResearchData.objects.count(),
        'unique_predictions': ResearchData.objects.values('prediction').distinct().count(),
        'avg_confidence': ResearchData.objects.aggregate(
            avg_conf=Avg('confidence')
        )['avg_conf'] or 0.0,
        'data_coverage': {
            'with_age': ResearchData.objects.exclude(age_group='').count(),
            'with_gender': ResearchData.objects.exclude(gender='').count(),
            'with_region': ResearchData.objects.exclude(region='').count(),
        }
    }
    
    context = {
        'ml_models': ml_models,
        'stats': stats,
        'available_tools': [
            {'name': 'Data Visualization', 'icon': 'chart-bar', 'description': 'Create interactive visualizations'},
            {'name': 'Statistical Analysis', 'icon': 'calculator', 'description': 'Perform statistical tests'},
            {'name': 'Machine Learning', 'icon': 'brain', 'description': 'Train and evaluate ML models'},
            {'name': 'Report Generator', 'icon': 'file-pdf', 'description': 'Generate research reports'},
        ]
    }
    
    return render(request, 'researcher/tools.html', context)


@login_required
def researcher_profile(request):
    """Researcher profile management"""
    researcher = request.user
    
    if request.method == 'POST':
        # Update profile information
        researcher.institution = request.POST.get('institution', '')
        researcher.research_area = request.POST.get('research_area', '')
        researcher.full_name = request.POST.get('full_name', '')
        researcher.phone = request.POST.get('phone', '')
        researcher.address = request.POST.get('address', '')
        
        # Handle profile picture
        if 'profile_picture' in request.FILES:
            researcher.profile_picture = request.FILES['profile_picture']
        
        researcher.save()
        
        messages.success(request, 'Profile updated successfully!')
        
        # Create notification
        Notification.create_notification(
            user=researcher,
            title='Profile Updated',
            message='Your researcher profile has been updated',
            notification_type='success'
        )
        
        log_event('PROFILE_UPDATE', researcher, {'role': 'researcher'}, request)
        
        return redirect('researcher_profile')
    
    # Get researcher statistics
    researcher_stats = {
        'data_points_contributed': ResearchData.objects.count(),
        'analyses_performed': AuditLog.objects.filter(
            user=researcher,
            action__in=['RESEARCH_QUERY', 'ENCRYPTED_SEARCH']
        ).count(),
        'chat_sessions': ChatHistory.objects.filter(user=researcher).count(),
    }
    
    context = {
        'researcher': researcher,
        'stats': researcher_stats,
        'research_focus_areas': [
            'Clinical Research',
            'Epidemiology',
            'Health Informatics',
            'Medical Statistics',
            'Public Health',
            'Biomedical Research'
        ]
    }
    
    return render(request, 'researcher/profile.html', context)

# ============================================
# COMMON VIEWS
# ============================================

@login_required
@is_approved_user
def profile_view(request):
    """User profile management"""
    if request.method == 'POST':
        # Get appropriate form based on role
        if request.user.is_doctor():
            form = DoctorProfileForm(request.POST, request.FILES, instance=request.user)
        elif request.user.is_researcher():
            form = ResearcherProfileForm(request.POST, request.FILES, instance=request.user)
        else:
            form = PatientProfileForm(request.POST, request.FILES, instance=request.user)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            
            # Create notification
            Notification.create_notification(
                user=request.user,
                title='Profile Updated',
                message='Your profile information has been updated successfully.',
                notification_type='success'
            )
            
            log_event('PROFILE_UPDATE', request.user, {}, request)
            return redirect('profile_view')
    else:
        if request.user.is_doctor():
            form = DoctorProfileForm(instance=request.user)
        elif request.user.is_researcher():
            form = ResearcherProfileForm(instance=request.user)
        else:
            form = PatientProfileForm(instance=request.user)
    
    return render(request, f'{request.user.role}/profile.html', {'form': form})

@login_required
def notifications_view(request):
    """View and manage notifications"""
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Mark as read if requested
    if request.method == 'POST':
        notification_id = request.POST.get('notification_id')
        if notification_id:
            try:
                notification = Notification.objects.get(id=notification_id, user=request.user)
                notification.is_read = True
                notification.save()
                
                # Redirect to action URL if exists
                if notification.action_url:
                    return redirect(notification.action_url)
            except Notification.DoesNotExist:
                pass
    
    # Mark all as read
    mark_all_read = request.GET.get('mark_all_read')
    if mark_all_read:
        notifications.update(is_read=True)
        messages.success(request, 'All notifications marked as read.')
        return redirect('notifications_view')
    
    context = {
        'notifications': notifications,
        'unread_count': notifications.filter(is_read=False).count(),
    }
    return render(request, 'common/notifications.html', context)

@login_required
def chat_history_view(request):
    """View chat history"""
    chat_history = ChatHistory.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    context = {
        'chat_history': chat_history[:50],  # Limit to 50
    }
    return render(request, 'common/chat_history.html', context)

# ============================================
# ANALYTICS HELPER FUNCTIONS
# ============================================

def get_risk_distribution_analytics():
    """Get risk distribution analytics"""
    risk_data = {}
    for risk_level, _ in User.RISK_LEVEL_CHOICES:
        count = User.objects.filter(risk_level=risk_level).count()
        risk_data[risk_level] = count
    
    # Add time series data (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_counts = {}
    
    for i in range(30):
        date = timezone.now() - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        count = MedicalRecord.objects.filter(
            created_at__date=date.date()
        ).count()
        daily_counts[date_str] = count
    
    return {
        'risk_distribution': risk_data,
        'daily_analyses': daily_counts,
    }

def get_symptom_correlations():
    """Get symptom correlation analysis"""
    # This is a simplified version
    # In production, you'd analyze actual symptom data
    
    common_correlations = [
        {'symptoms': 'fever,cough', 'frequency': 85, 'common_disease': 'Flu'},
        {'symptoms': 'headache,fatigue', 'frequency': 72, 'common_disease': 'Migraine'},
        {'symptoms': 'nausea,vomiting', 'frequency': 63, 'common_disease': 'Gastroenteritis'},
        {'symptoms': 'chest_pain,breathlessness', 'frequency': 45, 'common_disease': 'Cardiac Issue'},
        {'symptoms': 'joint_pain,fatigue', 'frequency': 58, 'common_disease': 'Arthritis'},
    ]
    
    return common_correlations

def get_demographic_analysis():
    """Get demographic analysis"""
    # Age distribution
    age_groups = {
        '0-18': User.objects.filter(date_of_birth__isnull=False).count(),  # Simplified
        '19-35': 150,  # Placeholder
        '36-50': 120,
        '51-65': 80,
        '66+': 40,
    }
    
    # Gender distribution
    gender_data = {
        'male': 200,
        'female': 180,
        'other': 20,
    }
    
    # Regional distribution
    region_data = {
        'North': 120,
        'South': 150,
        'East': 80,
        'West': 100,
    }
    
    return {
        'age_groups': age_groups,
        'gender_distribution': gender_data,
        'regional_distribution': region_data,
    }

def get_prediction_trends():
    """Get prediction trends over time"""
    trends = []
    
    # Get last 7 days
    for i in range(7):
        date = timezone.now() - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        
        # Count predictions for this date
        count = AuditLog.objects.filter(
            action='ML_PREDICTION',
            timestamp__date=date.date()
        ).count()
        
        trends.append({
            'date': date_str,
            'predictions': count,
        })
    
    return trends



















# ============================================
# UTILITY FUNCTIONS
# ============================================

import joblib
import pandas as pd
import numpy as np
import json
import requests
from cryptography.fernet import Fernet
import hashlib
import base64
from django.conf import settings

# Initialize encryption
def get_encryption_key():
    """Get or create encryption key"""
    key = getattr(settings, 'ENCRYPTION_KEY', None)
    if not key:
        # Generate a new key (in production, this should be stored securely)
        key = Fernet.generate_key()
        settings.ENCRYPTION_KEY = key
    return key

fernet = Fernet(get_encryption_key())

def encrypt_data(data):
    """Encrypt data"""
    if isinstance(data, dict):
        data = json.dumps(data)
    return fernet.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data):
    """Decrypt data"""
    try:
        decrypted = fernet.decrypt(encrypted_data.encode()).decode()
        # Try to parse as JSON
        try:
            return json.loads(decrypted)
        except:
            return decrypted
    except:
        return ""

def calculate_fuzzy_risk(confidence, age=35, severity_factors=0):
    """Calculate fuzzy risk level"""
    # Base risk from confidence
    if confidence < 0.4:
        base_risk = 0.2
    elif confidence < 0.6:
        base_risk = 0.4
    elif confidence < 0.8:
        base_risk = 0.6
    else:
        base_risk = 0.8
    
    # Adjust for age (higher age = higher risk)
    age_factor = min(1.0, age / 80)
    
    # Adjust for severity factors
    severity_factor = min(1.0, severity_factors * 0.1)
    
    # Calculate final risk score
    risk_score = base_risk * 0.6 + age_factor * 0.3 + severity_factor * 0.1
    
    # Map to risk level
    if risk_score < 0.3:
        return "low"
    elif risk_score < 0.5:
        return "medium"
    elif risk_score < 0.7:
        return "high"
    else:
        return "critical"


import requests
import json
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def query_ollama(prompt, model=None, max_tokens=500, temperature=0.7):
    """
    Query Ollama LLM with improved error handling and configuration
    
    Args:
        prompt (str): The input prompt
        model (str): Model name (defaults to settings.OLLAMA_MODEL)
        max_tokens (int): Maximum tokens to generate
        temperature (float): Sampling temperature (0.0 to 1.0)
    
    Returns:
        str: Generated response or error message
    """
    # Get configuration from settings
    model = model or getattr(settings, 'OLLAMA_MODEL', 'llama3')
    host = getattr(settings, 'OLLAMA_HOST', 'http://127.0.0.1:11434')
    
    try:
        # Prepare the request
        url = f"{host}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "stop": ["\n\n", "Human:", "Assistant:"]
            }
        }
        
        logger.debug(f"Querying Ollama at {url} with model: {model}")
        logger.debug(f"Prompt length: {len(prompt)} chars")
        
        # Make the request with timeout
        response = requests.post(
            url,
            json=payload,
            timeout=120,  # 2 minute timeout for longer responses
            headers={'Content-Type': 'application/json'}
        )
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '').strip()
            
            # Log token usage if available
            if 'prompt_eval_count' in result:
                logger.info(
                    f"Ollama response: {result.get('prompt_eval_count', 0)} prompt tokens, "
                    f"{result.get('eval_count', 0)} generated tokens"
                )
            
            return response_text
        else:
            error_msg = f"Ollama API error: {response.status_code}"
            if response.text:
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('error', response.text[:100])}"
                except:
                    error_msg += f" - {response.text[:100]}"
            
            logger.error(error_msg)
            return f"I apologize, but I encountered an error: {error_msg}"
            
    except requests.exceptions.Timeout:
        error_msg = "Request timed out. Ollama might be busy or not responding."
        logger.error(error_msg)
        return "I'm taking too long to respond. Please try again with a simpler query or check if Ollama is running."
    
    except requests.exceptions.ConnectionError:
        error_msg = "Cannot connect to Ollama service. Please ensure Ollama is running."
        logger.error(error_msg)
        return "I cannot connect to the AI service. Please make sure Ollama is running on 127.0.0.1:11434."
    
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error: {str(e)}"
        logger.error(error_msg)
        return f"Network error occurred: {str(e)}"
    
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON response: {str(e)}"
        logger.error(error_msg)
        return "Received an invalid response from the AI service."
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return "An unexpected error occurred. Please try again later."
    



# ML Model Loading and Prediction
ML_MODEL = None
ML_FEATURES = None

def load_ml_model():
    """Load ML model and features"""
    global ML_MODEL, ML_FEATURES
    
    if ML_MODEL is None:
        try:
            # Load trained model
            model_path = settings.BASE_DIR / 'ml_models' / 'disease_predictor.joblib'
            ML_MODEL = joblib.load(model_path)
            
            # Load features
            features_path = settings.BASE_DIR / 'ml_models' / 'features.json'
            with open(features_path, 'r') as f:
                ML_FEATURES = json.load(f)
                
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            ML_MODEL = None
            ML_FEATURES = None
    
    return ML_MODEL, ML_FEATURES

def ml_predict(symptoms_list):
    """Predict disease from symptoms"""
    try:
        model, features = load_ml_model()
        
        if model is None or features is None:
            return {
                'success': False,
                'error': 'ML model not loaded'
            }
        
        # Create feature vector
        feature_vector = np.zeros(len(features))
        for symptom in symptoms_list:
            if symptom in features:
                idx = features.index(symptom)
                feature_vector[idx] = 1
        
        # Make prediction
        prediction = model.predict([feature_vector])[0]
        probabilities = model.predict_proba([feature_vector])[0]
        confidence = max(probabilities)
        
        # Calculate risk level
        risk_level = calculate_fuzzy_risk(confidence)
        
        # Get LLM explanation
        symptoms_text = ", ".join(symptoms_list)
        explanation_prompt = f"""
        Predicted condition: {prediction}
        Confidence: {confidence:.2%}
        Reported symptoms: {symptoms_text}
        
        Provide a brief explanation of what this condition might involve.
        Include general advice and when to see a doctor.
        Do not provide a diagnosis.
        Keep response to 3-4 sentences.
        """
        
        explanation = query_ollama(explanation_prompt)
        
        return {
            'success': True,
            'prediction': prediction,
            'confidence': float(confidence),
            'risk_level': risk_level,
            'explanation': explanation,
            'symptoms_analyzed': len(symptoms_list)
        }
        
    except Exception as e:
        logger.error(f"ML prediction error: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def similarity_search(query_vector, top_k=5):
    """Encrypted similarity search (simplified)"""
    try:
        # In production, this would use proper encrypted similarity search
        # For now, return mock data
        similar_cases = []
        
        # Mock similar cases
        diseases = ['Common Cold', 'Influenza', 'Migraine', 'Gastroenteritis', 'Bronchitis']
        
        for i in range(top_k):
            similar_cases.append({
                'similarity': 0.9 - (i * 0.1),
                'prediction': diseases[i % len(diseases)],
                'risk_level': ['low', 'medium', 'high'][i % 3],
                'age': 25 + (i * 10),
                'gender': ['male', 'female'][i % 2],
            })
        
        return similar_cases
        
    except Exception as e:
        logger.error(f"Similarity search error: {e}")
        return []

def log_event(action, user, details=None, request=None):
    """Log audit event"""
    try:
        audit_log = AuditLog(
            user=user,
            action=action,
            details=details or {}
        )
        
        if request:
            audit_log.ip_address = request.META.get('REMOTE_ADDR')
            audit_log.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        audit_log.save()
        
    except Exception as e:
        logger.error(f"Failed to log event: {e}")

def send_approval_email(user):
    """Send account approval email"""
    try:
        subject = 'Your Account Has Been Approved'
        message = f"""
        Dear {user.get_full_name()},
        
        Your account has been approved by the administrator.
        You can now access the Medical Decision Support System.
        
        Login URL: {settings.SITE_URL}/login/
        
        Role: {user.get_role_display()}
        
        If you have any questions, please contact support.
        
        Best regards,
        Medical Decision Support System Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Approval email sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send approval email: {e}")

def send_welcome_email(user):
    """Send welcome email after registration"""
    try:
        subject = 'Welcome to Medical Decision Support System'
        message = f"""
        Dear {user.get_full_name()},
        
        Thank you for registering with the Medical Decision Support System.
        Your account is pending administrator approval.
        
        You will receive another email once your account is approved.
        
        Registration Details:
        - Username: {user.username}
        - Role: {user.get_role_display()}
        - Status: Pending Approval
        
        If you have any questions, please contact support.
        
        Best regards,
        Medical Decision Support System Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")

# ============================================
# EMAIL INTEGRATION
# ============================================

def send_password_reset_email(user, reset_token):
    """Send password reset email"""
    try:
        reset_url = f"{settings.SITE_URL}/reset-password/{reset_token}/"
        
        subject = 'Password Reset Request'
        message = f"""
        Dear {user.get_full_name()},
        
        You have requested to reset your password.
        Click the link below to reset your password:
        
        {reset_url}
        
        This link will expire in 24 hours.
        
        If you did not request this, please ignore this email.
        
        Best regards,
        Medical Decision Support System Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Password reset email sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")

def send_emergency_alert(patient, doctor, risk_level, prediction):
    """Send emergency alert to doctor"""
    try:
        subject = f'EMERGENCY: High Risk Patient - {patient.get_full_name()}'
        message = f"""
        EMERGENCY ALERT
        
        Patient: {patient.get_full_name()}
        Risk Level: {risk_level.upper()}
        Predicted Condition: {prediction}
        
        Immediate attention required.
        
        Patient Contact: {patient.phone or 'Not provided'}
        
        Please review this case immediately.
        
        Medical Decision Support System
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [doctor.email],
            fail_silently=False,
        )
        
        logger.info(f"Emergency alert sent to doctor {doctor.email}")
        
    except Exception as e:
        logger.error(f"Failed to send emergency alert: {e}")