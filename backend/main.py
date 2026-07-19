from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
try:
    import ollama
except ImportError:
    ollama = None  # type: ignore
import json
import logging
from pydantic import ValidationError
from google.oauth2 import id_token
from google.auth.transport import requests
from jose import jwt
from datetime import datetime, timedelta
import os
import shutil
from typing import Optional, Any, Dict, List
import requests as http_requests
import threading
import re
import subprocess
import webbrowser
import difflib
import time
from urllib.parse import quote_plus, urlparse
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

try:
    import pyautogui
except ImportError:
    pyautogui = None  # type: ignore

try:
    import pyperclip
except ImportError:
    pyperclip = None  # type: ignore

try:
    import pygetwindow as gw
except ImportError:
    gw = None  # type: ignore

try:
    from PIL import Image, ImageDraw, ImageGrab
except ImportError:
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageGrab = None  # type: ignore

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore
try:
    import winshell
except ImportError:
    winshell = None  # type: ignore
try:
    from win32com.client import Dispatch
except ImportError:
    Dispatch = None  # type: ignore
try:
    import pystray
    from pystray import MenuItem as item
except ImportError:
    pystray = None  # type: ignore
try:
    import keyboard
except ImportError:
    keyboard = None  # type: ignore

import database
import models
import os_tools
from database import SessionLocal, Message


# Configure module-level logger (used throughout for CRITICAL/WARNING startup events)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("jarvis.main")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = verify_required_config()
    if not SECRET_KEY:
        logger.critical(
            "CRITICAL: JWT_SECRET is not set or is empty. "
            "The server cannot issue or verify tokens. Set JWT_SECRET in your .env file."
        )
        raise RuntimeError(
            "JWT_SECRET is missing from the environment. "
            "Refusing to start without a valid secret key."
        )
    if missing:
        logger.warning("Server starting with missing config keys: %s", ", ".join(missing))
    database.init_db()
    threading.Thread(target=setup_system_tray, daemon=True).start()
    threading.Thread(target=start_voice_listener, daemon=True).start()
    yield

app = FastAPI(title="Jarvis Backend", description="AI-Driven Desktop Assistant API", lifespan=lifespan)

# Setup CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, this should be restricted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Import all configuration from the central config module ─────────────────
# config.py handles .env loading, exports clean named constants, and validates
# required keys.  Do NOT call os.getenv() directly in this file.
import config as cfg

JWT_SECRET     = cfg.JWT_SECRET
SECRET_KEY     = cfg.JWT_SECRET          # alias used by jose/jwt helpers below
ALGORITHM     = cfg.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = cfg.ACCESS_TOKEN_EXPIRE_MINUTES
GOOGLE_CLIENT_ID = cfg.GOOGLE_CLIENT_ID
BACKEND_URL   = cfg.BACKEND_URL
OLLAMA_ENDPOINT = cfg.OLLAMA_ENDPOINT
OLLAMA_MODEL  = cfg.OLLAMA_MODEL
WORKSPACE_DIR = cfg.WORKSPACE_PATH


def verify_required_config() -> list[str]:
    """Delegates to config.verify_required_config() which owns the required-key list."""
    return cfg.verify_required_config()


_app_index_cache = None

def discover_installed_apps():
    """
    Dynamically crawls installed applications using PowerShell Get-StartApps (covers UWP and Desktop apps)
    and falls back to Start Menu folders. Caches the result to prevent lag on subsequent calls.
    """
    global _app_index_cache
    if _app_index_cache is not None:
        return _app_index_cache

    app_index = {}
    
    # 1. Use Get-StartApps for comprehensive listing (UWP + standard apps)
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout:
            apps = json.loads(result.stdout)
            for app in apps:
                name = app.get("Name", "")
                appid = app.get("AppID", "")
                if name and appid:
                    clean_name = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
                    if clean_name:
                        app_index[clean_name] = f"shell:AppsFolder\\{appid}"
    except Exception as e:
        print(f"[APP DISCOVERY] Failed to run Get-StartApps: {e}")

    # 2. Fallback to manually crawling Start Menu
    program_data = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
    app_data = os.environ.get('APPDATA', '')
    start_menu_paths = [
        os.path.join(program_data, r'Microsoft\Windows\Start Menu\Programs'),
        os.path.join(app_data, r'Microsoft\Windows\Start Menu\Programs')
    ]
    for base_path in start_menu_paths:
        if not os.path.exists(base_path):
            continue
        for root, _, files in os.walk(base_path):
            for file in files:
                if not file.lower().endswith(('.lnk', '.exe')):
                    continue
                display_name = os.path.splitext(file)[0].lower()
                clean_name = re.sub(r"[^a-z0-9]+", " ", display_name).strip()
                if clean_name and clean_name not in app_index:
                    app_index[clean_name] = os.path.join(root, file)

    # 3. Cache and return
    _app_index_cache = app_index
    return app_index

def smart_launch(app_name):
    """
    Attempts to intelligently discover and launch an application by name.
    """
    app_name_clean = app_name.lower().strip()

    if not app_name_clean:
        return "No application name provided."

    if shutil.which(app_name_clean):
        os.system(f"start {app_name_clean}")
        return f"Launched system utility: {app_name_clean}"

    installed_apps = discover_installed_apps()
    
    # Check for exact matches first
    if app_name_clean in installed_apps:
        matches = [app_name_clean]
    else:
        # Increase cutoff to 0.75 to prevent absurd matches like 'calculator' -> 'narrator'
        matches = difflib.get_close_matches(app_name_clean, installed_apps.keys(), n=1, cutoff=0.75)

    if matches:
        matched_name = matches[0]
        shortcut_path = installed_apps[matched_name]
        try:
            if shortcut_path.startswith("shell:AppsFolder\\"):
                subprocess.Popen(["explorer", shortcut_path], shell=True)
            else:
                os.startfile(shortcut_path)
            return f"Dynamically discovered and opened {matched_name}"
        except AttributeError:
            subprocess.Popen([shortcut_path], shell=True)
            return f"Opened shortcut via fallback execution: {matched_name}"
        except Exception as exc:
            return f"Failed to launch {matched_name}: {exc}"

    return f"Could not locate an application named '{app_name}' on this system."

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(database.get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token.")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token session.")
        user = db.query(database.User).filter(database.User.email == email).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User session not found.")
        return user
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token session.")

# ==========================================
# SYSTEM TRAY & VOICE COMMAND CORE DEFINITIONS
# ==========================================

is_jarvis_muted = False
is_recording_voice = False
# WORKSPACE_DIR is resolved from the .env WORKSPACE_PATH key (set at line 110).
# Do NOT reassign here — the value from os.getenv above is the single source of truth.

def ensure_workspace_dir():
    try:
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
    except Exception as e:
        print(f"Failed to create public workspace directory: {e}")

def list_workspace_files():
    ensure_workspace_dir()
    try:
        if not os.path.exists(WORKSPACE_DIR):
            return []
        files = os.listdir(WORKSPACE_DIR)
        result = []
        for file in files:
            filepath = os.path.join(WORKSPACE_DIR, file)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                result.append({
                    "name": file,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        return result
    except Exception as e:
        print(f"Failed to list files in indexer: {e}")
        return []

def handle_file_creation(user_input: str) -> str:
    ensure_workspace_dir()
    filename_match = re.search(r"(\w+\.\w+)", user_input)
    filename = filename_match.group(1) if filename_match else "note.txt"
    
    content = "Hello from Jarvis."
    if "content" in user_input:
        parts = user_input.split("content")
        if len(parts) > 1:
            content = parts[1].strip(" '\"")
    elif "write" in user_input:
        parts = user_input.split("write")
        if len(parts) > 1:
            content = parts[1].strip(" '\"")
            
    filepath = os.path.join(WORKSPACE_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully created file '{filename}' with content size {len(content)} bytes."
    except Exception as e:
        return f"Failed to create file: {str(e)}"

def create_tray_image():
    image = Image.new('RGB', (64, 64), color=(0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.polygon([(32, 12), (52, 48), (12, 48)], fill=(255, 255, 255))
    return image

def on_tray_action(icon, item):
    global is_jarvis_muted
    action_str = str(item)
    if action_str == "Show Console":
        print("Tray Command: Show Console triggered.")
    elif action_str == "Mute Jarvis":
        is_jarvis_muted = not is_jarvis_muted
        print(f"Tray Command: Mute status updated to {is_jarvis_muted}")
    elif action_str == "Exit":
        print("Tray Command: Exit backend requested.")
        icon.stop()
        os._exit(0)

def setup_system_tray():
    if not pystray:
        print("System tray is disabled (pystray package missing).")
        return
    try:
        menu = pystray.Menu(
            item('Show Console', on_tray_action),
            item('Mute Jarvis', on_tray_action, checked=lambda item: is_jarvis_muted),
            item('Exit', on_tray_action)
        )
        icon = pystray.Icon("Jarvis Core", create_tray_image(), "Jarvis Core", menu)
        icon.run()
    except Exception as e:
        print(f"Failed to start system tray icon: {e}")

def record_and_transcribe():
    global is_recording_voice
    if is_recording_voice:
        return
    is_recording_voice = True
    print("Voice activation triggered! Listening for speech...")
    transcription = ""
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        r.energy_threshold = 300
        r.pause_threshold = 0.8
        with sr.Microphone() as source:
            print("Adjusting for ambient noise...")
            r.adjust_for_ambient_noise(source, duration=0.6)
            print("Listening... speak now.")
            audio = r.listen(source, timeout=5, phrase_time_limit=6)
        transcription = r.recognize_google(audio)
        print(f"[VOICE] Transcription captured: '{transcription}'")
    except Exception as e:
        # No mic, no audio, recognition timeout — abort cleanly. Do NOT fall back to any hardcoded command.
        print(f"[VOICE] Speech capture failed or no speech detected: {e}. Aborting voice dispatch.")
        is_recording_voice = False
        return

    if not transcription.strip():
        print("[VOICE] Empty transcription. Aborting.")
        is_recording_voice = False
        return

    try:
        from database import SessionLocal
        import models
        db = SessionLocal()
        from database import User
        # DEV_USER_EMAIL is sourced from .env — never hardcoded.
        dev_email = cfg.DEV_USER_EMAIL
        dev_user = db.query(User).filter(User.email == dev_email).first()
        if not dev_user:
            dev_user = User(
                google_id="voice_system_user",
                email=dev_email,
                full_name=cfg.DEV_USER_NAME,
                picture_url=""
            )
            db.add(dev_user)
            db.commit()
            db.refresh(dev_user)
        req = models.ChatRequest(message=transcription)
        res = assistant_chat(req, db, dev_user)
        print(f"[VOICE] Execution result: {res.response}")
        db.close()
    except Exception as ex:
        print(f"[VOICE] Pipeline error: {ex}")
    finally:
        is_recording_voice = False

def start_voice_listener():
    if not keyboard:
        print("Voice core hotkey registration disabled (keyboard package missing).")
        return
    
    def hotkey_callback():
        threading.Thread(target=record_and_transcribe, daemon=True).start()
    
    try:
        keyboard.add_hotkey('ctrl+space', hotkey_callback)
        print("Keyboard Hotkey listener registered: Press 'Ctrl + Space' to trigger Voice Automation.")
        keyboard.wait()
    except Exception as e:
        print(f"Failed to start keyboard listener: {e}")



@app.get("/")
def read_root():
    return {"message": "Jarvis Backend is running!"}

@app.get("/api/auth/google/config")
def get_google_config():
    return {"client_id": GOOGLE_CLIENT_ID}

@app.post("/api/auth/google/verify", response_model=models.AuthResponse)
def verify_google_token(req: models.GoogleAuthRequest, db: Session = Depends(database.get_db)):
    """
    Verifies a Google OAuth2 ID token, provisions/updates the user record,
    and returns a JWT session token for application authentication.
    """
    try:
        # ── Mock / Dev Auth bypass ──────────────────────────────────────────
        # Read live from os.getenv (not frozen cfg constants) so that changes
        # to .env are reflected immediately after uvicorn auto-reloads.
        # ENABLE_MOCK_AUTH must be "true" AND the token must match MOCK_AUTH_TOKEN.
        # This block NEVER runs in production (ENABLE_MOCK_AUTH defaults to "false").
        _mock_enabled = os.getenv("ENABLE_MOCK_AUTH", "false").lower() == "true"
        _mock_token   = os.getenv("MOCK_AUTH_TOKEN", "")
        if _mock_enabled and _mock_token and req.token == _mock_token:
            dev_email = os.getenv("DEV_USER_EMAIL", "dev@jarvis.local")
            dev_name  = os.getenv("DEV_USER_NAME",  "Jarvis Dev User")
            user = db.query(database.User).filter(database.User.email == dev_email).first()
            if not user:
                user = database.User(
                    google_id="mock_dev_user",
                    email=dev_email,
                    full_name=dev_name,
                    picture_url=""
                )
                db.add(user)
                try:
                    db.commit()
                    db.refresh(user)
                except Exception as e:
                    db.rollback()
                    raise HTTPException(status_code=500, detail=f"Database transaction failure: {str(e)}")
            session_token = create_access_token(data={"sub": user.email})
            return models.AuthResponse(
                status="success",
                message="Google authentication handshake complete (mock bypass).",
                token=session_token
            )


        # Verify OAuth2 token signature, expiration, and audience check if client ID is set
        request_transport = requests.Request()
        audience = GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID else None
        
        idinfo = id_token.verify_oauth2_token(req.token, request_transport, audience)
        
        google_id = idinfo.get("sub")
        email = idinfo.get("email")
        full_name = idinfo.get("name")
        picture_url = idinfo.get("picture")
        
        if not google_id or not email:
            raise HTTPException(status_code=400, detail="Missing critical claims (Google ID or Email) in token.")
        
        # Check if user already exists with this google_id
        user = db.query(database.User).filter(database.User.google_id == google_id).first()
        if not user:
            # Fallback check if user email is registered without a google_id (transition phase)
            user = db.query(database.User).filter(database.User.email == email).first()
            if user:
                user.google_id = google_id
                user.full_name = full_name
                user.picture_url = picture_url
            else:
                user = database.User(
                    google_id=google_id,
                    email=email,
                    full_name=full_name,
                    picture_url=picture_url
                )
                db.add(user)
            
            try:
                db.commit()
                db.refresh(user)
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Database transaction failure during provisioning: {str(e)}")
        else:
            # Sync user profile details if changed
            updated = False
            if user.full_name != full_name:
                user.full_name = full_name
                updated = True
            if user.picture_url != picture_url:
                user.picture_url = picture_url
                updated = True
            if updated:
                try:
                    db.commit()
                    db.refresh(user)
                except Exception:
                    db.rollback()

        # Generate custom application session token
        session_token = create_access_token(data={"sub": user.email})
        return models.AuthResponse(
            status="success",
            message="Google authentication handshake complete.",
            token=session_token
        )
    except ValueError as val_err:
        raise HTTPException(status_code=401, detail=f"Invalid Google ID token: {str(val_err)}")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal authentication server error: {str(e)}")

@app.get("/api/auth/google/callback", response_class=HTMLResponse)
def google_callback():
    """
    Serves a simple HTML page that extracts the Google OAuth2 ID Token from the URL fragment
    and sends it to the parent window (opener) via postMessage before closing.
    """
    html_content = """
    <html>
    <head>
        <title>Authorizing Jarvis</title>
        <style>
            body {
                background-color: #000000;
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }
            .card {
                text-align: center;
                border: 1px solid #27272a;
                background-color: #09090b;
                padding: 32px;
                max-width: 320px;
                border-radius: 0px;
            }
            h3 {
                margin: 0 0 8px;
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 1px;
                text-transform: uppercase;
            }
            p {
                font-size: 11px;
                color: #a1a1aa;
                margin: 0;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h3>Authorizing</h3>
            <p>Completing system core authentication handshake...</p>
        </div>
        <script>
            // Parse hash fragment
            const hash = window.location.hash;
            if (hash) {
                const params = new URLSearchParams(hash.substring(1));
                const idToken = params.get("id_token");
                if (idToken) {
                    if (window.opener) {
                        window.opener.postMessage({ type: "GOOGLE_AUTH_SUCCESS", token: idToken }, "*");
                        window.close();
                    } else {
                        // fallback if no opener is found
                        document.querySelector("p").innerText = "Authentication completed. Close this window.";
                    }
                } else {
                    document.querySelector("p").innerText = "No credentials received from Google. Please close and try again.";
                }
            } else {
                document.querySelector("p").innerText = "Waiting for authorization hash redirection...";
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/auth/verify")
def verify_token(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = None,
    db: Session = Depends(database.get_db)
):
    actual_token = token
    if authorization and authorization.startswith("Bearer "):
        actual_token = authorization.split(" ")[1]
        
    if not actual_token:
        raise HTTPException(status_code=400, detail="Token is required.")
        
    try:
        payload = jwt.decode(actual_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token session.")
        
        user = db.query(database.User).filter(database.User.email == email).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User session not found.")
            
        return {"status": "success", "message": "Token is valid.", "email": email}
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token session.")

def parse_intent_with_llm(user_input: str) -> models.LLMIntent:
    """
    Calls the local Ollama LLM to parse natural language intent.
    Enforces a strict Pydantic JSON schema format.
    """
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        "You are a precise OS assistant intent parser. Your goal is to map user commands to the system intent.\n"
                        "Classify the user input into one of the following intents:\n"
                        "- open_app: user wants to launch/open/start an application (e.g. notepad, calculator, paint, browser)\n"
                        "- screenshot: user wants to capture/take a screenshot\n"
                        "- system_query: user wants to perform other actions like adjusting volume (volume_up, volume_down, volume_mute) or media playback (play_pause)\n\n"
                        "For open_app, set target_param to the name of the app (e.g. 'notepad', 'calculator').\n"
                        "For system_query, set target_param to the specific system action (e.g. 'volume_up', 'volume_down', 'volume_mute', 'play_pause').\n"
                        "For screenshot, set target_param to null.\n"
                        "Only output raw valid JSON adhering to the specified schema."
                    )
                },
                {
                    'role': 'user',
                    'content': user_input
                }
            ],
            format=models.LLMIntent.model_json_schema()
        )
        content = response.message.content
        if not content:
            raise ValueError("LLM returned empty response")
        parsed_intent = models.LLMIntent.model_validate_json(content)
        return parsed_intent
    except (ValidationError, json.JSONDecodeError) as val_err:
        print(f"LLM output validation failed: {val_err}. Content: {content}")
        raise HTTPException(
            status_code=422,
            detail=f"LLM failed to output a valid intent schema. Error: {str(val_err)}"
        )
    except Exception as e:
        print(f"Failed to query LLM: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"LLM parsing service error: {str(e)}"
        )

@app.post("/api/execute", response_model=models.ExecuteResponse)
def execute_command(
    req: models.ExecuteRequest,
    db: Session = Depends(database.get_db),
    current_user: database.User = Depends(get_current_user)
):
    user_input = req.user_input
    
    # 1. Determine intent via LLM router
    try:
        parsed_llm_intent = parse_intent_with_llm(user_input)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal LLM processing error: {str(e)}")
        
    intent = parsed_llm_intent.intent
    target_param = parsed_llm_intent.target_param
    
    response_msg = ""
    status = "pending"
    
    # 2. Execute Action based on Intent
    if intent == "open_app":
        app_alias = target_param.strip().lower() if target_param else ""
        if not app_alias:
            status, response_msg = "error", "Could not determine which application to launch."
        else:
            # 1. Check user-configured custom mappings in the database first.
            db_app = db.query(database.AppMapping).filter(
                database.AppMapping.alias_name.ilike(f"%{app_alias}%")
            ).first()

            if db_app:
                # User has a pinned path — use it directly via os_tools.
                result = os_tools.launch_application(db_app.system_path)
                status = result["status"]
                response_msg = result["message"]
            else:
                # 2. No DB entry — fall through to dynamic discovery via Start Menu indexer.
                # smart_launch() crawls Start Menu directories and uses fuzzy matching.
                # It also checks PATH (shutil.which) so system utilities like calc.exe
                # and notepad.exe are found naturally without any hardcoded aliases.
                launch_msg = smart_launch(app_alias)
                if "Could not locate" in launch_msg:
                    status = "error"
                    response_msg = launch_msg
                else:
                    status = "success"
                    response_msg = launch_msg
                
    elif intent == "screenshot":
        result = os_tools.take_screenshot()
        status = result["status"]
        response_msg = result["message"]
        
    elif intent == "system_query":
        valid_media_actions = ["volume_up", "volume_down", "volume_mute", "play_pause"]
        action_mapping = {
            "mute": "volume_mute",
            "volume_mute": "volume_mute",
            "volume mute": "volume_mute",
            "up": "volume_up",
            "volume_up": "volume_up",
            "volume up": "volume_up",
            "down": "volume_down",
            "volume_down": "volume_down",
            "volume down": "volume_down",
            "play": "play_pause",
            "pause": "play_pause",
            "play_pause": "play_pause",
            "play pause": "play_pause"
        }
        
        normalized_action = action_mapping.get(target_param.lower()) if target_param else None
        
        if normalized_action in valid_media_actions:
            result = os_tools.adjust_media_controls(normalized_action)
            status = result["status"]
            response_msg = result["message"]
        else:
            status = "error"
            response_msg = f"System command '{target_param}' not recognized or unsupported."
            
    else:
        status = "error"
        response_msg = "Unknown command or intent not recognized."
        
    # 3. Log to database
    try:
        log_entry = database.AssistantLog(
            user_input=user_input,
            detected_intent=intent,
            ai_response=response_msg,
            status=status
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"Failed to save log to DB: {e}")

    return models.ExecuteResponse(
        status=status,
        message=response_msg,
        intent=intent
    )

def handle_command(user_input: str) -> Optional[dict]:
    """Intent router for lightweight open/search operations without entering the vision loop."""
    if not user_input or not isinstance(user_input, str):
        return None

    normalized_input = user_input.strip()
    lowered = normalized_input.lower()

    open_match = re.search(r"\b(?:open|launch|start)\s+(.+)$", lowered)
    if open_match:
        app_key = open_match.group(1).strip().lower()
        try:
            result_message = smart_launch(app_key)
        except Exception as exc:
            print(f"[FAST LAUNCH] Failed to launch {app_key}: {exc}")
            return {"status": "error", "message": str(exc)}

        if "Could not locate" in result_message:
            return {"status": "error", "message": result_message}

        return {"status": "success", "message": "Success", "payload": result_message}

    search_match = re.search(r"\b(?:search|find)(?:\s+for)?\s+(.+)$", lowered)
    if search_match:
        query = search_match.group(1).strip()
        search_url = f"https://www.google.com/search?q={quote_plus(query)}"
        webbrowser.open(search_url, new=2)
        return {"status": "success", "message": f"Searching web for: {query}", "payload": search_url}

    confidence = 0.0
    if re.search(r"\b(open|launch|start|search|find)\b", lowered):
        confidence = 0.85
    elif len(normalized_input.split()) >= 2:
        confidence = 0.6

    if confidence < 0.8:
        return {"status": "error", "message": "Did you mean search or open?"}

    return None


def capture_desktop_state() -> dict:
    """
    Capture the current primary desktop frame for local vision-style agent reasoning.
    Returns a lightweight state payload with image dimensions and an RGB array.
    """
    if ImageGrab is None or np is None:
        return {"width": 0, "height": 0, "rgb_array": None, "error": "Image capture dependencies are unavailable"}

    try:
        screenshot = ImageGrab.grab(all_screens=False)
        if screenshot is None:
            return {"width": 0, "height": 0, "rgb_array": None, "error": "No screenshot captured"}

        rgb_image = screenshot.convert("RGB")
        rgb_array = np.array(rgb_image)
        if rgb_array.ndim == 2:
            rgb_array = np.repeat(rgb_array[:, :, None], 3, axis=2)

        height, width = rgb_array.shape[:2]
        return {
            "timestamp": time.time(),
            "width": width,
            "height": height,
            "rgb_array": rgb_array,
            "mode": "primary_monitor"
        }
    except Exception as e:
        print(f"[DESKTOP EYES] Failed to capture desktop state: {e}")
        return {"width": 0, "height": 0, "rgb_array": None, "error": str(e)}


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url
    if not re.match(r"^https?://", url, re.IGNORECASE):
        if url.startswith("www."):
            return "https://" + url
        if re.match(r"^[\w-]+(\.[\w-]+)+.*$", url):
            return "https://" + url
    return url


def parse_simple_agent_intent(user_msg: str) -> Optional[dict]:
    if not user_msg or not user_msg.strip():
        return None

    normalized = user_msg.strip()
    lower = normalized.lower()

    url_match = re.search(r"\b(?:open|go to)\s+(?P<url>(?:https?://|http://|www\.)\S+)$", lower)
    if url_match:
        return {"type": "open_url", "url": normalize_url(url_match.group("url"))}

    host_match = re.search(r"\b(?:open|go to)\s+(?P<host>[\w.-]+\.[a-z]{2,6}(?:/\S*)?)$", lower)
    if host_match:
        return {"type": "open_url", "url": normalize_url(host_match.group("host"))}

    search_match = re.search(r"\b(?:search|find)(?:\s+for)?\s+(?P<query>.+)$", lower)
    if search_match:
        return {"type": "search", "query": search_match.group("query").strip()}

    quick_app_match = re.search(r"\b(?:open|launch|start)\s+(.+)$", lower)
    if quick_app_match:
        return {"type": "open_app", "app": quick_app_match.group(1).strip()}

    direct_site_match = re.search(r"\b(?:open|go to)\s+(google|youtube|github|stackoverflow)$", lower)
    if direct_site_match:
        site = direct_site_match.group(1)
        url_map = {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "github": "https://www.github.com",
            "stackoverflow": "https://stackoverflow.com"
        }
        return {"type": "open_url", "url": url_map.get(site, "https://www.google.com")}

    return None


def execute_simple_agent_intent(intent: dict) -> dict:
    try:
        if intent.get("type") == "open_url":
            url = normalize_url(str(intent.get("url", "")).strip())
            if not url:
                return {"status": "error", "message": "Invalid URL provided."}
            webbrowser.open(url, new=2)
            return {"status": "success", "message": f"Opened URL: {url}", "execution_type": "BROWSER_URL", "payload": url}

        if intent.get("type") == "search":
            query = str(intent.get("query", "")).strip()
            if not query:
                return {"status": "error", "message": "Search query was empty."}
            url = f"https://www.google.com/search?q={quote_plus(query)}"
            webbrowser.open(url, new=2)
            return {"status": "success", "message": f"Searching Google for: {query}", "execution_type": "BROWSER_URL", "payload": url}

        if intent.get("type") == "open_app":
            app_alias = str(intent.get("app", "")).strip()
            result_message = smart_launch(app_alias)
            return {
                "status": "success" if "Could not locate" not in result_message else "error",
                "message": result_message,
                "execution_type": "SHELL_COMMAND",
                "payload": app_alias,
            }

        return {"status": "none", "message": "No simple routing rule matched."}
    except Exception as e:
        print(f"[FAST ROUTER] Failed to execute simple intent: {e}")
        return {"status": "error", "message": str(e)}



def save_message_to_db(user_id, conversation_id, sender, content):
    """Saves a message to the database and links it to a conversation."""
    db = SessionLocal()
    try:
        # 1. Create a new message entry
        new_message = Message(
            conversation_id=conversation_id,
            sender=sender,
            content=content
        )
        db.add(new_message)
        db.commit()
    finally:
        db.close()

# Inside your chat handling function in main.py
import asyncio

async def generate_ai_response(user_input: str) -> str:
    """Generates an AI response using the local Ollama LLM."""
    try:
        import ollama
        response = await asyncio.to_thread(
            ollama.chat,
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': user_input}]
        )
        return str(response['message']['content']) if isinstance(response, dict) else str(response.message.content)
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "I'm sorry, I encountered an error while trying to process your request."

async def handle_chat_input(user_input, current_session_id):
    # 1. Save user input immediately
    save_message_to_db(user_id=1, conversation_id=current_session_id, sender="user", content=user_input)

    # 2. Generate the AI response
    ai_response = await generate_ai_response(user_input)

    # 3. Save the AI response immediately
    save_message_to_db(user_id=1, conversation_id=current_session_id, sender="ai", content=ai_response)
    
    return ai_response


def execute_agent_action(action: dict) -> dict:
    """
    Native desktop action executor for the autonomous Computer Use Agent loop.
    Supports SHELL_EXECUTE, MOUSE_CLICK, TYPE_TEXT, and KEYBOARD_SHORTCUT.
    """
    if not isinstance(action, dict):
        return {"status": "error", "message": "Action payload must be an object."}

    if pyautogui is None:
        return {"status": "error", "message": "pyautogui is not available in this environment."}

    action_type = str(action.get("action", "")).upper()
    try:
        if action_type == "SHELL_EXECUTE":
            command = str(action.get("command", "")).strip()
            if not command:
                return {"status": "error", "message": "SHELL_EXECUTE requires a command."}
            subprocess.Popen(command, shell=True)
            return {"status": "success", "message": f"Executed shell command: {command}"}

        if action_type == "MOUSE_CLICK":
            x = int(action.get("x", 0))
            y = int(action.get("y", 0))
            pyautogui.click(x, y)
            return {"status": "success", "message": f"Clicked screen coordinate ({x}, {y})"}

        if action_type == "TYPE_TEXT":
            text = str(action.get("text", ""))
            pyautogui.write(text, interval=0.01)
            return {"status": "success", "message": f"Typed {len(text)} characters"}

        if action_type == "KEYBOARD_SHORTCUT":
            keys = action.get("keys", [])
            if not isinstance(keys, list) or not keys:
                return {"status": "error", "message": "KEYBOARD_SHORTCUT requires a non-empty keys array."}
            normalized_keys = [str(k).strip().lower() for k in keys if str(k).strip()]
            if normalized_keys:
                pyautogui.hotkey(*normalized_keys)
            return {"status": "success", "message": f"Executed shortcut: {'+'.join(normalized_keys)}"}

        return {"status": "error", "message": f"Unsupported action type: {action_type}"}
    except Exception as e:
        print(f"[AGENT ACTION] Failed to execute action {action_type}: {e}")
        return {"status": "error", "message": str(e)}


def execute_system_action(steps: list) -> dict:
    """
    Sequential GUI Orchestration Engine.
    Executes an array of steps (LAUNCH, WAIT, TYPE, SHORTCUT, PASTE) chronologically.
    """
    if not steps:
        return {"status": "none", "message": "No automation steps to execute."}

    if pyautogui is None or pyperclip is None:
        return {"status": "error", "message": "Desktop automation dependencies are not available in this environment."}

    executed_steps = []
    try:
        for idx, step in enumerate(steps):
            step_type = str(step.get("type", "")).upper()
            payload = step.get("payload", "")

            print(f"[GUI ENGINE] Step {idx+1}/{len(steps)} | Type: {step_type} | Payload: {payload}")

            if step_type == "LAUNCH":
                subprocess.Popen(payload, shell=True)
                executed_steps.append(f"LAUNCH({payload})")

                try:
                    normalized_payload = str(payload).lower()
                    title_hint = None
                    if "notepad" in normalized_payload:
                        title_hint = "Notepad"
                    elif "calc" in normalized_payload or "calculator" in normalized_payload:
                        title_hint = "Calculator"
                    elif "mspaint" in normalized_payload or "paint" in normalized_payload:
                        title_hint = "Paint"
                    elif "wordpad" in normalized_payload:
                        title_hint = "WordPad"
                    elif "code" in normalized_payload or "vscode" in normalized_payload:
                        title_hint = "Visual Studio Code"
                    elif "chrome" in normalized_payload:
                        title_hint = "Google Chrome"
                    elif "edge" in normalized_payload:
                        title_hint = "Microsoft Edge"

                    target = title_hint or os.path.splitext(str(payload))[0]
                    for retry in range(3):
                        windows = gw.getWindowsWithTitle(target) if target else []
                        if windows:
                            try:
                                windows[0].activate()
                                windows[0].maximize()
                                break
                            except Exception:
                                pass
                        time.sleep(0.3)
                except Exception as activation_error:
                    print(f"[GUI ENGINE] Window activation failed after launch: {activation_error}")

            elif step_type == "WAIT":
                try:
                    duration = float(payload)
                except (TypeError, ValueError):
                    duration = 1.0
                time.sleep(duration)
                executed_steps.append(f"WAIT({duration}s)")

            elif step_type == "TYPE":
                pyautogui.write(str(payload), interval=0.01)
                executed_steps.append(f"TYPE({len(str(payload))} chars)")

            elif step_type == "SHORTCUT":
                keys = [k.strip().lower() for k in str(payload).split("+") if k.strip()]
                if keys:
                    pyautogui.hotkey(*keys)
                executed_steps.append(f"SHORTCUT({payload})")

            elif step_type == "MAKE_SHORTCUT":
                if not isinstance(payload, dict):
                    print(f"[GUI ENGINE] MAKE_SHORTCUT invalid payload: {payload}")
                else:
                    shortcut_name = str(payload.get("name", "Jarvis Shortcut")).strip()
                    target_path = str(payload.get("target_path", "")).strip()
                    if shortcut_name and target_path:
                        if not winshell or not Dispatch:
                            raise RuntimeError("Windows shortcut creation dependencies are not available.")
                        desktop_path = winshell.desktop()
                        shortcut_path = os.path.join(desktop_path, f"{shortcut_name}.lnk")
                        shell = Dispatch('WScript.Shell')
                        shortcut = shell.CreateShortCut(shortcut_path)
                        shortcut.Targetpath = target_path
                        shortcut.WorkingDirectory = os.path.dirname(target_path)
                        shortcut.save()
                        executed_steps.append(f"MAKE_SHORTCUT({shortcut_path})")
                    else:
                        print("[GUI ENGINE] MAKE_SHORTCUT payload missing required 'name' or 'target_path'.")

            elif step_type == "MOVE_FILE":
                if not isinstance(payload, dict):
                    print(f"[GUI ENGINE] MOVE_FILE invalid payload: {payload}")
                else:
                    source_path = str(payload.get("source", "")).strip()
                    destination_path = str(payload.get("destination", "")).strip()
                    if source_path and destination_path:
                        source_path = os.path.abspath(source_path)
                        destination_path = os.path.abspath(destination_path)
                        shutil.move(source_path, destination_path)
                        executed_steps.append(f"MOVE_FILE({source_path} -> {destination_path})")
                    else:
                        print("[GUI ENGINE] MOVE_FILE payload missing required 'source' or 'destination'.")

            elif step_type == "PASTE":
                pyperclip.copy(str(payload))
                time.sleep(0.1)
                pyautogui.hotkey("ctrl", "v")
                executed_steps.append(f"PASTE({len(str(payload))} chars)")

            else:
                print(f"[GUI ENGINE] Unknown step type: {step_type}")

        return {"status": "success", "message": f"Completed: {', '.join(executed_steps)}"}
    except Exception as e:
        print(f"[GUI ENGINE] Error during sequence: {e}")
        return {"status": "error", "message": f"Orchestration failed: {str(e)}"}


@app.post("/api/assistant/chat", response_model=models.ChatResponse)
def assistant_chat(
    req: models.ChatRequest,
    db: Session = Depends(database.get_db),
    current_user: database.User = Depends(get_current_user)
):
    user_msg = req.message

    fast_command_result = handle_command(user_msg)
    if fast_command_result is not None:
        return models.ChatResponse(
            response=fast_command_result.get("message", "Success"),
            intent="SYSTEM_COMMAND",
            action="none",
            execution_type="SHELL_COMMAND",
            payload=fast_command_result.get("payload"),
            steps=[]
        )

    # Fast-path simple commands before entering vision-based inference.
    simple_intent = parse_simple_agent_intent(user_msg)
    if simple_intent is not None:
        simple_result = execute_simple_agent_intent(simple_intent)
        if simple_result.get("status") == "success":
            return models.ChatResponse(
                response=simple_result.get("message", "Executed command."),
                intent="SYSTEM_COMMAND",
                action="none",
                execution_type=simple_result.get("execution_type", "BROWSER_URL"),
                payload=simple_result.get("payload"),
                steps=[]
            )
        return models.ChatResponse(
            response=simple_result.get("message", "Command routing failed."),
            intent="SYSTEM_COMMAND",
            action="none",
            execution_type=simple_result.get("execution_type", "none"),
            payload=simple_result.get("payload"),
            steps=[]
        )

    # 1. Fetch conversational history from the DB (last 5 message exchanges)
    db_history: List[Dict[str, str]] = []
    try:
        past_logs = db.query(database.AssistantLog).order_by(database.AssistantLog.id.desc()).limit(5).all()
        past_logs.reverse()
        for log in past_logs:
            if log.user_input:
                db_history.append({"role": "user", "content": log.user_input})
            if log.ai_response:
                db_history.append({"role": "assistant", "content": log.ai_response})
    except Exception as e:
        print(f"Failed to query database context history: {e}")

    # 2. Run an autonomous perception-action loop with the local Ollama model.
    url = OLLAMA_ENDPOINT

    def build_system_prompt() -> str:
        return (
            "You are Jarvis, an autonomous computer-use agent for this desktop environment. "
            "You are not limited to a fixed launcher; you may plan and execute a sequence of native tool actions.\n"
            "Return ONLY a valid JSON object with NO markdown fences, NO explanation text outside the JSON.\n\n"
            "Required JSON schema:\n"
            "{\n"
            "  \"response\": \"A concise confirmation or progress update\",\n"
            "  \"objective\": \"The current task goal\",\n"
            "  \"status\": \"in_progress\" | \"completed\" | \"failed\",\n"
            "  \"final_condition\": \"What must be true for the task to be considered complete\",\n"
            "  \"next_action\": {\n"
            "    \"action\": \"SHELL_EXECUTE\" | \"MOUSE_CLICK\" | \"TYPE_TEXT\" | \"KEYBOARD_SHORTCUT\",\n"
            "    \"command\": \"raw terminal command\",\n"
            "    \"x\": 0,\n"
            "    \"y\": 0,\n"
            "    \"text\": \"payload to input\",\n"
            "    \"keys\": [\"ctrl\", \"s\"]\n"
            "  },\n"
            "  \"steps\": [\n"
            "    { \"type\": \"LAUNCH\" | \"WAIT\" | \"PASTE\" | \"SHORTCUT\", \"payload\": \"string\" }\n"
            "  ]\n"
            "}\n\n"
            "Tool-calling blueprint:\n"
            "- SHELL_EXECUTE: execute a raw terminal command for file operations, directory mapping, or launching apps.\n"
            "- MOUSE_CLICK: click a visible UI element using pixel coordinates from the current desktop layout.\n"
            "- TYPE_TEXT: type arbitrary text into the currently focused input field.\n"
            "- KEYBOARD_SHORTCUT: trigger a system macro such as ctrl+s, ctrl+v, alt+tab.\n\n"
            "Rules:\n"
            "- Prefer the smallest valid action that advances the goal.\n"
            "- If the goal is already satisfied, return status 'completed' and set next_action to null.\n"
            "- If you cannot directly act yet, use a safe follow-up action such as WAIT or a harmless shell probe.\n"
            "- Always reason from the current desktop context and the user's stated objective."
        )

    response_text = "Standing by."
    intent = "GENERAL_QUERY"
    action = "none"
    steps = []
    status = "pending"
    agent_trace: List[Dict[str, Any]] = []
    max_steps = 6

    for step_index in range(max_steps):
        desktop_state = capture_desktop_state()
        desktop_summary = (
            f"Desktop size: {desktop_state.get('width', 0)}x{desktop_state.get('height', 0)} px; "
            f"mode={desktop_state.get('mode', 'unknown')}"
        )
        loop_context = (
            f"User objective: {user_msg}\n"
            f"Desktop context: {desktop_summary}\n"
            f"Previous actions: {agent_trace if agent_trace else 'none'}"
        )

        ollama_messages: List[Dict[str, Any]] = [{"role": "system", "content": build_system_prompt()}]
        ollama_messages.extend(db_history)
        ollama_messages.append({"role": "user", "content": loop_context})

        ollama_payload: Dict[str, Any] = {
            "model": OLLAMA_MODEL,
            "messages": ollama_messages,
            "stream": False,
            "format": "json"
        }

        try:
            ollama_resp = http_requests.post(url, json=ollama_payload, timeout=20.0)
            if ollama_resp.status_code == 200:
                data = ollama_resp.json()
                message_content = data.get("message", {}).get("content", "").strip()
                if message_content.startswith("```"):
                    message_content = re.sub(r'^```[^\n]*\n?', '', message_content)
                    message_content = re.sub(r'```$', '', message_content).strip()
                parsed_data = json.loads(message_content)
                response_text = parsed_data.get("response", response_text)
                intent = parsed_data.get("intent", intent)
                steps = parsed_data.get("steps", [])
                if not isinstance(steps, list):
                    steps = []
                action = parsed_data.get("action", "none")

                next_action = parsed_data.get("next_action")
                final_status = str(parsed_data.get("status", "in_progress")).lower()

                if isinstance(next_action, dict) and next_action.get("action"):
                    action_result = execute_agent_action(next_action)
                    agent_trace.append({
                        "step": step_index + 1,
                        "action": next_action.get("action"),
                        "result": action_result.get("status"),
                        "message": action_result.get("message")
                    })
                    if action_result.get("status") != "success":
                        status = "error"
                        response_text = f"Execution error: {action_result.get('message')}"
                        break

                    if final_status == "completed":
                        status = "success"
                        response_text = f"{response_text} ✓"
                        break
                elif steps:
                    legacy_result = execute_system_action(steps)
                    agent_trace.append({
                        "step": step_index + 1,
                        "action": "LEGACY_SEQUENCE",
                        "result": legacy_result.get("status"),
                        "message": legacy_result.get("message")
                    })
                    status = legacy_result.get("status", "pending")
                    response_text = f"{response_text} ✓ ({legacy_result.get('message')})"
                    break
                else:
                    if final_status == "completed":
                        status = "success"
                        response_text = f"{response_text} ✓"
                        break
                    status = "ok"

                time.sleep(1.0)
            else:
                raise RuntimeError("Ollama request failed")
        except Exception as e:
            print(f"[JARVIS] Ollama engine unreachable or returned invalid JSON: {e}")
            response_text = (
                f"Ollama engine is offline or returned an invalid response. "
                f"Please ensure '{OLLAMA_MODEL}' is running at {OLLAMA_ENDPOINT}. "
                f"(Error: {type(e).__name__})"
            )
            intent = "GENERAL_QUERY"
            steps = []
            action = "none"
            status = "error"
            break

    if status == "pending":
        status = "ok"

    # 3. Log to DB
    try:
        log_entry = database.AssistantLog(
            user_input=user_msg,
            detected_intent=intent,
            ai_response=response_text,
            status=status
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"Failed to write log to DB: {e}")

    # Format execution_type and payload for legacy UI components
    legacy_execution_type = "GUI_SEQUENCE" if steps else None
    legacy_payload = " | ".join([f"{s.get('type')}: {s.get('payload')}" for s in steps]) if steps else None

    return models.ChatResponse(
        response=response_text,
        intent=intent,
        action=action,
        execution_type=legacy_execution_type,
        payload=legacy_payload,
        steps=steps if steps else None
    )

@app.get("/api/system/metrics")
def get_system_metrics():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        return {"cpu": cpu, "ram": ram}
    except Exception as e:
        print(f"Failed to fetch system metrics: {e}")
        import random
        return {"cpu": round(random.uniform(5.0, 25.0), 1), "ram": round(random.uniform(40.0, 60.0), 1)}

@app.get("/api/system/voice/status")
def get_voice_status():
    return {"active": is_recording_voice}

@app.get("/api/system/files")
def get_workspace_files(
    db: Session = Depends(database.get_db),
    current_user: database.User = Depends(get_current_user)
):
    return list_workspace_files()

@app.get("/api/system/logs")
def get_system_logs(
    db: Session = Depends(database.get_db),
    current_user: database.User = Depends(get_current_user)
):
    try:
        db_logs = db.query(database.AssistantLog).order_by(database.AssistantLog.id.desc()).limit(10).all()
        result = []
        for log in reversed(db_logs):
            result.append({
                "id": log.id,
                "user_input": log.user_input,
                "detected_intent": log.detected_intent,
                "ai_response": log.ai_response,
                "status": log.status,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None
            })
        return result
    except Exception as e:
        print(f"Failed to fetch system logs: {e}")
        return []

if __name__ == "__main__":
    import uvicorn
    parsed_backend = urlparse(BACKEND_URL)
    uvicorn.run(app, host=parsed_backend.hostname or "127.0.0.1", port=int(parsed_backend.port or 8000))


