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

---
ScreetShots

<img width="948" height="518" alt="image" src="https://github.com/user-attachments/assets/edf4b321-9e9e-4e3d-8229-36059f0a6e05" />

<img width="949" height="517" alt="image" src="https://github.com/user-attachments/assets/8213dd01-666a-4318-942f-aad5e2a42466" />

<img width="949" height="515" alt="image" src="https://github.com/user-attachments/assets/d26381ec-6c15-43a3-ac1a-9d255b310f5c" />

<img width="949" height="517" alt="image" src="https://github.com/user-attachments/assets/227a1019-e8b5-432c-afb0-e70b56d12073" />

<img width="950" height="521" alt="image" src="https://github.com/user-attachments/assets/30d172e0-54a7-43a6-a840-f13b399eaabf" />

<img width="947" height="518" alt="image" src="https://github.com/user-attachments/assets/82b3d30a-1b66-4386-b823-6e925c7988bc" />

<img width="949" height="517" alt="image" src="https://github.com/user-attachments/assets/ab307d1f-b03b-44ca-a673-f25b77c5a9df" />

<img width="947" height="520" alt="image" src="https://github.com/user-attachments/assets/26b96acb-904c-4eae-9fa2-fcfb3425738c" />

<img width="942" height="514" alt="image" src="https://github.com/user-attachments/assets/7af4befe-05e4-4600-a85d-fb669909efcd" />

<img width="950" height="518" alt="image" src="https://github.com/user-attachments/assets/b0c643ef-da1a-462b-b34b-071777f9afa7" />

<img width="926" height="503" alt="image" src="https://github.com/user-attachments/assets/41899c1d-9331-40f6-bbad-58144e6ef88b" />

<img width="949" height="521" alt="image" src="https://github.com/user-attachments/assets/fd9b4d8e-d8c2-47d4-92b4-cdbd68121bf2" />

<img width="948" height="518" alt="image" src="https://github.com/user-attachments/assets/3b8d1537-1f2d-4567-9be6-31cc661dba9f" />

<img width="950" height="519" alt="image" src="https://github.com/user-attachments/assets/57537271-4cc4-4242-b91e-7817f03341ea" />

<img width="949" height="516" alt="image" src="https://github.com/user-attachments/assets/59825bb2-d661-4664-b3dc-cdb85046afd7" />

<img width="949" height="516" alt="image" src="https://github.com/user-attachments/assets/bca4b9a5-b75d-471e-ba29-2296dc5a10f5" />

