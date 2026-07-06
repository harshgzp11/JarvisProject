from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import ollama
import json
from pydantic import ValidationError
from passlib.context import CryptContext
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
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.post("/api/auth/signup", response_model=models.AuthResponse)
def signup(req: models.UserCreate, db: Session = Depends(database.get_db)):
    existing_user = db.query(database.User).filter(database.User.email == req.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pw = get_password_hash(req.password)
    new_user = database.User(email=req.email, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return models.AuthResponse(status="success", message="User created successfully")

@app.post("/api/auth/login", response_model=models.AuthResponse)
def login(req: models.UserLogin, db: Session = Depends(database.get_db)):
    user = db.query(database.User).filter(database.User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_access_token(data={"sub": user.email})
    return models.AuthResponse(status="success", message="Login successful", token=access_token)

@app.on_event("startup")
def on_startup():
    # Attempt to initialize DB tables if they don't exist
    database.init_db()

@app.get("/")
def read_root():
    return {"message": "Jarvis Backend is running!"}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.post("/api/auth/signup", response_model=models.AuthResponse)
def signup(req: models.UserCreate, db: Session = Depends(database.get_db)):
    # Duplicate email check
    existing_user = db.query(database.User).filter(database.User.email == req.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email is already registered.")
    
    hashed_pwd = get_password_hash(req.password)
    new_user = database.User(email=req.email, hashed_password=hashed_pwd)
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database registration failure: {str(e)}")
        
    token = create_access_token(data={"sub": req.email})
    return models.AuthResponse(status="success", message="User registered successfully.", token=token)

@app.post("/api/auth/login", response_model=models.AuthResponse)
def login(req: models.UserLogin, db: Session = Depends(database.get_db)):
    user = db.query(database.User).filter(database.User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
        
    token = create_access_token(data={"sub": req.email})
    return models.AuthResponse(status="success", message="Login successful.", token=token)

@app.get("/api/auth/verify")
def verify_token(token: Optional[str] = None, db: Session = Depends(database.get_db)):
    if not token:
        raise HTTPException(status_code=400, detail="Token parameter is required.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
