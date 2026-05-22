"""
Edge TTS wrapper — Microsoft Neural TTS, completely free.
Generates .mp3 audio files served by FastAPI as static files.
"""
import asyncio
import hashlib
import os
import edge_tts
from core.logging import get_logger

logger = get_logger("voice.tts")

AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Good English neural voice (free via edge-tts)
DEFAULT_VOICE = "en-US-JennyNeural"


async def text_to_speech(text: str, voice: str = DEFAULT_VOICE) -> str:
    """
    Convert text to speech using Edge TTS.
    Returns the relative URL path to the generated audio file.
    Caches by content hash to avoid regenerating the same text.
    """
    text_hash = hashlib.md5(f"{voice}:{text}".encode()).hexdigest()[:12]
    filename = f"tts_{text_hash}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)

    if not os.path.exists(filepath):
        logger.info("tts_generating", chars=len(text), voice=voice, filename=filename)
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filepath)
        logger.info("tts_saved", filename=filename)
    else:
        logger.info("tts_cache_hit", filename=filename)

    return f"/static/audio/{filename}"


async def get_audio_url(text: str, base_url: str, voice: str = DEFAULT_VOICE) -> str:
    """Return the full public URL for the TTS audio."""
    relative_path = await text_to_speech(text, voice)
    return f"{base_url.rstrip('/')}{relative_path}"
