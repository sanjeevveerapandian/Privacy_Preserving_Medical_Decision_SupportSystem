# Medical AI Assistant 🔐

A secure medical data application with tamper-proof audit logging, PII masking (Blind LLM), and encrypted storage.

## 🚀 Getting Started

Follow these steps to set up and run the entire system.

### 1. Environment Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database & System Initialization
```bash
# Run migrations
python manage.py makemigrations
python manage.py migrate

# Initialize system data (Predefined symptoms, disease models)
python manage.py setup_system

# Create an admin account
python manage.py createsuperuser
```

### 3. Start Background Services
You will need multiple terminal windows or tab for these services.

#### A. Redis (Required for Celery)
```bash
redis-server
```

#### B. Ollama (Local AI)
```bash
# Start Ollama server
ollama serve

# In another terminal, pull the required model
ollama pull phi3
```

#### C. Celery Worker (Asynchronous Processing)
```bash
# Mac / Linux
celery -A medical_assistant worker --loglevel=info
```

### 4. Run the Application
```bash
python manage.py runserver
```

---

## 🔒 Security Verification
To ensure all encryption and audit logging features are working correctly, run the automated verification script:

```bash
export PYTHONPATH=$PYTHONPATH:. && ./venv/bin/python3 verify_security.py
```

**What it tests:**
*   **PII Masking**: Ensures patient names are stripped before AI processing.
*   **Encrypted Storage**: Verifies medical summaries are unreadable in the database.
*   **Metadata Privacy**: Confirms document filenames are anonymized (UUIDs).
*   **Audit Integrity**: Validates the cryptographic signatures of access logs.
*   **Secure Video**: Tests transcript encryption and secure meeting summaries.

---

## 🛠 Tech Stack
*   **Backend**: Django (Python)
*   **Database**: SQLite (Encrypted fields)
*   **AI**: Ollama (phi3, llama3)
*   **Task Queue**: Celery + Redis
*   **Video**: Jitsi Meet (WebRTC)
*   **Security**: AES-256 (Fernet), HMAC-SHA256, PII Masking
