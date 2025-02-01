# app/database/base.py
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Declarative Base
Base = declarative_base()

def get_database_url() -> str:
    """
    Build or retrieve the database URL string for SQLAlchemy.
    If you want to support multiple environments or pass a DB URL
    from config or environment variables, handle that here.

    By default, we’re using a local SQLite file named 'dexscreener_data.db'.
    """
    # Option 1: Hard-code or read from environment variables
    # Example:
    #   db_url = os.getenv("DATABASE_URL", "sqlite:///dexscreener_data.db")

    # Option 2: Build from config, if you prefer
    #   from app.config.loader import load_config
    #   config = load_config()
    #   db_url = config.get("database", {}).get("url", "sqlite:///dexscreener_data.db")

    # For now, let's keep it simple:
    db_url = "sqlite:///dexscreener_data.db"
    return db_url

# Create Engine
DATABASE_URL = get_database_url()
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False  # Set to True for verbose SQL logging
)

# Session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Initialize the database. Call this once (e.g., at app startup)
    to ensure tables are created if they don't exist.
    """
    logger.info("Creating all database tables if not already existing...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization complete.")
