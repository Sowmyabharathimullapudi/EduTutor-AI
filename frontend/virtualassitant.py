import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
PROJECT_ID = os.getenv("PROJECT_ID")
REGION = os.getenv("REGION")
MODEL_ID = os.getenv("MODEL_ID")

import requests
def get_iam_token():
    url = "https://iam.cloud.ibm.com/identity/token"
    data = {
        "apikey": "Replace with Your IBM key",
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey"
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, data=data, headers=headers)
    response.raise_for_status()  # This will raise HTTPError if status != 200

    return response.json()["access_token"]
def ask_tutor(user_prompt):
    token = get_iam_token()
    url=f"https://{REGION}.ml.cloud.ibm.com/ml/v1/text/generation?version=2024-05-29"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # System instruction to restrict responses
    system_instruction = (
        "You are EduTutor AI, an educational assistant. "
        "Only answer questions related to academic subjects, study help, exams, or learning. "
        "If the user asks something unrelated to education, politely say you're restricted to education-related topics."
    )

    # Construct full prompt
    full_prompt = (
        f"{system_instruction}\n\n"
        f"User: {user_prompt}\n"
        f"AI:"
    )

    payload = {
        "model_id": MODEL_ID,
        "input": full_prompt,
        "project_id": PROJECT_ID,
        "parameters": {
            "decoding_method": "sample",
            "temperature": 0.7,
            "top_p": 0.9,
            "max_new_tokens": 3000,
            "stop_sequences": ["User:", "AI:"]
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    result = response.json()

    if "results" in result:
                output = result["results"][0]["generated_text"].strip()
                # Remove anything after 'User:' or 'AI:' if it still appears
                output = re.split(r"\bUser:|\bAI:", output)[0].strip()
                return output

    elif "errors" in result:
        return f"❌ API Error: {result['errors'][0]['message']}"
    else:
        return f"⚠️ Unknown error: {result}"
