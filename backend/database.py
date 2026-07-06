import os
import urllib.parse  # Safely encodes special characters like '@'
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from dotenv import load_dotenv

# Search and load environment variables from CWD, backend folder, or project root
load_dotenv()
local_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(local_env):
    load_dotenv(local_env, override=True)
parent_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(parent_env):
    load_dotenv(parent_env, override=True)

# 1. Fetch values from your .env file
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")  # This contains your password with the '@'
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "jarvis_db")

# 2. URL-encode the password dynamically so characters like '@' turn into safe string tokens (like %40)
encoded_password = urllib.parse.quote_plus(DB_PASSWORD)

# 3. Assemble the secure connection string using the encoded password token
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 4. Create the engine and database session factory (fixed variable name mismatch)
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ==========================================
# SQLALCHEMY ORM DATA SCHEMAS
# ==========================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    google_id = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    picture_url = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AssistantLog(Base):
    __tablename__ = "assistant_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_input = Column(Text, nullable=False)
    detected_intent = Column(String(255), nullable=False)
    ai_response = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class AppMapping(Base):
    __tablename__ = "app_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    alias_name = Column(String(255), unique=True, index=True, nullable=False)
    system_path = Column(String(1024), nullable=False)

# ==========================================
# REPOSITORY UTILITIES & INITIALIZERS
# ==========================================

def init_db():
    try:
        # Automatically generates the database tables on engine connection handshake
        Base.metadata.create_all(bind=engine)
        print("Database tables initialized successfully.")
    except Exception as e:
        print(f"Error initializing DB: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()