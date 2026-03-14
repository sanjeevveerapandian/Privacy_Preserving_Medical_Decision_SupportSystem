    # core/views/common_views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from core.models import Notification, AuditLog
from core.utils import log_event

@login_required
def notifications_view(request):
    """View notifications"""
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
                
                if notification.action_url:
                    return redirect(notification.action_url)
            except Notification.DoesNotExist:
                pass
    
    context = {
        'notifications': notifications,
        'unread_count': notifications.filter(is_read=False).count(),
    }
    return render(request, 'common/notifications.html', context)

@login_required
def activity_log(request):
    """View activity log"""
    activities = AuditLog.objects.filter(
        user=request.user
    ).order_by('-timestamp')[:50]
    
    context = {
        'activities': activities,
    }
    return render(request, 'common/activity_log.html', context)