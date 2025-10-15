import uuid
from pathlib import Path
import os

# Choose which local ASR backend to use: "whisper" or "faster_whisper"
# By default we'll use whisper (the openai whisper pip package).
ASR_BACKEND = os.getenv("ASR_BACKEND", "whisper")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def gen_id() -> str:
    return uuid.uuid4().hex

def save_upload_file(upload_file, destination: Path) -> None:
    # upload_file is fastapi.UploadFile
    with destination.open("wb") as f:
        f.write(upload_file.file.read())

# ---------- Whisper (OpenAI whisper) implementation ----------
if ASR_BACKEND == "whisper":
    try:
        import whisper
        # Load model once. Change to "small", "base", "medium", "large" as needed.
        WHISPER_MODEL = whisper.load_model(os.getenv("WHISPER_MODEL", "small"))
    except Exception as e:
        WHISPER_MODEL = None
        print("Warning: could not load whisper model:", e)

    def transcribe_audio_local(file_path: str) -> str:
        if WHISPER_MODEL is None:
            raise RuntimeError("Whisper model not loaded. Install whisper and ensure ffmpeg is available.")
        # result contains .get('text') or ['text']
        result = WHISPER_MODEL.transcribe(file_path)
        text = result.get("text", "") if isinstance(result, dict) else getattr(result, "text", "")
        return (text or "").strip()

# ---------- Faster-Whisper implementation (optional) ----------
elif ASR_BACKEND == "faster_whisper":
    try:
        from faster_whisper import WhisperModel
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
        FW_MODEL = WhisperModel(MODEL_SIZE, device=device)
    except Exception as e:
        FW_MODEL = None
        print("Warning: could not load faster-whisper model:", e)

    def transcribe_audio_local(file_path: str) -> str:
        if FW_MODEL is None:
            raise RuntimeError("faster-whisper model not loaded.")
        segments, info = FW_MODEL.transcribe(file_path)
        text = " ".join(segment.text for segment in segments)
        return text.strip()

else:
    raise RuntimeError("Unsupported ASR_BACKEND: " + ASR_BACKEND)
