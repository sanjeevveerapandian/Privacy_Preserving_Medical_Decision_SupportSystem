#!/usr/bin/env python
# setup_emr.py

import os
import django
import sys

# Add project to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from core.models import User, MedicalDocument
from django.core.files.base import ContentFile

def setup_test_data():
    """Create test data for EMR system"""
    print("Setting up EMR test data...")
    
    # Create test patient if not exists
    patient, created = User.objects.get_or_create(
        username='test_patient',
        defaults={
            'email': 'patient@test.com',
            'role': 'patient',
            'full_name': 'Test Patient',
            'status': 'approved'
        }
    )
    
    if created:
        patient.set_password('test123')
        patient.save()
        print(f"Created test patient: {patient.username}")
    
    # Create test doctor if not exists
    doctor, created = User.objects.get_or_create(
        username='test_doctor',
        defaults={
            'email': 'doctor@test.com',
            'role': 'doctor',
            'full_name': 'Test Doctor',
            'specialization': 'General Medicine',
            'status': 'approved'
        }
    )
    
    if created:
        doctor.set_password('test123')
        doctor.save()
        print(f"Created test doctor: {doctor.username}")
    
    # Create a test document record
    doc, created = MedicalDocument.objects.get_or_create(
        original_filename="test_document.pdf",
        defaults={
            'patient': patient,
            'doctor': doctor,
            'document_type': 'prescription',
            'encrypted_filename': 'test_encrypted.enc',
            'file_size': 1024,
            'mime_type': 'application/pdf',
            'processing_status': 'pending',
            'created_by': doctor
        }
    )
    
    if created:
        print(f"Created test document: {doc.document_id}")
    
    print("Setup complete!")
    print(f"Patient login: test_patient / test123")
    print(f"Doctor login: test_doctor / test123")

if __name__ == '__main__':
    setup_test_data()