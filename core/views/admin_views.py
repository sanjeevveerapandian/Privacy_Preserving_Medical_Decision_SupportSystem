from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import json

from core.decorators import role_required
from core.models import User, MedicalRecord, ChatSession, AuditLog, Notification
from core.utils import log_event, send_approval_email

@login_required
@role_required('admin')
def admin_dashboard(request):
    """Admin dashboard"""

    # Base queryset (exclude superuser)
    users_qs = User.objects.filter(is_superuser=False)

    # Statistics
    total_users = users_qs.count()
    pending_users = users_qs.filter(status='pending').count()
    approved_users = users_qs.filter(status='approved').count()

    role_counts = {
        'doctor': users_qs.filter(role='doctor', status='approved').count(),
        'patient': users_qs.filter(role='patient', status='approved').count(),
        'researcher': users_qs.filter(role='researcher', status='approved').count(),
    }

    # Recent activity (exclude superuser)
    recent_users = users_qs.order_by('-date_joined')[:5]
    recent_logs = AuditLog.objects.all().order_by('-timestamp')[:10]

    context = {
        'total_users': total_users,
        'pending_users': pending_users,
        'approved_users': approved_users,
        'role_counts': role_counts,
        'recent_users': recent_users,
        'recent_logs': recent_logs,
    }

    log_event('DASHBOARD_ACCESS', request.user, {'dashboard': 'admin'}, request)
    return render(request, 'admin/dashboard.html', context)


@login_required
@role_required('admin')
def admin_user_approval(request):
    """Approve pending users"""
    pending_users = User.objects.filter(status='pending',is_superuser=False).order_by('date_joined')
    
    # Get recently processed users (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recently_approved = User.objects.filter(
        status='approved',
        updated_at__gte=seven_days_ago
    ).order_by('-updated_at')[:10]
    
    recently_rejected = User.objects.filter(
        status='rejected',
        updated_at__gte=seven_days_ago
    ).order_by('-updated_at')[:10]
    
    context = {
        'pending_users': pending_users,
        'recently_approved': recently_approved,
        'recently_rejected': recently_rejected,
    }
    
    log_event('USER_APPROVAL_PAGE', request.user, {}, request)
    return render(request, 'admin/user_approval.html', context)

@login_required
@role_required('admin')
def approve_user_api(request, user_id):
    """API endpoint to approve a user"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        user = User.objects.get(id=user_id, status='pending')
        user.status = 'approved'
        user.is_active = True
        user.approved_by = request.user
        user.updated_at = timezone.now()
        user.save()
        
        # Send approval email
        try:
            send_approval_email(user)
        except Exception as e:
            print(f"Failed to send approval email: {e}")
        
        log_event('USER_APPROVAL', request.user, {
            'target_user': user.username,
            'action': 'approve',
            'role': user.role
        }, request)
        
        return JsonResponse({'success': True, 'message': f'User {user.username} approved successfully'})
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found or already processed'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@role_required('admin')
def reject_user_api(request, user_id):
    """API endpoint to reject a user"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        reason = data.get('reason', 'No reason provided')
        
        user = User.objects.get(id=user_id, status='pending',is_superuser=False)
        user.status = 'rejected'
        user.is_active = False
        user.rejection_reason = reason
        user.updated_at = timezone.now()
        user.save()
        
        # Send rejection email
        try:
            send_mail(
                'Account Registration Rejected',
                f'Dear {user.get_full_name() or user.username},\n\n'
                f'Your account registration has been rejected.\n'
                f'Reason: {reason}\n\n'
                f'If you believe this is an error, please contact support.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Failed to send rejection email: {e}")
        
        log_event('USER_REJECTION', request.user, {
            'target_user': user.username,
            'action': 'reject',
            'role': user.role,
            'reason': reason
        }, request)
        
        return JsonResponse({'success': True, 'message': f'User {user.username} rejected successfully'})
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found or already processed'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@role_required('admin')
def approve_all_users_api(request):
    """API endpoint to approve all pending users"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        pending_users = User.objects.filter(status='pending')
        approved_count = 0
        
        for user in pending_users:
            user.status = 'approved'
            user.is_active = True
            user.approved_by = request.user
            user.updated_at = timezone.now()
            user.save()
            approved_count += 1
            
            # Send approval email
            try:
                send_approval_email(user)
            except Exception as e:
                print(f"Failed to send approval email to {user.email}: {e}")
        
        log_event('BULK_APPROVAL', request.user, {
            'action': 'approve_all',
            'count': approved_count
        }, request)
        
        return JsonResponse({
            'success': True, 
            'message': f'Successfully approved {approved_count} user(s)',
            'count': approved_count
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})




@login_required
@role_required('admin')
def admin_user_management(request):
    """Manage all users"""

    users = User.objects.filter(is_superuser=False)

    # 🔍 SEARCH
    search = request.GET.get('search')
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    # 🎭 ROLE FILTER
    role = request.GET.get('role')
    if role:
        users = users.filter(role=role)

    # ✅ STATUS FILTER
    status = request.GET.get('status')
    if status:
        users = users.filter(status=status)

    users = users.order_by('-date_joined')

    # 🔁 ACTIVATE / DEACTIVATE
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

            log_event(
                'USER_MANAGEMENT',
                request.user,
                {'target_user': user.username, 'action': action},
                request
            )

        except User.DoesNotExist:
            messages.error(request, 'User not found.')

    context = {
        'users': users,
        'total_users': users.count(),
        'search': search,
        'role': role,
        'status': status,
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
    
    context = {
        'logs': logs[:100],
        'action_types': AuditLog.ACTION_CHOICES,
    }
    return render(request, 'admin/audit_logs.html', context)

@login_required
@role_required('admin')
def admin_user_detail(request, user_id):
    """View user details"""
    user = get_object_or_404(User, id=user_id)
    
    context = {
        'user_obj': user,
    }
    
    log_event('USER_DETAIL_VIEW', request.user, {
        'target_user': user.username
    }, request)
    
    return render(request, 'admin/user_detail.html', context)

@login_required
@role_required('admin')
def admin_system_monitoring(request):
    """System monitoring"""
    # Get system statistics
    last_24_hours = timezone.now() - timedelta(hours=24)
    
    system_stats = {
        'active_users_24h': User.objects.filter(last_login__gte=last_24_hours).count(),
        'new_registrations_24h': User.objects.filter(date_joined__gte=last_24_hours).count(),
        'total_chats': ChatSession.objects.count(),
        'total_predictions': AuditLog.objects.filter(action='PREDICTION').count(),
        'storage_usage': '2.5 GB',  # Mock data
        'active_sessions': 15,  # Mock data
    }
    
    context = {
        'system_stats': system_stats,
    }
    return render(request, 'admin/system_monitoring.html', context)