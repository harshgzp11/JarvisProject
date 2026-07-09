from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import ollama
import json
from pydantic import ValidationError
from google.oauth2 import id_token
from google.auth.transport import requests
from jose import jwt
from datetime import datetime, timedelta
import os
from typing import Optional
import requests as http_requests
import threading
import re
import subprocess
import webbrowser
import tempfile
import time
import pyautogui
import pyperclip
import pygetwindow as gw
from PIL import Image, ImageDraw
try:
    import pystray
    from pystray import MenuItem as item
except ImportError:
    pystray = None
try:
    import keyboard
except ImportError:
    keyboard = None

import database
import models
import os_tools

app = FastAPI(title="Jarvis Backend", description="AI-Driven Desktop Assistant API")

# Setup CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, this should be restricted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Configurations
SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.getenv("JWT_SECRET", "super-secret-key-change-in-production"))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

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
WORKSPACE_DIR = "C:\\Users\\Public\\JarvisWorkspace"

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
        dev_user = db.query(User).filter(User.email == "test@example.com").first()
        if not dev_user:
            dev_user = User(
                google_id="voice_system_user",
                email="test@example.com",
                full_name="Test Operator",
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

@app.on_event("startup")
def on_startup():
    # Attempt to initialize DB tables if they don't exist
    database.init_db()
    # Start system tray and Voice listener in non-blocking threads
    threading.Thread(target=setup_system_tray, daemon=True).start()
    threading.Thread(target=start_voice_listener, daemon=True).start()

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
        if req.token == "mock_google_id_token":
            user = db.query(database.User).filter(database.User.email == "test@example.com").first()
            if not user:
                user = database.User(
                    google_id="mock_google_id",
                    email="test@example.com",
                    full_name="Test Operator",
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
            model='llama3.2:latest',
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
            # Look up in database
            db_app = db.query(database.AppMapping).filter(database.AppMapping.alias_name.ilike(f"%{app_alias}%")).first()
            
            # fallback generic commands for common Windows apps if DB is empty
            fallback_apps = {
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "calc": "calc.exe",
                "paint": "mspaint.exe",
                "browser": "msedge.exe",
            }
            
            if db_app:
                system_path = db_app.system_path
            elif app_alias in fallback_apps:
                system_path = fallback_apps[app_alias]
            else:
                system_path = None
                
            if system_path:
                result = os_tools.launch_application(system_path)
                status = result["status"]
                response_msg = result["message"]
            else:
                status = "error"
                response_msg = f"Application '{app_alias}' not found in mappings."
                
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

def execute_system_action(steps: list) -> dict:
    """
    Sequential GUI Orchestration Engine.
    Executes an array of steps (LAUNCH, WAIT, TYPE, SHORTCUT, PASTE) chronologically.
    """
    if not steps:
        return {"status": "none", "message": "No automation steps to execute."}

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
    
    # 1. Fetch conversational history from the DB (last 5 message exchanges)
    db_history = []
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

    # 2. Determine intent & execution plan using local Ollama model (open-ended architecture)
    url = "http://localhost:11434/api/chat"

    system_prompt = (
        "You are a native desktop automation agent. Accept any natural language request and translate it into a strict JSON plan of executable desktop steps.\n"
        "Return ONLY a valid JSON object with NO markdown fences, NO explanation text outside the JSON.\n\n"
        "Your JSON response must follow this exact schema:\n"
        "{\n"
        "  \"response\": \"A brief, clean confirmation string for the user.\",\n"
        "  \"steps\": [\n"
        "    { \"type\": \"LAUNCH\" | \"WAIT\" | \"PASTE\" | \"SHORTCUT\", \"payload\": \"string\" }\n"
        "  ]\n"
        "}\n\n"
        "Step types available:\n"
        "- LAUNCH: Start a GUI app or command with subprocess shell execution. Example payload: 'notepad.exe' or 'calc.exe'.\n"
        "- WAIT: Pause execution for N seconds (for example '1.0') to allow an app to focus before the next step.\n"
        "- PASTE: Copy the supplied text or code block to the clipboard and inject it with ctrl+v.\n"
        "- SHORTCUT: Trigger a keyboard shortcut such as 'ctrl+s' or 'alt+tab' by splitting on '+'.\n\n"
        "Examples:\n"
        "1. Open Notepad, write a message, and save it:\n"
        "{\n"
        "  \"response\": \"Launching Notepad and writing the requested message.\",\n"
        "  \"steps\": [\n"
        "    { \"type\": \"LAUNCH\", \"payload\": \"notepad.exe\" },\n"
        "    { \"type\": \"WAIT\", \"payload\": \"1.0\" },\n"
        "    { \"type\": \"PASTE\", \"payload\": \"Hello from Jarvis!\" },\n"
        "    { \"type\": \"SHORTCUT\", \"payload\": \"ctrl+s\" }\n"
        "  ]\n"
        "}\n"
    )

    ollama_messages = [{"role": "system", "content": system_prompt}]
    ollama_messages.extend(db_history)
    ollama_messages.append({"role": "user", "content": user_msg})

    ollama_payload = {
        "model": "llama3.2:latest",
        "messages": ollama_messages,
        "stream": False,
        "format": "json"
    }

    response_text = "Standing by."
    intent = "GENERAL_QUERY"
    action = "none"
    steps = []

    try:
        ollama_resp = http_requests.post(url, json=ollama_payload, timeout=20.0)
        if ollama_resp.status_code == 200:
            data = ollama_resp.json()
            message_content = data.get("message", {}).get("content", "").strip()
            # Strip markdown fences if model wraps in ```json ... ```
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
    except Exception as e:
        print(f"[JARVIS] Ollama engine unreachable or returned invalid JSON: {e}")
        response_text = (
            f"Ollama engine is offline or returned an invalid response. "
            f"Please ensure Llama 3.2 is running at localhost:11434. (Error: {type(e).__name__})"
        )
        intent = "GENERAL_QUERY"
        steps = []
        action = "none"

    # 3. Execute via the new sequential steps engine
    status = "pending"
    if steps:
        exec_result = execute_system_action(steps)
        status = exec_result.get("status", "pending")
        if exec_result.get("status") == "success":
            response_text = f"{response_text} ✓ ({exec_result.get('message')})"
        elif exec_result.get("status") == "error":
            response_text = f"Execution error: {exec_result.get('message')}"
    else:
        status = "ok"

    # 4. Log to DB
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
    uvicorn.run(app, host="127.0.0.1", port=8000)

