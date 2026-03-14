# views.py (complete fixed version)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
import json
import re
from datetime import datetime, timedelta

from core.models import User, MedicalRecord, ChatSession, ChatMessage, MLModel, Notification, AuditLog, ResearchData
from core.forms import (
    DoctorProfileForm, ResearcherProfileForm, PatientProfileForm,
    ProfileForm, DoctorRegistrationForm, ResearcherRegistrationForm, 
    PatientRegistrationForm, MedicalRecordForm, SymptomsForm
)
from core.decorators import is_approved_user, role_required
from core.utils import log_event
from django.conf import settings

# ============================================
# UTILITY FUNCTIONS
# ============================================

def is_admin(user):
    return user.is_authenticated and (user.role == settings.ROLE_ADMIN or user.is_superuser or user.is_staff)

def get_role_based_form(user):
    if user.is_doctor():
        return DoctorProfileForm
    elif user.is_researcher():
        return ResearcherProfileForm
    else:
        return PatientProfileForm

def validate_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if not re.search(r'[A-Za-z]', password):
        return "Password must contain at least one letter"
    if not re.search(r'\d', password):
        return "Password must contain at least one number"
    return None

# ============================================
# API AUTHENTICATION VIEWS
# ============================================

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
                    'full_name': user.full_name,
                    'email': user.email
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
                role='patient',
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
                role='doctor',
                status='pending'
            )
            
            # Add doctor-specific fields
            user.specialization = specialization
            user.license_number = license_number
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
        
        # Basic validation
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
                role='researcher',
                status='pending'
            )
            
            # Add researcher-specific fields
            user.institution = institution
            user.research_area = research_area
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

@csrf_exempt
@require_POST
def api_register(request, role):
    """Unified registration endpoint"""
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

@csrf_exempt
@require_POST
def check_username(request):
    """Check username availability"""
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

@csrf_exempt
@require_POST
def check_email(request):
    """Check email availability"""
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

# ============================================
# HTML VIEWS (for backward compatibility)
# ============================================

def login_view(request):
    """Main login view"""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    return render(request, 'base_auth.html')

def logout_view(request):
    """Logout view"""
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

def register_doctor_view(request):
    """HTML doctor registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = DoctorRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                log_event(
                    action='REGISTER',
                    user=user,
                    details={'role': 'doctor', 'specialization': user.specialization},
                    request=request
                )
                messages.success(request, 'Doctor registration successful! Please wait for admin approval.')
                return redirect('login')
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = DoctorRegistrationForm()
    
    return render(request, 'register_doctor.html', {'form': form})

def register_researcher_view(request):
    """HTML researcher registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = ResearcherRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                log_event(
                    action='REGISTER',
                    user=user,
                    details={'role': 'researcher', 'institution': user.institution},
                    request=request
                )
                messages.success(request, 'Researcher registration successful! Please wait for admin approval.')
                return redirect('login')
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = ResearcherRegistrationForm()
    
    return render(request, 'register_researcher.html', {'form': form})

def register_patient_view(request):
    """HTML patient registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
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
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = PatientRegistrationForm()
    
    return render(request, 'register_patient.html', {'form': form})

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
# ADMIN VIEWS
# ============================================

@login_required
def admin_pending_count(request):
    """API endpoint to get count of pending users"""
    if not request.user.is_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    pending_count = User.objects.filter(status='pending').count()
    return JsonResponse({'pending_count': pending_count})

# ============================================
# PROFILE VIEWS
# ============================================

@login_required
@is_approved_user
def profile_view(request):
    """View and update user profile"""
    user = request.user
    FormClass = get_role_based_form(user)
    
    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = FormClass(instance=user)
    
    context = {
        'form': form,
        'user': user
    }
    return render(request, 'profile.html', context)

# ============================================
# DASHBOARD TEMPLATES
# ============================================

@login_required
@is_approved_user
@role_required('admin')
def admin_dashboard(request):
    """Admin dashboard"""
    pending_users = User.objects.filter(status='pending')
    total_users = User.objects.count()
    approved_users = User.objects.filter(status='approved').count()
    
    # Recent activity
    recent_logs = AuditLog.objects.all().order_by('-timestamp')[:10]
    
    context = {
        'pending_users': pending_users,
        'total_users': total_users,
        'approved_users': approved_users,
        'recent_logs': recent_logs,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)

@login_required
@is_approved_user
@role_required('doctor')
def doctor_dashboard(request):
    """Doctor dashboard"""
    doctor = request.user
    
    # Get assigned patients
    # Assuming you have a model for doctor-patient relationships
    # For now, show all patients
    patients = User.objects.filter(role='patient', status='approved')
    
    # Recent medical records
    recent_records = MedicalRecord.objects.all().order_by('-created_at')[:5]
    
    context = {
        'doctor': doctor,
        'patients': patients,
        'recent_records': recent_records,
        'total_patients': patients.count(),
    }
    return render(request, 'dashboard/doctor_dashboard.html', context)

@login_required
@is_approved_user
@role_required('researcher')
def researcher_dashboard(request):
    """Researcher dashboard"""
    researcher = request.user
    
    # Research data
    research_data = ResearchData.objects.all().order_by('-created_at')[:10]
    
    # Statistics
    total_data = ResearchData.objects.count()
    high_risk = ResearchData.objects.filter(risk_level='high').count()
    
    context = {
        'researcher': researcher,
        'research_data': research_data,
        'total_data': total_data,
        'high_risk': high_risk,
    }
    return render(request, 'dashboard/researcher_dashboard.html', context)

@login_required
@is_approved_user
@role_required('patient')
def patient_dashboard(request):
    """Patient dashboard"""
    patient = request.user
    
    # Medical records
    medical_records = MedicalRecord.objects.filter(patient=patient).order_by('-created_at')
    
    # Notifications
    notifications = Notification.objects.filter(user=patient, is_read=False).order_by('-created_at')[:5]
    
    context = {
        'patient': patient,
        'medical_records': medical_records,
        'notifications': notifications,
        'total_records': medical_records.count(),
    }
    return render(request, 'dashboard/patient_dashboard.html', context)



# Add to views.py
def pending_approval(request):
    """View for users with pending approval"""
    if request.user.is_authenticated and request.user.is_approved():
        return redirect('dashboard_redirect')
    return render(request, 'pending_approval.html')