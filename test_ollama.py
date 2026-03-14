# test_ollama.py
import requests
import json

def test_ollama_connection():
    base_url = "http://localhost:11434"
    
    print("Testing Ollama connection...")
    
    # Test 1: Basic connection
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✓ Basic connection: HTTP {response.status_code}")
    except Exception as e:
        print(f"✗ Basic connection failed: {e}")
        return False
    
    # Test 2: API tags
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = [m['name'] for m in data.get('models', [])]
            print(f"✓ API connection: Found {len(models)} models")
            for model in models:
                print(f"  - {model}")
        else:
            print(f"✗ API returned {response.status_code}")
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"✗ API test failed: {e}")
    
    # Test 3: Generate test
    try:
        payload = {
            "model": "llama3",
            "prompt": "Hello",
            "stream": False
        }
        response = requests.post(f"{base_url}/api/generate", 
                               json=payload, 
                               timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Generate test: Success")
            print(f"  Response: {data.get('response', '')[:100]}...")
        else:
            print(f"✗ Generate test failed: {response.status_code}")
            print(f"  Error: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Generate test failed: {e}")
    
    return True

if __name__ == "__main__":
    test_ollama_connection()