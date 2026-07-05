from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

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

@app.on_event("startup")
def on_startup():
    # Attempt to initialize DB tables if they don't exist
    database.init_db()

@app.get("/")
def read_root():
    return {"message": "Jarvis Backend is running!"}

def simple_nlp_intent_matcher(user_input: str):
    """
    A basic intent matching function.
    In a fully fleshed out AI model, this would be an LLM call or a trained intent classifier.
    """
    ui = user_input.lower()
    if "open" in ui or "launch" in ui or "start" in ui:
        return "launch_app"
    elif "screenshot" in ui or "capture" in ui:
        return "take_screenshot"
    elif "volume up" in ui or "increase volume" in ui:
        return "volume_up"
    elif "volume down" in ui or "decrease volume" in ui:
        return "volume_down"
    elif "mute" in ui:
        return "volume_mute"
    elif "play" in ui or "pause" in ui:
        return "play_pause"
    else:
        return "unknown"

def extract_app_alias(user_input: str) -> str:
    """Extracts the potential app name from the launch command."""
    ui = user_input.lower()
    for verb in ["open", "launch", "start"]:
        if verb in ui:
            # simple logic: get the word after the verb
            parts = ui.split(verb)
            if len(parts) > 1:
                return parts[1].strip()
    return ""

@app.post("/api/execute", response_model=models.ExecuteResponse)
def execute_command(req: models.ExecuteRequest, db: Session = Depends(database.get_db)):
    user_input = req.user_input
    
    # 1. Determine intent
    intent = simple_nlp_intent_matcher(user_input)
    
    response_msg = ""
    status = "pending"
    
    # 2. Execute Action based on Intent
    if intent == "launch_app":
        app_alias = extract_app_alias(user_input)
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
                
    elif intent == "take_screenshot":
        result = os_tools.take_screenshot()
        status = result["status"]
        response_msg = result["message"]
        
    elif intent in ["volume_up", "volume_down", "volume_mute", "play_pause"]:
        result = os_tools.adjust_media_controls(intent)
        status = result["status"]
        response_msg = result["message"]
        
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
        # If DB is not set up correctly, we still return the execution result, but maybe log a warning
        print(f"Failed to save log to DB: {e}")

    return models.ExecuteResponse(
        status=status,
        message=response_msg,
        intent=intent
    )
