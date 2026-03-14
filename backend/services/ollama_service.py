import json
import requests

from backend.services.anonymizer_service import anonymizer

def query_ollama(prompt: str, model: str = "llama3", secure: bool = True):
    """
    Send a prompt to Ollama.
    If secure=True, anonymizes PII before sending.
    """
    mapping = {}
    final_prompt = prompt
    
    if secure:
        final_prompt, mapping = anonymizer.anonymize(prompt)

    url = "http://localhost:11434/api/generate"
    payload = {"model": model, "prompt": final_prompt}
    response = requests.post(url, json=payload, stream=True)

    output = ""
    for line in response.iter_lines():
        if line:
            try:
                data = json.loads(line.decode("utf-8"))
                if "response" in data:
                    output += data["response"]
            except Exception:
                continue
    
    result = output.strip()
    
    # Restore PII in the response if we anonymized the input
    if secure and mapping:
        result = anonymizer.restore(result, mapping)
        
    return result



