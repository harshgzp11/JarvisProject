import io
import logging
import os
import re
import threading
import time
import wave

import numpy as np
import requests
import sounddevice as sd

API_URL = "http://127.0.0.1:8000/api/assistant/chat"
WAKE_KEYWORDS = ["hey jarvis", "jarvis"]
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SECONDS = 3.0
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_SECONDS)
TRANSCRIPTION_ENDPOINT = None
HEARTBEAT_INTERVAL = 5.0
GAIN_MULTIPLIER = 15.0
VOLUME_TRIGGER_THRESHOLD = 0.01
TARGET_DEVICE_NAME = "microphone array"

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


def select_input_device() -> int:
    devices = sd.query_devices()
    fallback_index = None
    fallback_name = None

    for index, device in enumerate(devices):
        if device["max_input_channels"] <= 0:
            continue

        name = str(device["name"]).lower()
        if TARGET_DEVICE_NAME in name:
            log_status(f"Using Microphone: {device['name']}")
            return index

        if fallback_index is None:
            fallback_index = index
            fallback_name = device["name"]

    if fallback_index is not None:
        log_status(f"Using Microphone: {fallback_name}")
        return fallback_index

    raise RuntimeError("No input audio device found. Please connect a microphone.")


def compute_volume(audio_chunk: np.ndarray) -> float:
    if audio_chunk.size == 0:
        return 0.0

    samples = audio_chunk.astype(np.float32)
    normalized = samples / np.iinfo(np.int16).max
    boosted = normalized * GAIN_MULTIPLIER
    return float(np.linalg.norm(boosted) / boosted.size)


def transcribe_audio_chunk(audio_chunk: np.ndarray) -> str | None:
    volume = compute_volume(audio_chunk)
    print(f"[DEBUG] Audio volume: {volume:.6f}")
    if volume > VOLUME_TRIGGER_THRESHOLD:
        print("[DEBUG] Voice Detected")
        return "jarvis"
    return None


def dispatch_command_async(command_text: str) -> None:
    def worker(command: str) -> None:
        payload = {"message": command}
        try:
            response = requests.post(API_URL, json=payload, timeout=10)
            response.raise_for_status()
            log_status(f"Dispatched command: '{command}' -> status {response.status_code}")
        except Exception as exc:
            if isinstance(exc, requests.Timeout):
                log_status(f"Command dispatch timed out: {exc}")
            else:
                log_status(f"Command dispatch failed: {exc}")

    thread = threading.Thread(target=worker, args=(command_text,), daemon=True)
    thread.start()


def monitor_audio_stream() -> None:
    device_index = select_input_device()

    def heartbeat() -> None:
        while True:
            log_status("Heartbeat: Listening...")
            time.sleep(HEARTBEAT_INTERVAL)

    hb_thread = threading.Thread(target=heartbeat, daemon=True)
    hb_thread.start()

    try:
        log_status("Voice listener started. Listening for 'Hey Jarvis' or 'Jarvis'.")
        with sd.InputStream(device=device_index, samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
            while True:
                try:
                    audio_chunk, _ = stream.read(CHUNK_SIZE)
                    if audio_chunk.size == 0:
                        continue

                    samples = np.asarray(audio_chunk, dtype=np.int16)
                    raw_volume = compute_volume(samples)
                    print(f"[DEBUG] Captured chunk volume: {raw_volume:.6f}")

                    transcript = transcribe_audio_chunk(samples)
                    if not transcript:
                        continue

                    cleaned_text = transcript.strip()
                    if not cleaned_text:
                        continue

                    print(f"[VOICE] {cleaned_text}")
                    lowered = cleaned_text.lower()
                    if any(keyword in lowered for keyword in WAKE_KEYWORDS):
                        command_text = ""
                        for keyword in WAKE_KEYWORDS:
                            if keyword in lowered:
                                command_text = re.sub(rf"\b{re.escape(keyword)}\b", "", lowered, flags=re.IGNORECASE).strip()
                                break
                        command_text = re.sub(r"^[,.:;\-\s]+", "", command_text).strip()
                        if command_text:
                            log_status(f"Wake phrase detected. Command extracted: '{command_text}'")
                            dispatch_command_async(command_text)
                        else:
                            log_status("Wake word detected; waiting for the next spoken command.")
                except Exception as exc:
                    log_status(f"Audio capture loop error: {exc}")
                    time.sleep(1.0)
    except Exception as exc:
        log_status(f"Microphone error: {exc}")
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
