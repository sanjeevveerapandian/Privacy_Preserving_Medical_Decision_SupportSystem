import base64
import json
from backend.services.anonymizer_service import anonymizer
from backend.services.ollama_service import query_ollama
from backend.services.crypto_service import encrypt_data, decrypt_data
from backend.services.audit_service import audit_service

class MeetingAIService:
    """Service to process and secure meeting transcripts and summaries"""
    
    def process_session(self, appointment, raw_transcript):
        """
        1. Anonymizes the transcript (Blind LLM).
        2. Generates an AI summary.
        3. Encrypts both transcript and summary.
        4. Saves to the appointment model.
        """
        # 1. Anonymize for the AI
        masked_transcript, mapping = anonymizer.anonymize(raw_transcript)
        
        # 2. Query LLM for summary (Blindly)
        prompt = (
            f"You are a medical assistant summarizing a doctor-patient consultation. "
            f"Here is the anonymized transcript: \n\n{masked_transcript}\n\n"
            f"Provide a concise medical summary including: Key Symptoms, Advice Given, and Next Steps."
        )
        
        masked_summary = query_ollama(prompt)
        
        # 3. Restore PII for our encrypted storage (Authorized doctors only)
        # We restore before encrypting so that when a doctor decrypts, they see names.
        full_summary = anonymizer.restore(masked_summary, mapping)
        
        # 4. Encrypt for Database Storage
        # We store as base64 encoded strings
        encrypted_transcript = base64.b64encode(encrypt_data(raw_transcript)).decode('utf-8')
        encrypted_summary = base64.b64encode(encrypt_data(full_summary)).decode('utf-8')
        
        # 5. Save to model
        appointment.meeting_transcript = encrypted_transcript
        appointment.meeting_summary = encrypted_summary
        appointment.save(update_fields=['meeting_transcript', 'meeting_summary'])
        
        # 6. Audit (Signed)
        audit_service.log_action(
            user=appointment.doctor,
            action='GENERATE_SUMMARY',
            resource_type='Appointment',
            resource_id=appointment.appointment_id
        )
        
        return {
            'success': True,
            'summary': full_summary
        }

    def get_decrypted_content(self, appointment, user):
        """
        Decrypts meeting data for authorized users.
        """
        if user not in [appointment.patient, appointment.doctor]:
            return {'success': False, 'error': 'Unauthorized'}
            
        result = {}
        
        if appointment.meeting_transcript:
            enc_bytes = base64.b64decode(appointment.meeting_transcript)
            result['transcript'] = decrypt_data(enc_bytes)
            
        if appointment.meeting_summary:
            enc_bytes = base64.b64decode(appointment.meeting_summary)
            result['summary'] = decrypt_data(enc_bytes)
            
        # Log decryption access
        audit_service.log_action(
            user=user,
            action='VIEW_MINUTES',
            resource_type='Appointment',
            resource_id=appointment.appointment_id
        )
        
        return result

meeting_ai_service = MeetingAIService()
