# core/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
import uuid
# models.py (MedicalRecord model update)
from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('researcher', 'Researcher'),
        ('patient', 'Patient'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    RISK_LEVEL_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    # Core fields
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    email = models.EmailField(unique=True)
    
    # Profile fields
    full_name = models.CharField(max_length=255, blank=True)
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', 
                                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    
    # Role-specific fields
    specialization = models.CharField(max_length=100, blank=True)  # Doctor
    license_number = models.CharField(max_length=50, blank=True)  # Doctor
    institution = models.CharField(max_length=200, blank=True)  # Researcher
    research_area = models.TextField(blank=True)  # Researcher
    
    # New Doctor-specific fields for certificates
    qualifications = models.CharField(max_length=255, blank=True)  # e.g., M.B.B.S, M.D.
    clinic_name = models.CharField(max_length=255, blank=True)
    clinic_address = models.TextField(blank=True)
    signature = models.ImageField(upload_to='signatures/', null=True, blank=True)
    biography = models.TextField(blank=True)

    
    # Medical data
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, blank=True)
    ml_confidence_score = models.FloatField(default=0.0)
    last_analysis = models.DateTimeField(null=True, blank=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Metadata
    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    
    class Meta:
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def get_full_name(self):
        if self.full_name:
            return self.full_name
        return super().get_full_name()
    
    def is_admin(self):
        return self.role == 'admin' or self.is_superuser or self.is_staff
    
    def is_doctor(self):
        return self.role == 'doctor'
    
    def is_researcher(self):
        return self.role == 'researcher'
    
    def is_patient(self):
        return self.role == 'patient'
    
    def is_approved(self):
        return self.status == 'approved'
    
    def get_role_dashboard(self):
        return f"{self.role}_dashboard"



class MedicalRecord(models.Model):
    """Encrypted medical records with fuzzy logic data"""
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='medical_records')
    record_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Encrypted fields
    encrypted_data = models.TextField()
    encrypted_symptoms = models.TextField()
    encrypted_diagnosis = models.TextField(blank=True)
    encrypted_treatment = models.TextField(blank=True)
    
    # ML Analysis fields
    risk_level = models.CharField(max_length=20, choices=User.RISK_LEVEL_CHOICES, blank=True)
    confidence_score = models.FloatField(default=0.0)
    risk_score = models.FloatField(default=0.0, help_text="Composite risk score from fuzzy logic")
    
    # Fuzzy logic data
    fuzzy_membership = models.JSONField(default=dict, blank=True, 
        help_text="Fuzzy membership values for risk categories")
    analysis_components = models.JSONField(default=dict, blank=True,
        help_text="Component scores used in fuzzy logic calculation")
    
    # Additional metadata
    symptoms_count = models.IntegerField(default=0)
    severe_symptoms_count = models.IntegerField(default=0)
    patient_age = models.IntegerField(null=True, blank=True)
    past_history_file = models.FileField(upload_to='medical_history/', null=True, blank=True)
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                   related_name='created_records')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Medical Record'
        verbose_name_plural = 'Medical Records'
        indexes = [
            models.Index(fields=['patient', 'created_at']),
            models.Index(fields=['risk_level', 'confidence_score']),
            models.Index(fields=['created_by', 'created_at']),
        ]
    
    def __str__(self):
        return f"Record {self.record_id} - {self.patient.username}"
    
    def get_diagnosis_summary(self):
        """Decrypt and return diagnosis summary as a string"""
        from .utils import decrypt_data
        import json
        import ast
        if not self.encrypted_diagnosis:
            return "No diagnosis provided"
        
        try:
            data = decrypt_data(self.encrypted_diagnosis)
            # If it's a JSON string, parse it
            if isinstance(data, str) and (data.startswith('{') or data.startswith('[')):
                try:
                    data = json.loads(data)
                except Exception:
                    try:
                        # Fallback for Python-repr style strings
                        data = ast.literal_eval(data)
                    except Exception:
                        pass
            
            if isinstance(data, dict):
                # Handle both types of prediction structures seen in the system
                return data.get('prediction', data.get('primary_prediction', "No diagnosis provided"))
            return str(data)
        except Exception:
            return "Error decoding diagnosis"

    def get_symptoms_list(self):
        """Decrypt and return symptoms as a list of strings (names)"""
        from .utils import decrypt_data
        import json
        import ast
        if not self.encrypted_symptoms:
            return []
        try:
            items = decrypt_data(self.encrypted_symptoms)
            # If it's a JSON string, parse it
            if isinstance(items, str) and (items.startswith('{') or items.startswith('[')):
                try:
                    items = json.loads(items)
                except Exception:
                    try:
                        # Fallback for Python-repr style strings (e.g. from str(list_of_dicts))
                        items = ast.literal_eval(items)
                    except Exception:
                        pass
            
            if isinstance(items, list):
                # Extract names if they are dictionaries
                result = []
                for item in items:
                    if isinstance(item, dict):
                        result.append(item.get('name', item.get('code', str(item))))
                    else:
                        result.append(str(item))
                return result
            elif isinstance(items, dict):
                # Sometimes a single symptom might be saved
                return [items.get('name', items.get('code', str(items)))]
            elif isinstance(items, str):
                # Handle string representation of a list if it didn't match startswith
                if items.startswith("['") or items.startswith('["'):
                    try:
                        items = ast.literal_eval(items)
                        if isinstance(items, list):
                            return [str(i) for i in items]
                    except:
                        pass
                # If it's still a string, maybe it's a comma-separated list
                if ',' in items:
                    return [i.strip() for i in items.split(',')]
                return [items]
            return []
        except Exception:
            return []
    
    def get_risk_level_display(self):
        """Get human-readable risk level"""
        risk_display = {
            'low': 'Low Risk',
            'medium': 'Medium Risk',
            'high': 'High Risk',
            'critical': 'Critical Risk'
        }
        return risk_display.get(self.risk_level, self.risk_level)
    
    def get_confidence_display(self):
        """Get confidence as percentage"""
        return f"{self.confidence_score * 100:.1f}%"
    
    def get_fuzzy_membership_display(self):
        """Format fuzzy membership for display"""
        if not self.fuzzy_membership:
            return "Not available"
        
        low = self.fuzzy_membership.get('low', 0) * 100
        medium = self.fuzzy_membership.get('medium', 0) * 100
        high = self.fuzzy_membership.get('high', 0) * 100
        
        return f"Low: {low:.1f}%, Medium: {medium:.1f}%, High: {high:.1f}%"

class ChatSession(models.Model):
    """Chat sessions for different roles"""
    ROLE_CHOICES = (
        ('doctor', 'Doctor'),
        ('researcher', 'Researcher'),
        ('patient', 'Patient'),
    )
    
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    title = models.CharField(max_length=200, default="Chat Session")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"

class ChatMessage(models.Model):
    """Individual chat messages"""
    MESSAGE_TYPE_CHOICES = (
        ('user', 'User'),
        ('ai', 'AI Assistant'),
        ('system', 'System'),
    )
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.message_type}: {self.content[:50]}..."

class MLModel(models.Model):
    """Stored ML models"""
    name = models.CharField(max_length=100)
    version = models.CharField(max_length=20)
    model_file = models.FileField(upload_to='ml_models/')
    features = models.JSONField(default=list)
    accuracy = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} v{self.version}"

class Notification(models.Model):
    """User notifications"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=[
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ])
    is_read = models.BooleanField(default=False)
    action_url = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    @classmethod
    def create_notification(cls, user, title, message, notification_type='info', action_url=''):
        return cls.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url
        )

class AuditLog(models.Model):
    """System audit logging"""
    ACTION_CHOICES = [
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('REGISTER', 'User Registration'),
        ('UPDATE', 'Data Update'),
        ('DELETE', 'Data Delete'),
        ('PREDICTION', 'ML Prediction'),
        ('CHAT', 'Chat Interaction'),
        ('SEARCH', 'Encrypted Search'),
        ('APPROVAL', 'User Approval'),
        ('ACCESS', 'System Access'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.action} - {self.user.username if self.user else 'System'}"

class ResearchData(models.Model):
    """Anonymized research data"""
    data_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    encrypted_features = models.TextField()
    prediction = models.CharField(max_length=100)
    confidence = models.FloatField()
    risk_level = models.CharField(max_length=20)
    age_group = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    region = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Research Data {self.data_id}"
    



# Add to core/models.py
class Appointment(models.Model):
    APPOINTMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    
    APPOINTMENT_TYPE_CHOICES = [
        ('consultation', 'Consultation'),
        ('follow_up', 'Follow-up'),
        ('emergency', 'Emergency'),
        ('routine_checkup', 'Routine Checkup'),
        ('symptom_review', 'Symptom Review'),
    ]
    
    appointment_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_appointments')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doctor_appointments')
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    appointment_type = models.CharField(max_length=50, choices=APPOINTMENT_TYPE_CHOICES, default='consultation')
    status = models.CharField(max_length=20, choices=APPOINTMENT_STATUS_CHOICES, default='pending')
    reason = models.TextField()
    symptoms = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_urgent = models.BooleanField(default=False)
    duration_minutes = models.IntegerField(default=30)
    
    # Video Consultation Fields
    is_video_consultation = models.BooleanField(default=False)
    meeting_link = models.URLField(max_length=500, null=True, blank=True)
    # Encrypted fields (Base64 encoded encrypted strings)
    meeting_transcript = models.TextField(null=True, blank=True)
    meeting_summary = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['-appointment_date', 'appointment_time']
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['appointment_date', 'appointment_time']),
        ]
    
    def __str__(self):
        return f"Appointment {self.appointment_id} - {self.patient.username} with Dr. {self.doctor.username}"
    
    def is_upcoming(self):
        now = timezone.now()
        appointment_datetime = datetime.combine(self.appointment_date, self.appointment_time)
        return appointment_datetime > now and self.status in ['confirmed', 'pending']
    
    def get_duration(self):
        return self.duration_minutes
    
    def get_formatted_datetime(self):
        return f"{self.appointment_date.strftime('%Y-%m-%d')} {self.appointment_time.strftime('%H:%M')}"
    
    def can_be_cancelled(self):
        appointment_datetime = datetime.combine(self.appointment_date, self.appointment_time)
        time_until_appointment = appointment_datetime - timezone.now()
        return time_until_appointment.total_seconds() > 3600  # 1 hour before
    






































# core/models.py (add these models to your existing models)

class MedicalDocument(models.Model):
    """Model for storing medical documents"""
    DOCUMENT_TYPE_CHOICES = [
        ('lab_report', 'Lab Report'),
        ('xray', 'X-Ray'),
        ('mri', 'MRI - Brain Tumor'),
        ('ct_scan', 'CT Scan'),
        ('discharge_summary', 'Discharge Summary'),
        ('medical_certificate', 'Medical Certificate'),
        ('insurance_form', 'Insurance Form'),
        ('other', 'Other'),
    ]
    
    document_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='medical_documents')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_documents', null=True, blank=True)
    
    # Document details
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPE_CHOICES)
    original_filename = models.CharField(max_length=255)
    encrypted_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    mime_type = models.CharField(max_length=100)
    
    # Extracted data (encrypted)
    extracted_text = models.TextField(blank=True)  # OCR extracted text
    extracted_data = models.JSONField(default=dict, blank=True)  # Structured extracted data
    diagnosis = models.TextField(blank=True)
    medications = models.JSONField(default=list, blank=True)
    lab_results = models.JSONField(default=list, blank=True)
    
    # Metadata
    upload_date = models.DateTimeField(auto_now_add=True)
    document_date = models.DateField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    processing_status = models.CharField(max_length=50, default='pending', choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ])
    
    # AI Inference Results
    ai_prediction = models.CharField(max_length=50, null=True, blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)
    ai_summary = models.TextField(null=True, blank=True)  # AI-generated descriptive summary
    ai_heatmap = models.ImageField(upload_to='heatmaps/', null=True, blank=True)
    ai_status = models.CharField(max_length=20, default='Pending', choices=[
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    ])
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')
    
    class Meta:
        ordering = ['-upload_date']
        verbose_name = "Medical Document"
        verbose_name_plural = "Medical Documents"
    
    def get_ai_summary(self):
        """Decrypt and return AI summary"""
        if not self.ai_summary:
            return ""
        
        try:
            from core.services.crypto_service import decrypt_data
            import base64
            
            # If it's not base64, it might be old plaintext
            try:
                encrypted_bytes = base64.b64decode(self.ai_summary)
                data = decrypt_data(encrypted_bytes)
                if isinstance(data, dict):
                    return data.get('summary', data.get('analysis', ''))
                return str(data)
            except:
                return self.ai_summary
        except Exception as e:
            print(f"Error decrypting AI summary: {e}")
            return self.ai_summary

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.patient.username} - {self.upload_date.date()}"

class EMRExtractionLog(models.Model):
    """Log for EMR extraction processes"""
    log_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    document = models.ForeignKey(MedicalDocument, on_delete=models.CASCADE, related_name='extraction_logs')
    
    # Process details
    extraction_method = models.CharField(max_length=50)
    processing_time = models.FloatField()  # in seconds
    success = models.BooleanField(default=False)
    
    # Extracted information
    text_length = models.IntegerField(default=0)
    entities_found = models.JSONField(default=list, blank=True)
    confidence_score = models.FloatField(default=0.0)
    
    # Errors
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Extraction Log - {self.document.document_type} - {self.created_at}"


# core/models.py - Update EMRPrediction model:

class EMRPrediction(models.Model):
    prediction_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(MedicalDocument, on_delete=models.CASCADE, related_name='predictions')
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='predictions')
    
    predicted_conditions = models.JSONField(default=list)  # List of predicted conditions
    confidence_scores = models.JSONField(default=dict)     # {condition: confidence_score}
    risk_level = models.CharField(max_length=20, choices=[
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical')
    ], default='Low')
    
    symptoms_detected = models.JSONField(default=list)     # Symptoms used for prediction
    llm_analysis = models.TextField(blank=True)           # AI explanation
    model_status = models.CharField(max_length=20, default='primary', choices=[
        ('primary', 'Primary Model'),
        ('fallback', 'Fallback Model'),
        ('error', 'Model Error')
    ])
    
    created_at = models.DateTimeField(auto_now_add=True)
    def get_llm_analysis(self):
        """Decrypt and return LLM analysis"""
        if not self.llm_analysis:
            return ""
        
        try:
            from core.services.crypto_service import decrypt_data
            import base64
            import json
            
            # Decode base64 and decrypt
            encrypted_bytes = base64.b64decode(self.llm_analysis)
            data = decrypt_data(encrypted_bytes)
            
            if isinstance(data, dict):
                return data.get('analysis', '')
            return str(data)
        except Exception as e:
            print(f"Error decrypting LLM analysis: {e}")
            return "Error: Could not decrypt analysis data."

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'EMR Prediction'
        verbose_name_plural = 'EMR Predictions'
    
    def __str__(self):
        return f"Prediction for {self.patient} - {self.get_risk_level_display()}"
    
    def get_confidence_percentage(self):
        """Get confidence as percentage"""
        if self.confidence_scores:
            try:
                # Get first confidence score
                for key, value in self.confidence_scores.items():
                    if isinstance(value, (int, float)):
                        return f"{float(value):.1f}%"
            except:
                pass
        return "N/A"
    
    def get_confidence_value(self):
        """Get confidence as float"""
        if self.confidence_scores:
            try:
                for key, value in self.confidence_scores.items():
                    if isinstance(value, (int, float)):
                        return float(value)
            except:
                pass
        return 0.0
class MedicalCertificate(models.Model):
    """Digital Medical Certificate issued by a doctor to a patient"""
    certificate_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_certificates')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='issued_certificates')
    
    # Clinical Details
    diagnosis = models.TextField()
    treatment_from = models.DateField()
    treatment_to = models.DateField(null=True, blank=True)
    
    # Advice
    rest_advised_from = models.DateField(null=True, blank=True)
    rest_advised_to = models.DateField(null=True, blank=True)
    fit_to_resume_date = models.DateField(null=True, blank=True)
    additional_advice = models.TextField(blank=True)
    
    # Metadata
    issued_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-issued_date', '-created_at']
        verbose_name = "Medical Certificate"
        verbose_name_plural = "Medical Certificates"

    def __str__(self):
        return f"Certificate {self.certificate_id} - {self.patient.full_name or self.patient.username}"

class DataAccessLog(models.Model):
    """Tamper-proof log for healthcare data access"""
    log_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='access_logs')
    
    ACTION_CHOICES = [
        ('VIEW', 'View Document'),
        ('DOWNLOAD', 'Download Document'),
        ('PREDICT', 'Generate AI Prediction'),
        ('EXTRACT', 'OCR Text Extraction'),
        ('EXPORT', 'Export Medical Data'),
    ]
    
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=50) # 'MedicalDocument', 'EMRPrediction', etc.
    resource_id = models.CharField(max_length=255) # ID of the accessed resource
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Security: Signature for tamper-detection
    signature = models.CharField(max_length=255, blank=True) # HMAC-SHA256
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Data Access Log"
        verbose_name_plural = "Data Access Logs"

    def __str__(self):
        return f"{self.user} - {self.action} - {self.resource_type} ({self.created_at.date()})"
