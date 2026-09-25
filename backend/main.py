from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
import json
import pypdf
import io
import sqlite3
import psycopg2
import os
import re
from pdf_generator import generate_pdf_report

# --- 1. DATABASE SETUP & CONNECTION ROUTER ---
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    if DATABASE_URL:
        # Production: PostgreSQL
        return psycopg2.connect(DATABASE_URL, sslmode="require")
    else:
        # Local Development: SQLite
        return sqlite3.connect("interview_history.db")

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        # PostgreSQL syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id SERIAL PRIMARY KEY,
                round_type VARCHAR(100),
                question TEXT,
                user_answer TEXT,
                score INT,
                feedback TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        # SQLite syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_type TEXT,
                question TEXT,
                user_answer TEXT,
                score INTEGER,
                feedback TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    conn.commit()
    cursor.close()
    conn.close()

init_db()

# --- 2. INITIALIZE FASTAPI APP ---
app = FastAPI(title="Smart Interview Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. GEMINI CLIENT SETUP ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Error initializing Gemini Client: {e}")

# --- 4. PYDANTIC MODELS ---
class InterviewRequest(BaseModel):
    job_role: str
    round_type: str 

class EvaluationRequest(BaseModel):
    question: str
    user_answer: str

class HistorySaveRequest(BaseModel):
    round_type: str
    question: str
    user_answer: str
    score: int
    feedback: str

# --- 5. HELPER TO PARSE JSON SAFELY ---
def parse_json_array(text):
    clean = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(clean)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    lines = [re.sub(r'^\d+[\.\)]\s*', '', line).strip() for line in clean.split('\n') if line.strip()]
    return lines[:3]

# --- 6. ROUTES & ENDPOINTS ---

@app.get("/")
def home():
    return {"message": "Welcome to the Smart Interview Assistant API!"}

# --- EXPORT PDF REPORT ---
@app.get("/export-pdf")
def export_pdf():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT round_type, question, user_answer, score, feedback, timestamp FROM history ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        history_list = [
            {"round_type": r[0], "question": r[1], "user_answer": r[2], "score": r[3], "feedback": r[4], "timestamp": str(r[5])} 
            for r in rows
        ]
        
        pdf_buffer = generate_pdf_report(history_list)
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=Interview_Summary_Report.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- GENERATE QUESTIONS ---
@app.post("/generate-questions")
def generate_questions(request: InterviewRequest):
    try:
        r_type = request.round_type.strip().lower()
        
        if r_type == "aptitude":
            prompt = (
                f"Generate exactly 3 Multiple Choice Questions (MCQs) for an Aptitude assessment tailored for a '{request.job_role}' role.\n"
                f"CRITICAL: Return ONLY a raw JSON array of objects. Do not include markdown or ```json backticks.\n"
                f"Format: [{{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_answer\": \"exact option\"}}]"
            )
            response = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            clean_text = response.text.strip().replace("```json", "").replace("```", "")
            return {"job_role": request.job_role, "round_type": request.round_type, "is_mcq": True, "questions": json.loads(clean_text)}
        else:
            prompt = (
                f"Generate exactly 3 highly relevant technical/HR interview questions for a '{request.job_role}' candidate for a '{request.round_type}' round.\n"
                f"CRITICAL: Return ONLY a raw JSON array of 3 string questions. Do not include markdown, code blocks, or numbers.\n"
                f"Example format: [\"Question 1 text\", \"Question 2 text\", \"Question 3 text\"]"
            )
            response = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            questions_list = parse_json_array(response.text)
            return {"job_role": request.job_role, "round_type": request.round_type, "is_mcq": False, "questions": questions_list}
            
    except Exception as e:
        print(f"CRITICAL BACKEND ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# --- GENERATE RESUME QUESTIONS ---
@app.post("/generate-questions-from-resume")
async def generate_questions_from_resume(
    round_type: str = Form(...), 
    file: UploadFile = File(...)
):
    try:
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
        
        pdf_bytes = await file.read()
        pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        
        resume_text = ""
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                resume_text += text + "\n"
        
        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from the PDF.")

        prompt = (
            f"You are an expert technical interviewer.\n"
            f"Read the following candidate resume text:\n"
            f"--- START RESUME ---\n{resume_text[:2500]}\n--- END RESUME ---\n\n"
            f"Task: Generate exactly 3 direct, deep, technical interview questions tailored specifically to the candidate's projects and skills for a '{round_type}' round.\n\n"
            f"CRITICAL INSTRUCTION:\n"
            f"- DO NOT provide feedback or review the resume.\n"
            f"- DO NOT include intro words like 'Here is a review' or headers like '## Resume Review'.\n"
            f"- Output MUST be a valid JSON array of 3 question strings ONLY.\n"
            f"Example correct format:\n"
            f"[\"How did you handle state management in your React project?\", \"Explain your approach to optimizing the SQL query in project X.\", \"What design patterns did you implement in project Y?\"]"
        )

        response = ai_client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        
        questions_list = parse_json_array(response.text)
        return {"round_type": round_type, "filename": file.filename, "questions": questions_list}

    except Exception as e:
        print(f"RESUME GENERATION ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# --- EVALUATE ANSWER ---
@app.post("/evaluate-answer")
def evaluate_answer(request: EvaluationRequest):
    try:
        prompt = (
            f"Evaluate this response:\nQuestion: {request.question}\nAnswer: {request.user_answer}\n\n"
            f"Return ONLY a JSON object with keys: 'score' (0-10 integer), 'strengths', 'weaknesses', 'model_answer'."
        )
        response = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- TRANSCRIBE SPEECH ---
@app.post("/transcribe-speech")
async def transcribe_speech(file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()
        mime_type = file.content_type if file.content_type else "audio/wav"

        prompt = "Transcribe the spoken text in this audio accurately. Output only raw transcript."
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                genai.types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                prompt
            ]
        )
        return {"filename": file.filename, "transcription": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- SAVE HISTORY ---
@app.post("/save-history")
def save_history(request: HistorySaveRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO history (round_type, question, user_answer, score, feedback)
            VALUES (%s, %s, %s, %s, %s)
        """ if DATABASE_URL else """
            INSERT INTO history (round_type, question, user_answer, score, feedback)
            VALUES (?, ?, ?, ?, ?)
        """
        
        cursor.execute(query, (request.round_type, request.question, request.user_answer, request.score, request.feedback))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- GET HISTORY ---
@app.get("/get-history")
def get_history():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, round_type, question, user_answer, score, feedback, timestamp FROM history ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        history_list = [
            {
                "id": r[0],
                "round_type": r[1],
                "question": r[2],
                "user_answer": r[3],
                "score": r[4],
                "feedback": r[5],
                "timestamp": str(r[6])
            }
            for r in rows
        ]
        return {"history": history_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))