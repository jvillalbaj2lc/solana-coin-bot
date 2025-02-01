# app/database/base.py
import os
import logging
from pathlib import Path
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# Declarative Base
Base = declarative_base()

def get_database_path() -> Path:
    """Get the database file path, creating directories if needed."""
    # Use data directory in project root
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir / "dexscreener.db"

def get_database_url() -> str:
    """
    Build the database URL string for SQLAlchemy.
    Uses SQLite database in the data directory.
    """
    db_path = get_database_path()
    return f"sqlite:///{db_path}"

# Create Engine with proper configuration
DATABASE_URL = get_database_url()
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # Needed for SQLite
        "timeout": 30  # Wait up to 30 seconds for locks
    } if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,  # Enable automatic reconnection
    pool_recycle=3600,   # Recycle connections every hour
    echo=False          # Set to True for SQL logging
)

# Session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_db_exists() -> bool:
    """Check if the database exists and has the required tables."""
    db_path = get_database_path()
    if not db_path.exists():
        return False
    
    try:
        inspector = inspect(engine)
        # Check if our main table exists
        return "token_snapshots" in inspector.get_table_names()
    except SQLAlchemyError as e:
        logger.error(f"Error checking database: {e}")
        return False

def init_db(force: bool = False) -> None:
    """
    Initialize the database, creating tables if they don't exist.
    
    :param force: If True, drop and recreate all tables
    :raises: SQLAlchemyError if database initialization fails
    """
    try:
        if force:
            logger.warning("Forcing database reinitialization...")
            Base.metadata.drop_all(bind=engine)
        
        if force or not check_db_exists():
            logger.info("Creating database tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialization complete.")
        else:
            logger.info("Database already initialized.")
            
    except SQLAlchemyError as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def get_db():
    """
    Get a database session.
    Use this as a context manager:
    
    with get_db() as db:
        db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
