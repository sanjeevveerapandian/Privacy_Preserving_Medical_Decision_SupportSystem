import sys
import os
import django
import base64

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from backend.services.crypto_service import decrypt_data

# I'm prepending 'Z' which the user missed when copying!
token = "Z" + "0FBQUFBQnBxdkU0LUtDS1UxY3g4SjltaDRTVFpxUURfOW9OVXlGRGRYUTE3eDV0U0lhR3FBaTU1cW43S3dmQkwzVlN3M2N2U0llV1hLZjNLZ2Z5blZhX0xtQkRsdDFHcHdFZDBXeXVnZzBUb2t5NkEtb0pib3R2V2xsMnpfTTk0dDV6WjI0d2YzMDZZVms3VkpsYzFGSEZ4blAzN0tuVmFEbzR1T054N0prLUZ6b0YtV1I0X0ZVMVdXak5WcFZMQ3EtbEtDbFkyT3B1c0d6X3FJRklCdFFpNlhKQTF6WVZOQT09"

try:
    enc_bytes = base64.b64decode(token + "==")
    print("Fernet decrypted:", decrypt_data(enc_bytes))
except Exception as e:
    print("Error:", e)
