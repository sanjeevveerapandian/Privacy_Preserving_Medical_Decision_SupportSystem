import json, os
from datetime import datetime

USER_FILE = "data/users.json"

def load_users():
    if not os.path.exists(USER_FILE):
        os.makedirs("data", exist_ok=True)
        with open(USER_FILE, "w") as f:
            json.dump({"admin": {
                "username": "admin",
                "password": "admin123",
                "role": "admin",
                "approved": True,
                "registered_at": datetime.now().isoformat()
            }}, f, indent=4)
    with open(USER_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(USER_FILE, "w") as f:
        json.dump(data, f, indent=4)