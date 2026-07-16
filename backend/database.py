import urllib.parse  # Safely encodes special characters like '@'
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# All configuration is imported from the central config module.
# config.py owns .env loading — do NOT call load_dotenv() or os.getenv() here.
import config as cfg

# ==========================================
# DATABASE CONNECTION SETUP
# ==========================================

# URL-encode the password so special characters like '@' become safe tokens (%40)
encoded_password = urllib.parse.quote_plus(cfg.DB_PASSWORD)

# Assemble the secure connection string using named constants from config
DATABASE_URL = (
    f"mysql+pymysql://{cfg.DB_USER}:{encoded_password}"
    f"@{cfg.DB_HOST}:{cfg.DB_PORT}/{cfg.DB_NAME}"
)

# Create the engine and database session factory
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
        # Connect without DB name to run CREATE DATABASE DDL if necessary
        temp_url = (
            f"mysql+pymysql://{cfg.DB_USER}:{encoded_password}"
            f"@{cfg.DB_HOST}:{cfg.DB_PORT}"
        )
        temp_engine = create_engine(temp_url, isolation_level="AUTOCOMMIT")
        with temp_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {cfg.DB_NAME}"))
        temp_engine.dispose()
    except Exception as e:
        print(f"Warning: Auto-creation of database '{cfg.DB_NAME}' failed: {e}")

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