from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import requests
import re
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
from fastapi.middleware.cors import CORSMiddleware
import uuid
# Firebase init (use your JSON credentials)
#create a service account in firebase 
cred = credentials.Certificate("?Your serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'replace with your database URL'
})


class ChatEntry(BaseModel):
    uid: str
    question: str
    answer: str
# FastAPI app
app = FastAPI()

# Request model
class QuizRequest(BaseModel):
    uid: str
    topic: str
    difficulty: str = "medium"


# Response model
class QuizQuestion(BaseModel):
    question: str
    options: Dict[str, str]
    answer: str

# Allow frontend access (adjust origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Question(BaseModel):
    question: str
    options: Dict[str, str]
    answer: str
    user_answer: str

class QuizHistoryRequest(BaseModel):
    uid: str
    score: int
    total: int
    topic: str
    difficulty: str
    timestamp: str
    quiz: List[Question]  # List of 10 questions with user answers
class NotesRequest(BaseModel):
    notes: str
class FlashcardRequest(BaseModel):
    notes: str

# IBM Granite API configuration
API_KEY = "Replace With your IBM API KEY"
MODEL_ID = "ibm/granite-3-2b-instruct"
PROJECT_ID = "Project ID IN IBM CLoud"
VERSION = "2024-05-01"
#replace this end point URl according to your model
ENDPOINT = f"https://us-south.ml.cloud.ibm.com/ml/v1/text/generation?version={VERSION}"

# Get IAM token
def get_iam_token(api_key):
    response = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        data={"apikey": api_key, "grant_type": "urn:ibm:params:oauth:grant-type:apikey"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"IAM Token error: {response.text}")

# Call IBM model and generate quiz text
def generate_quiz_text(topic, difficulty):
    token = get_iam_token(API_KEY)
    prompt = f"""
    Generate exactly 10 multiple-choice questions on the topic: "{topic}" with {difficulty} difficulty.
    Each question must have:

    - Four options (A, B, C, D) on separate lines.
    - A clearly labeled correct answer in this format: Answer: <A/B/C/D>

    Do NOT include any code formatting, Markdown, backticks, or special characters. Strictly use plain text like this:

    Q1. <Question>
    A. Option A
    B. Option B
    C. Option C
    D. Option D
    Answer: <Correct Option Letter>

    Repeat for 10 questions only.
    """



    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    data = {
        "model_id": MODEL_ID,
        "input": prompt.strip(),
        "parameters": {
            "max_new_tokens": 2000,
            "temperature": 0.7
        },
        "project_id": PROJECT_ID
    }

    response = requests.post(ENDPOINT, headers=headers, json=data)
    result = response.json()

    if "results" in result:
        return result["results"][0]["generated_text"]
    else:
        raise ValueError(f"Unexpected response: {result}")

# Parse model output into structured questions
def parse_quiz_output(quiz_text: str) -> List[QuizQuestion]:
    questions = []
    # Split using Q1., Q2., ..., but also support without exact dots
    blocks = re.split(r"Q\d+\.\s*", quiz_text.strip())
    for block in blocks:
        if not block.strip():
            continue

        lines = block.strip().split("\n")
        if len(lines) < 6:
            continue  # Incomplete block

        question_line = lines[0].strip()
        try:
            options = {}
            for i, opt in enumerate(["A", "B", "C", "D"]):
                if not lines[i + 1].strip().startswith(f"{opt}."):
                    raise ValueError("Missing or malformed option")
                options[opt] = lines[i + 1].strip()[2:].strip()

            # Find Answer:
            answer_line = next((line for line in lines if "Answer:" in line), "")
            answer_match = re.search(r"Answer:\s*([A-D])", answer_line)
            if not answer_match:
                raise ValueError("No valid answer found")
            answer = answer_match.group(1)

            questions.append(QuizQuestion(
                question=question_line,
                options=options,
                answer=answer
            ))

        except Exception:
            continue  # Skip malformed question

    return questions

# API endpoint for quiz generation
@app.post("/generate-quiz", response_model=List[QuizQuestion])
def generate_quiz(request: QuizRequest):
    try:
        attempts = 0
        max_attempts = 3
        structured_quiz = []

        while attempts < max_attempts:
            raw_quiz = generate_quiz_text(request.topic, request.difficulty)
            structured_quiz = parse_quiz_output(raw_quiz)

            if len(structured_quiz) == 10:
                break  # Success
            attempts += 1

        if len(structured_quiz) != 10:
            raise HTTPException(status_code=500, detail=f"Failed to generate 10 questions after {max_attempts} attempts.")

        return structured_quiz

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/save-chat-history")
def save_chat(entry: ChatEntry):
    try:
        timestamp = datetime.utcnow().isoformat()
        db.reference(f'chat_history/{entry.uid}').push({
            'question': entry.question,
            'answer': entry.answer,
            'timestamp': timestamp
        })
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/get-chat-history/{uid}")
def get_history(uid: str):
    try:
        ref = db.reference(f'chat_history/{uid}')
        return ref.get() or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/student-history")
def get_student_history(uid: str):
    ref = db.reference(f"quiz_history/{uid}")
    records = ref.get()
    if not records:
        return []
    return list(records.values())



# ==============================
# Save Quiz History Endpoint
# ==============================
@app.post("/save-quiz-history")
def save_quiz_history(request: QuizHistoryRequest):
    try:
        ref = db.reference(f"quiz_history/{request.uid}")
        history_id = str(uuid.uuid4())

        ref.child(history_id).set({
            "score": request.score,
            "total": request.total,
            "topic": request.topic,
            "difficulty": request.difficulty,
            "timestamp": request.timestamp,
            "quiz": [q.dict() for q in request.quiz]
        })

        return {"message": "✅ Quiz history saved successfully."}
    except Exception as e:
        return {"error": str(e)}

# ==============================
# Get Quiz History by UID
# ==============================
@app.get("/get-quiz-history/{uid}")
def get_quiz_history(uid: str):
    try:
        ref = db.reference(f"quiz_history/{uid}")
        data = ref.get()
        if data:
            return data
        return {"message": "No quiz history found."}
    except Exception as e:
        return {"error": str(e)}

def clean_summary(text: str) -> str:
    # Remove bullets like ✅, dashes, etc.
    text = re.sub(r'✅|\s*-\s*', '', text)

    # Extract lines that look like numbered points
    lines = re.findall(r'(?:^\d{1,2}\.\s.*?$)', text, flags=re.MULTILINE)

    # Re-number them properly
    cleaned = ""
    for idx, line in enumerate(lines, start=1):
        content = re.sub(r'^\d{1,2}\.\s*', '', line)
        cleaned += f"{idx}. {content.strip()}\n"

    return cleaned.strip()

@app.post("/summarize-notes")
def summarize_notes(req: NotesRequest):
    token = get_iam_token(API_KEY)

    # Improved prompt to guide clean output
    prompt = (
        "Summarize the following text into exactly 5 to 7 clear and concise points. "
        "Each point should be numbered like 1., 2., 3. Do not include emojis or bullets.\n\n"
        f"{req.notes}"
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    data = {
        "model_id": MODEL_ID,
        "input": prompt.strip(),
        "parameters": {
            "max_new_tokens": 300,
            "temperature": 0.5
        },
        "project_id": PROJECT_ID
    }

    response = requests.post(ENDPOINT, headers=headers, json=data)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    try:
        summary_raw = response.json()["results"][0]["generated_text"]
        summary_cleaned = clean_summary(summary_raw)
        return {"summary": summary_cleaned}
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected response format from IBM Granite.")

@app.post("/generate-flashcards")
def generate_flashcards(req: FlashcardRequest):
    token = get_iam_token(API_KEY)

    prompt = (
        "From the following study notes, generate 5 question-answer flashcards. "
        "Each flashcard should be numbered and follow this format:\n\n"
        "Q: <Question>\nA: <Answer>\n\n"
        f"{req.notes}"
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    data = {
        "model_id": MODEL_ID,
        "input": prompt.strip(),
        "parameters": {
            "max_new_tokens": 400,
            "temperature": 0.5
        },
        "project_id": PROJECT_ID
    }

    response = requests.post(ENDPOINT, headers=headers, json=data)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    try:
        result = response.json()["results"][0]["generated_text"]
        return {"flashcards": result.strip()}
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected flashcard format.")
