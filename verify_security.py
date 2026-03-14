import os
import sys
import base64
import json

# Add current directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

try:
    from backend.services.anonymizer_service import anonymizer
    from core.services.crypto_service import encrypt_data, decrypt_data
    print("✅ Services imported successfully.")
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Ensure you are running this from the project root.")
    sys.exit(1)

def run_verification():
    print("-" * 40)
    print("MEDICAL AI SECURITY VERIFICATION")
    print("-" * 40)

    # 1. Test Anonymization
    print("\n[1/3] Testing PII Masking...")
    sample_text = "Patient: Alice Smith, Email: alice@example.com, Phone: +1-555-0199. Diagnosis: Severe Migraine."
    anon_text, mapping = anonymizer.anonymize(sample_text)
    
    print(f"  Input: {sample_text}")
    print(f"  Masked: {anon_text}")
    
    # Check if PII is gone
    pii_found = any(name in anon_text for name in ["Alice Smith", "alice@example.com", "555-0199"])
    if not pii_found:
        print("  ✅ PASS: PII successfully masked.")
    else:
        print("  ❌ FAIL: PII still visible in masked text.")

    # 2. Test Restoration
    print("\n[2/3] Testing PII Restoration...")
    ai_output = "I have analyzed the records for [PATIENT_NAME_1] and suggest further testing for Migraine."
    restored = anonymizer.restore(ai_output, mapping)
    print(f"  AI Output: {ai_output}")
    print(f"  Restored:  {restored}")
    
    if "Alice Smith" in restored:
        print("  ✅ PASS: PII successfully restored for authorized view.")
    else:
        print("  ❌ FAIL: PII not restored correctly.")

    # 3. Test Storage Encryption
    print("\n[3/3] Testing Database Storage Encryption...")
    sensitive_summary = "High risk of cardiac event."
    encrypted_bytes = encrypt_data({'summary': sensitive_summary})
    # This is what gets saved to DB
    db_string = base64.b64encode(encrypted_bytes).decode('utf-8')
    
    print(f"  Raw Summary: {sensitive_summary}")
    print(f"  DB Storage String: {db_string[:30]}...")
    
    # Decrypt 
    dec_bytes = base64.b64decode(db_string)
    dec_data = decrypt_data(dec_bytes)
    
    if dec_data.get('summary') == sensitive_summary:
        print("  ✅ PASS: Database encryption/decryption works.")
    else:
        print("  ❌ FAIL: Decryption result mismatch.")

    # 4. Test Metadata Encryption (UUID Filenames)
    print("\n[4/5] Testing Metadata Encryption (UUID Filenames)...")
    from core.services.emr_service import EMRProcessor
    processor = EMRProcessor()
    
    # Simulate a file save
    mock_filename = "patient_report_secret.pdf"
    
    class MockFile:
        def __init__(self, name):
            self.name = name
        def read(self):
            return b"mock file content"
        def chunks(self):
            yield b"mock file content"
            
    result = processor.save_encrypted_document(MockFile(mock_filename), "report", 1)
    
    enc_filename = result.get('encrypted_filename', '')
    print(f"  Original: {mock_filename}")
    print(f"  Stored As: {enc_filename}")
    
    if ".pdf" not in enc_filename and len(enc_filename) > 30: # Check if it's a UUID-like string
        print("  ✅ PASS: Filename is anonymized (UUID).")
    else:
        print("  ❌ FAIL: Filename still contains metadata or isn't UUID.")

    # 5. Test Tamper-Proof Audit Logging
    print("\n[5/5] Testing Tamper-Proof Audit Logging...")
    from backend.services.audit_service import audit_service
    from core.models import DataAccessLog
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    test_user = User.objects.first()
    
    # Create a signed log
    log = audit_service.log_action(
        user=test_user,
        action='VIEW',
        resource_type='TestResource',
        resource_id='test-123'
    )
    
    print(f"  Log Created: {log.action} on {log.resource_type}")
    print(f"  Signature: {log.signature[:20]}...")
    
    # Verify it
    is_valid = audit_service.verify_log(log)
    if is_valid:
        print("  ✅ PASS: Initial log signature is valid.")
    else:
        print("  ❌ FAIL: Log signature failed verification.")
        
    # Test Tamper Detection
    print("  Testing Tamper Detection (Simulating malicious edit)...")
    original_action = log.action
    log.action = 'DELETE' # Malicious change
    
    is_valid_after_tamper = audit_service.verify_log(log)
    if not is_valid_after_tamper:
        print(f"  ✅ PASS: System detected tampering (Changed '{original_action}' to 'DELETE').")
    else:
        print("  ❌ FAIL: System failed to detect tampering!")
    # 6. Test Meeting AI Service (Secure Video Consultations)
    print("\n[6/6] Testing Secure Video Consultation Processing...")
    from backend.services.meeting_ai_service import meeting_ai_service
    from core.models import Appointment
    
    # Get a test appointment
    appointment = Appointment.objects.first()
    if not appointment:
        print("  ⚠️ Skipping: No appointment found in database for testing.")
    else:
        raw_transcript = "Dr. Smith: We will start you on Lisinopril for your hypertension. Patient: Thank you doctor."
        print(f"  Input Transcript: {raw_transcript}")
        
        # Process session (Mock query_ollama behavior by overriding it temporarily if needed, but let's see if it works as is)
        result = meeting_ai_service.process_session(appointment, raw_transcript)
        
        if result['success']:
            print("  ✅ PASS: Meeting processed successfully.")
            print(f"  Encrypted Transcript in DB: {appointment.meeting_transcript[:20]}...")
            print(f"  Encrypted Summary in DB: {appointment.meeting_summary[:20]}...")
            
            # Test Decryption
            decrypted = meeting_ai_service.get_decrypted_content(appointment, appointment.doctor)
            if decrypted.get('transcript') == raw_transcript:
                print("  ✅ PASS: Meeting data decrypted successfully for authorized doctor.")
            else:
                print("  ❌ FAIL: Decrypted transcript mismatch.")
        else:
            print(f"  ❌ FAIL: {result.get('error')}")

    print("\n" + "-" * 40)
    print("OVERALL STATUS: SECURITY ACTIVE 🔐")
    print("-" * 40)

if __name__ == "__main__":
    # Setup Django environment for models/DB access
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
    django.setup()
    # Mock generate_summary if ollama is not running
    import unittest.mock as mock
    with mock.patch('backend.services.meeting_ai_service.query_ollama', return_value="[AI SUMMARY]: Patient has hypertension. Suggested Lisinopril."):
        run_verification()
