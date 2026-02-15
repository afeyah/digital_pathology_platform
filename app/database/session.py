# File: app/database/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Using SQLite for development
SQLALCHEMY_DATABASE_URL = "sqlite:///./digital_pathology.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# This is what your pages are trying to import!
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()