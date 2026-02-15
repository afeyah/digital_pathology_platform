# File: app/database/create_database.py
# Install required dependencies: pip install sqlalchemy bcrypt
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, JSON, Enum
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import enum

try:
    import bcrypt
except ImportError:
    raise ImportError("bcrypt is required. Install it with: pip install bcrypt")

# --- Configuration ---
# The database file will be created in your root folder
DATABASE_URL = "sqlite:///cancer_detection.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Enumerations for Type Safety ---
class UserRole(enum.Enum):
    """Defines the two types of users in the Path-Benchmark platform."""
    ADMIN = "admin"
    PATHOLOGIST = "pathologist"

# --- Database Models ---

class User(Base):
    """Stores authentication and profile details for Admin and Pathologists."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False) # Stores the hashed bcrypt string
    
    role = Column(Enum(UserRole), nullable=False)
    professional_id = Column(String, unique=True, nullable=True) 

    # Relationship: A pathologist can be linked to multiple reports
    reports = relationship("Report", back_populates="user")

class Patient(Base):
    """Represents a medical case for a specific patient."""
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, nullable=False) # e.g., 'Case-001'
    name = Column(String, nullable=False)
    
    # Cascade ensures that deleting a patient removes their associated slides
    wsis = relationship("WSI", back_populates="patient", cascade="all, delete-orphan")

class WSI(Base):
    """Stores the file path to the large .svs Whole Slide Images."""
    __tablename__ = "wsis"
    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, nullable=False) # Task 5: Link to local directory
    patient_id = Column(Integer, ForeignKey("patients.id"))
    
    patient = relationship("Patient", back_populates="wsis")
    reports = relationship("Report", back_populates="wsi", cascade="all, delete-orphan")

class Report(Base):
    """The result of an AI analysis session on a specific slide."""
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    
    wsi_id = Column(Integer, ForeignKey("wsis.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    
    wsi = relationship("WSI", back_populates="reports")
    user = relationship("User", back_populates="reports")
    rois = relationship("ROI", back_populates="report", cascade="all, delete-orphan")
    heatmaps = relationship("Heatmap", back_populates="report", cascade="all, delete-orphan")

class ROI(Base):
    """Stores coordinates for boxes drawn on the slide (Region of Interest)."""
    __tablename__ = "rois"
    id = Column(Integer, primary_key=True, index=True)
    coordinates = Column(JSON, nullable=False) # Stores x, y, width, height as JSON
    report_id = Column(Integer, ForeignKey("reports.id"))
    
    report = relationship("Report", back_populates="rois")

class Heatmap(Base):
    """Links to the AI-generated overlay images."""
    __tablename__ = "heatmaps"
    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String, nullable=False)
    report_id = Column(Integer, ForeignKey("reports.id"))
    
    report = relationship("Report", back_populates="heatmaps")

# --- Database Utilities ---

def init_db():
    """Creates the database and all tables based on the models above."""
    Base.metadata.create_all(bind=engine)
    print("Database structure initialized successfully!")

def hash_password(plain_password: str) -> str:
    """Uses bcrypt to securely hash passwords before database storage."""
    password_bytes = plain_password.encode('utf-8') 
    hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_bytes.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a user's login attempt against the stored hash."""
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def create_initial_users():
    """Seeds the database with a default Admin account for testing."""
    db = SessionLocal()
    if not db.query(User).filter_by(username="admin").first():
        admin = User(
            name="Super Admin",
            username="admin",
            password=hash_password("admin"), 
            role=UserRole.ADMIN
        )
        db.add(admin)
        db.commit()
        print("Default admin created (Username: admin / Password: admin)")
    db.close()

if __name__ == "__main__":
    # Run this file directly to reset/create your database locally
    init_db()
    create_initial_users()