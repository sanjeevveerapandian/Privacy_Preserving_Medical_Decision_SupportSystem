# core/decorators.py
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages

def is_approved_user(view_func):
    """Check if user is approved"""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Allow superusers and staff regardless of status
        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # Check if user is approved
        if not request.user.is_approved():
            messages.warning(request, 'Your account is pending approval. Please wait for admin approval.')
            return redirect('pending_approval')  # You need to create this view
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def role_required(allowed_roles):
    """Check if user has required role"""
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Superusers can access anything
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Convert single role to list
            if isinstance(allowed_roles, str):
                allowed = [allowed_roles]
            else:
                allowed = allowed_roles
            
            # Check if user role is in allowed roles
            if request.user.role not in allowed and not request.user.is_admin():
                raise PermissionDenied("You don't have permission to access this page.")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator