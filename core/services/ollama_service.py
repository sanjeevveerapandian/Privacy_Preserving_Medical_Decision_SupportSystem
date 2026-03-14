import json
import requests

def query_ollama(prompt: str, model: str = "llama3"):
    """Send a prompt to Ollama and return plain text output."""
    url = "http://localhost:11434/api/generate"
    payload = {"model": model, "prompt": prompt}
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
    return output.strip()



