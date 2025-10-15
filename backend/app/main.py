# main.py
import os
import re
import json
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ----------------------------
# Load environment
# ----------------------------
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set in .env or environment variables.")

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
ASR_BACKEND = os.getenv("ASR_BACKEND", "whisper")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Helpers
# ----------------------------
def gen_id() -> str:
    return uuid.uuid4().hex

def save_upload_file(upload_file: UploadFile, destination: Path) -> None:
    with destination.open("wb") as f:
        f.write(upload_file.file.read())

# ----------------------------
# Whisper local transcription
# ----------------------------
if ASR_BACKEND == "whisper":
    try:
        import whisper
        WHISPER_MODEL = whisper.load_model(WHISPER_MODEL_SIZE)
    except Exception as e:
        WHISPER_MODEL = None
        print("Warning: could not load whisper model:", e)

    def transcribe_audio_local(file_path: str) -> str:
        if WHISPER_MODEL is None:
            raise RuntimeError("Whisper model not loaded. Install whisper and ffmpeg.")
        result = WHISPER_MODEL.transcribe(file_path)
        text = result.get("text", "") if isinstance(result, dict) else getattr(result, "text", "")
        return (text or "").strip()
else:
    raise RuntimeError("Unsupported ASR_BACKEND: " + ASR_BACKEND)

# ----------------------------
# Pydantic models
# ----------------------------
class ActionItem(BaseModel):
    text: str
    owner: Optional[str] = None
    due: Optional[str] = None

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
app = FastAPI(title="Meeting Summarizer - Local Whisper + Google AI Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory store
STORE = {}

# ----------------------------
# Google Generative AI setup
# ----------------------------
import google.generativeai as genai
genai.configure(api_key=GOOGLE_API_KEY)

def summarize_transcript_with_google(transcript: str) -> dict:
    prompt = f"""
You are an assistant that reads medical consultation transcripts.
Analyze the transcript carefully and extract:

1) A concise summary (2-4 sentences) of the consultation.
2) All decisions made by the doctor or medical staff, even implied ones.
3) Action items for patient, parent, or medical staff, clearly stating:
   - task description
   - who should do it (owner)
   - deadline or timing if mentioned

Return **ONLY valid JSON** in this exact format:
{{
  "summary": "string",
  "decisions": ["list of decisions, if any, otherwise empty"],
  "action_items": [
      {{
          "text": "task description",
          "owner": "who should do it (optional)",
          "due": "deadline or timing (optional)"
      }}
  ]
}}

Transcript:
{transcript}
"""
    try:
        response = genai.models.TextGeneration.create(
            model="chat-bison-001",
            prompt=prompt,
            temperature=0
        )
        # New API returns result_text
        content = getattr(response, "text", "") or ""
        # Attempt strict JSON parsing
        m = re.search(r"(\{.*\})", content, flags=re.S)
        json_text = m.group(1) if m else content
        parsed = json.loads(json_text)
        parsed.setdefault("summary", "")
        parsed.setdefault("decisions", [])
        parsed.setdefault("action_items", [])
        return parsed
    except Exception as e:
        print("Google AI summarization failed:", e)
        return {"summary": transcript[:400] + "...", "decisions": [], "action_items": []}

# ----------------------------
# Upload endpoint
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
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    try:
        transcript = transcribe_audio_local(str(dest))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {e}")

    parsed = summarize_transcript_with_google(transcript)

    decisions = parsed.get("decisions") or []
    action_items_raw = parsed.get("action_items") or []
    action_items = []
    for ai in action_items_raw:
        if isinstance(ai, dict):
            action_items.append(ActionItem(
                text=ai.get("text",""),
                owner=ai.get("owner"),
                due=ai.get("due")
            ))
        else:
            action_items.append(ActionItem(text=str(ai)))

    result = MeetingResult(
        id=mid,
        filename=filename,
        transcript=transcript,
        summary=parsed.get("summary", "")[:2000],
        decisions=decisions,
        action_items=action_items
    )

    STORE[mid] = result
    return result

# ----------------------------
# Get transcript endpoint
# ----------------------------
@app.get("/transcript/{mid}", response_model=MeetingResult)
async def get_result(mid: str):
    if mid not in STORE:
        raise HTTPException(status_code=404, detail="Not found")
    return STORE[mid]

