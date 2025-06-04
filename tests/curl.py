import requests

url = "http://localhost:11434/api/chat"
payload = {
    "model": "mistral",
    "messages": [
        {
            "role": "user",
            "content": "Why is the sky blue?"
        }
    ],
    "stream": False
}

response = requests.post(url, json=payload)
print(response.text)
