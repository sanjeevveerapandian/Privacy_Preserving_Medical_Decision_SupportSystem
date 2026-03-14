import os
import django
import uuid
from datetime import date, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from core.models import User, MedicalCertificate

def verify_certificate_creation():
    print("--- Verifying Medical Certificate Feature ---")
    
    # Get a doctor and a patient
    doctor = User.objects.filter(role='doctor').first()
    patient = User.objects.filter(role='patient').first()
    
    if not doctor or not patient:
        print("Error: Need at least one doctor and one patient in the database.")
        return

    print(f"Using Doctor: {doctor.username}")
    print(f"Using Patient: {patient.username}")

    # Create a test certificate
    try:
        cert = MedicalCertificate.objects.create(
            patient=patient,
            doctor=doctor,
            diagnosis="Viral Fever and General Weakness",
            treatment_from=date.today() - timedelta(days=3),
            treatment_to=date.today(),
            rest_advised_from=date.today(),
            rest_advised_to=date.today() + timedelta(days=5),
            fit_to_resume_date=date.today() + timedelta(days=6),
            additional_advice="Maintain hydration and take prescribed medications."
        )
        print(f"Successfully created certificate with UUID: {cert.certificate_id}")
        
        # Verify fields
        assert cert.diagnosis == "Viral Fever and General Weakness"
        assert cert.doctor == doctor
        assert cert.patient == patient
        print("Verification: All fields correctly saved.")
        
        # Clean up
        cert.delete()
        print("Cleanup: Test certificate deleted.")
        print("--- Verification Successful ---")
        
    except Exception as e:
        print(f"Verification Failed: {e}")

if __name__ == "__main__":
    verify_certificate_creation()
