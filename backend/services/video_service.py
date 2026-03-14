import random
import string
import hashlib
from django.conf import settings
from backend.services.audit_service import audit_service

class VideoService:
    """Service to manage secure Jitsi Meet video consultation links"""
    
    def __init__(self):
        # We use a public Jitsi instance or a private one if configured
        self.jitsi_base_url = getattr(settings, 'JITSI_BASE_URL', 'https://meet.jit.si')
        
    def create_secure_meeting(self, appointment):
        """
        Generates a secure, random meeting link for an appointment.
        Updates the appointment object with the link.
        """
        # Generate a unique, unpredictable room name
        # We combine appointment ID with a random salt for security
        random_salt = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        room_payload = f"{appointment.appointment_id}-{random_salt}"
        room_name = hashlib.sha256(room_payload.encode()).hexdigest()[:24]
        
        # Construct the URL
        meeting_url = f"{self.jitsi_base_url}/{room_name}"
        
        # Update the appointment
        appointment.is_video_consultation = True
        appointment.meeting_link = meeting_url
        appointment.save(update_fields=['is_video_consultation', 'meeting_link'])
        
        # Log the security event (Signed)
        audit_service.log_action(
            user=appointment.doctor,
            action='CREATE_MEETING',
            resource_type='Appointment',
            resource_id=appointment.appointment_id
        )
        
        return meeting_url

    def get_join_info(self, appointment, user):
        """
        Verifies permission and returns joining details.
        Logs the access.
        """
        if user not in [appointment.patient, appointment.doctor]:
            return {'success': False, 'error': 'Unauthorized'}
            
        # Log meeting access
        audit_service.log_action(
            user=user,
            action='JOIN_MEETING',
            resource_type='Appointment',
            resource_id=appointment.appointment_id
        )
        
        return {
            'success': True,
            'meeting_url': appointment.meeting_link,
            'room_name': appointment.meeting_link.split('/')[-1]
        }

video_service = VideoService()
