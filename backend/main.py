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

@app.on_event("startup")
def on_startup():
    # Attempt to initialize DB tables if they don't exist
    database.init_db()

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

