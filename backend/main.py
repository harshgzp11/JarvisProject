from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import ollama
import json
from pydantic import ValidationError

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
def execute_command(req: models.ExecuteRequest, db: Session = Depends(database.get_db)):
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
