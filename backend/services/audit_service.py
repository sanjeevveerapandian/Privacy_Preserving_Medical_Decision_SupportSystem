import hmac
import hashlib
import json
import os
from django.conf import settings
from core.models import DataAccessLog

# Use a secret key for signing logs
# In production, this should be in an environment variable or secret manager
LOG_SIGNING_KEY = getattr(settings, 'LOG_SIGNING_KEY', settings.SECRET_KEY).encode()

class AuditService:
    """Service for tamper-proof audit logging"""
    
    @staticmethod
    def log_action(user, action, resource_type, resource_id, request=None):
        """Create a cryptographically signed log entry"""
        ip_address = None
        user_agent = ""
        
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_USER_AGENT', '')

        # Create the log entry first (signature will be added after)
        log = DataAccessLog.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Sign the log
        log.signature = AuditService._generate_signature(log)
        log.save(update_fields=['signature'])
        
        return log

    @staticmethod
    def _generate_signature(log):
        """Generate HMAC-SHA256 signature for a log entry"""
        # Create a string representation of the log's important fields
        payload = {
            "log_id": str(log.log_id),
            "user_id": str(log.user.id) if log.user else "None",
            "action": log.action,
            "resource_id": log.resource_id,
            "timestamp": log.created_at.isoformat()
        }
        
        # Sort keys to ensure consistent hashing
        data_string = json.dumps(payload, sort_keys=True).encode()
        
        # Create signature
        signature = hmac.new(LOG_SIGNING_KEY, data_string, hashlib.sha256).hexdigest()
        return signature

    @staticmethod
    def verify_log(log):
        """Verify if a log entry has been tampered with"""
        if not log.signature:
            return False
            
        expected_signature = AuditService._generate_signature(log)
        return hmac.compare_digest(log.signature, expected_signature)

    @staticmethod
    def verify_all_logs():
        """Audit all logs and return list of tampered entries"""
        tampered_logs = []
        for log in DataAccessLog.objects.all():
            if not AuditService.verify_log(log):
                tampered_logs.append(log)
        return tampered_logs

audit_service = AuditService()

def log_event(action, user=None, details=None, request=None):
    """Backward compatibility for old log_event calls.
    Redirects to signed log_action.
    """
    return audit_service.log_action(
        user=user,
        action=action,
        resource_type="System",
        resource_id="0",
        request=request
    )
