# main.py
import os
import uuid
import json
import re
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import whisper
import google.generativeai as genai

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set in .env")

genai.configure(api_key=GOOGLE_API_KEY)

# ----------------------------
# Whisper model
# ----------------------------
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "tiny")
WHISPER_MODEL = whisper.load_model(WHISPER_MODEL_SIZE)

# ----------------------------
# Data storage
# ----------------------------
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
STORE = {}

def gen_id() -> str:
    return uuid.uuid4().hex

def save_upload_file(upload_file: UploadFile, destination: Path):
    with destination.open("wb") as f:
        f.write(upload_file.file.read())

# ----------------------------
# Pydantic models
# ----------------------------
class ActionItem(BaseModel):
    task: str
    assigned_to: Optional[str] = None
    deadline: Optional[str] = None

class MeetingResult(BaseModel):
    id: str
    filename: str
    transcript: str
    summary: str
    decisions: List[str]
    action_items: List[ActionItem]

# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI(title="Meeting Summarizer - Whisper + Gemini AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# AI functions
# ----------------------------
MODEL_GEN = genai.GenerativeModel("gemini-2.5-pro")

def transcribe_audio(file_path: str) -> str:
    result = WHISPER_MODEL.transcribe(file_path)
    return result.get("text", "").strip()

def summarize_and_extract(transcript: str) -> dict:
    # 1️⃣ Summary
    summary_prompt = f"""
You are an AI meeting assistant.
Summarize the following meeting transcript into a concise, clear summary:
{transcript}
"""
    summary_resp = MODEL_GEN.generate_content(summary_prompt)
    summary_text = summary_resp.text

    # 2️⃣ Extract Decisions & Action Items
    analysis_prompt = f"""
You are an AI meeting assistant.
Analyze the following meeting transcript and extract:

1) Key Decisions – list of decisions finalized.
2) Action Items – list of actionable tasks with responsible persons and deadlines if mentioned.

Return JSON only with this format:
{{
  "decisions": ["..."],
  "action_items": [
    {{"task": "...", "assigned_to": "...", "deadline": "..."}}
  ]
}}

Transcript:
{transcript}
"""
    analysis_resp = MODEL_GEN.generate_content(analysis_prompt)
    output_text = analysis_resp.text

    # Clean Markdown JSON if present
    clean_output = re.sub(r"^```json\s*|```$", "", output_text, flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(clean_output)
    except json.JSONDecodeError:
        parsed = {"decisions": [], "action_items": []}

    return {
        "summary": summary_text,
        "decisions": parsed.get("decisions", []),
        "action_items": parsed.get("action_items", [])
    }

# ----------------------------
# Endpoints
# ----------------------------
@app.post("/upload", response_model=MeetingResult)
async def upload_meeting(file: UploadFile = File(...)):
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Upload an audio file (audio/*)")

    mid = gen_id()
    filename = f"{mid}_{file.filename}"
    dest = DATA_DIR / filename

    try:
        save_upload_file(file, dest)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    try:
        transcript = transcribe_audio(str(dest))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {e}")

    try:
        parsed = summarize_and_extract(transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization error: {e}")

    # Convert action items to Pydantic model
    action_items = []
    for ai in parsed.get("action_items", []):
        if isinstance(ai, dict):
            action_items.append(ActionItem(
                task=ai.get("task", ""),
                assigned_to=ai.get("assigned_to"),
                deadline=ai.get("deadline")
            ))
        else:
            action_items.append(ActionItem(task=str(ai)))

    result = MeetingResult(
        id=mid,
        filename=filename,
        transcript=transcript,
        summary=parsed.get("summary", "")[:2000],
        decisions=parsed.get("decisions", []),
        action_items=action_items
    )

    STORE[mid] = result
    return result

@app.get("/transcript/{mid}", response_model=MeetingResult)
async def get_transcript(mid: str):
    if mid not in STORE:
        raise HTTPException(status_code=404, detail="Not found")
    return STORE[mid]

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
