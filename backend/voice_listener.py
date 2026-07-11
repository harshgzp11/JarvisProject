import io
import logging
import os
import queue
import re
import threading
import time
import wave

import numpy as np
import requests
import sounddevice as sd

API_URL = "http://127.0.0.1:8000/api/assistant/chat"
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_DURATION = 0.5
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_DURATION)
WAKE_KEYWORDS = ["hey jarvis", "jarvis"]
VAD_ENERGY_THRESHOLD = 0.02
MAX_VOICE_SECONDS = 8.0
TRANSCRIPTION_API_URL = os.environ.get("VOICE_TRANSCRIPTION_API_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("voice_listener")


def current_timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def log_status(message: str) -> None:
    logger.info(f"{current_timestamp()} | {message}")


def rms_level(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(chunk), axis=0)).mean())


def format_wav_bytes(samples: np.ndarray) -> bytes:
    samples = np.asarray(samples, dtype=np.float32)
    samples = np.clip(samples, -1.0, 1.0)
    int_samples = (samples * 32767.0).astype(np.int16)
    with io.BytesIO() as buffer:
        with wave.open(buffer, mode="wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(int_samples.tobytes())
        return buffer.getvalue()


def extract_command_from_transcript(transcript: str) -> str | None:
    normalized = transcript.lower().strip()
    for keyword in WAKE_KEYWORDS:
        if keyword in normalized:
            remainder = normalized.split(keyword, 1)[1].strip()
            remainder = re.sub(r"^[,.:;\-\s]+", "", remainder)
            return remainder or None
    return None


def transcribe_audio_chunk(wav_bytes: bytes) -> str | None:
    if TRANSCRIPTION_API_URL:
        try:
            response = requests.post(
                TRANSCRIPTION_API_URL,
                files={"file": ("command.wav", wav_bytes, "audio/wav")},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload.get("transcript") or payload.get("text")
        except Exception as exc:
            log_status(f"Transcription API error: {exc}")
            return None
    elif OPENAI_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            files = {
                "file": ("command.wav", wav_bytes, "audio/wav"),
                "model": (None, "gpt-4o-transcribe"),
            }
            response = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                files=files,
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("text")
        except Exception as exc:
            log_status(f"OpenAI transcription error: {exc}")
            return None
    else:
        log_status("No transcription backend configured. Set VOICE_TRANSCRIPTION_API_URL or OPENAI_API_KEY.")
        return None


def dispatch_command_async(command_text: str) -> None:
    def worker(command: str) -> None:
        payload = {"message": command}
        try:
            response = requests.post(API_URL, json=payload, timeout=10)
            response.raise_for_status()
            log_status(f"Dispatched command: '{command}' -> status {response.status_code}")
        except Exception as exc:
            log_status(f"Command dispatch failed: {exc}")

    thread = threading.Thread(target=worker, args=(command_text,), daemon=True)
    thread.start()


def monitor_audio_stream() -> None:
    audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=20)
    active_buffer = np.zeros((0, CHANNELS), dtype=np.float32)
    silence_frames = 0
    voice_active = False

    def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            log_status(f"InputStream status: {status}")
        try:
            audio_queue.put_nowait(indata.copy())
        except queue.Full:
            log_status("Audio queue is full; dropping audio frame.")

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=callback,
        ):
            log_status("Voice listener started. Listening for 'Hey Jarvis' or 'Jarvis'.")
            while True:
                try:
                    chunk = audio_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                energy = rms_level(chunk)
                if energy >= VAD_ENERGY_THRESHOLD:
                    silence_frames = 0
                    voice_active = True
                    active_buffer = np.concatenate([active_buffer, chunk], axis=0)
                    if active_buffer.shape[0] > SAMPLE_RATE * MAX_VOICE_SECONDS:
                        active_buffer = active_buffer[-int(SAMPLE_RATE * MAX_VOICE_SECONDS) :]
                elif voice_active:
                    silence_frames += 1
                    if silence_frames >= 3:
                        if active_buffer.shape[0] > 0:
                            wav_bytes = format_wav_bytes(active_buffer)
                            transcript = transcribe_audio_chunk(wav_bytes)
                            if transcript:
                                command_text = extract_command_from_transcript(transcript)
                                if command_text:
                                    log_status(f"Wake phrase detected. Command extracted: '{command_text}'")
                                    dispatch_command_async(command_text)
                                else:
                                    log_status(f"Wake word heard but no command extracted: '{transcript}'")
                            active_buffer = np.zeros((0, CHANNELS), dtype=np.float32)
                        voice_active = False
                        silence_frames = 0
                else:
                    continue
    except Exception as exc:
        log_status(f"Audio stream error: {exc}")
        time.sleep(2.0)
        monitor_audio_stream()


def main() -> None:
    log_status("Starting native Windows microphone voice listener.")
    try:
        monitor_audio_stream()
    except KeyboardInterrupt:
        log_status("Voice listener stopped by keyboard interrupt.")
    except Exception as exc:
        log_status(f"Fatal listener error: {exc}")


if __name__ == "__main__":
    main()
