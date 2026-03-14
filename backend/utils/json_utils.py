# backend/utils/json_utils.py

import json
import base64
from datetime import datetime

class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles bytes and other non-serializable types"""
    
    def default(self, obj):
        if isinstance(obj, bytes):
            # Convert bytes to base64 string
            return base64.b64encode(obj).decode('utf-8')
        elif isinstance(obj, datetime):
            # Convert datetime to ISO format string
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            # Convert objects with __dict__ to dict
            return obj.__dict__
        elif hasattr(obj, 'to_json'):
            # Use object's to_json method if available
            return obj.to_json()
        else:
            # Let the base class default method raise the TypeError
            return super().default(obj)


def safe_json_dumps(data, ensure_ascii=False):
    """Safely convert data to JSON string"""
    try:
        return json.dumps(data, cls=JSONEncoder, ensure_ascii=ensure_ascii)
    except Exception as e:
        # Fallback: convert everything to strings
        return json.dumps(_force_strings(data), ensure_ascii=ensure_ascii)


def _force_strings(obj):
    """Recursively convert all values to strings"""
    if isinstance(obj, dict):
        return {str(k): _force_strings(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [_force_strings(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        try:
            return str(obj)
        except:
            return ""


def make_serializable(data):
    """Ensure data is JSON serializable"""
    try:
        # Try to serialize it first
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        # If it fails, use our force strings method
        return _force_strings(data)