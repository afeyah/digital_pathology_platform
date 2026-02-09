from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, JSON, Enum
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import enum
import bcrypt

# 1. Setup
DATABASE_URL = "sqlite:///cancer_detection.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define the Role Enum for type safety
class UserRole(enum.Enum):
    ADMIN = "admin"
    PATHOLOGIST = "pathologist"

# 2. Define Entities

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    
    # User type Column
    role = Column(Enum(UserRole), nullable=False)
    
    # Store Pathologist ID (could be null for admins)
    professional_id = Column(String, unique=True, nullable=True) 

    # Relationship: A user (specifically a pathologist) generates reports
    reports = relationship("Report", back_populates="user")

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    
    wsis = relationship("WSI", back_populates="patient", cascade="all, delete-orphan")

class WSI(Base):
    __tablename__ = "wsis"
    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    
    patient = relationship("Patient", back_populates="wsis")
    reports = relationship("Report", back_populates="wsi", cascade="all, delete-orphan")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    
    wsi_id = Column(Integer, ForeignKey("wsis.id"))
    
    # Linked to the generic User table
    user_id = Column(Integer, ForeignKey("users.id"))
    
    wsi = relationship("WSI", back_populates="reports")
    user = relationship("User", back_populates="reports")
    rois = relationship("ROI", back_populates="report", cascade="all, delete-orphan")
    heatmaps = relationship("Heatmap", back_populates="report", cascade="all, delete-orphan")

class ROI(Base):
    __tablename__ = "rois"
    id = Column(Integer, primary_key=True, index=True)
    coordinates = Column(JSON, nullable=False)
    report_id = Column(Integer, ForeignKey("reports.id"))
    
    report = relationship("Report", back_populates="rois")

class Heatmap(Base):
    __tablename__ = "heatmaps"
    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String, nullable=False)
    report_id = Column(Integer, ForeignKey("reports.id"))
    
    report = relationship("Report", back_populates="heatmaps")

# 3. Initialization
def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database initialized with Unified User Table!")

# 4. Helper to Create Users
def create_initial_users():
    db = SessionLocal()
    
    if not db.query(User).filter_by(username="admin").first():
        # hash password
        secure_pw = hash_password("admin") 
        
        admin = User(
            name="Super Admin",
            username="admin",
            password=secure_pw,  # Store encrypted password
            role=UserRole.ADMIN
        )
        db.add(admin)
        print("Admin created with hashed password.")
        
    db.commit()
    db.close()


def hash_password(plain_password: str) -> str:
    """Takes a plain password and returns a hashed string to store in DB."""
    # 1. Convert string to bytes
    password_bytes = plain_password.encode('utf-8') 
    # 2. Generate salt and hash
    hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    # 3. Decode back to string so it can be stored in SQLite
    return hashed_bytes.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Checks if the plain password matches the stored hash."""
    # 1. Convert plain password to bytes
    password_bytes = plain_password.encode('utf-8')
    # 2. Convert stored hash string back to bytes
    hashed_bytes = hashed_password.encode('utf-8')
    # 3. Check if they match
    return bcrypt.checkpw(password_bytes, hashed_bytes)

if __name__ == "__main__":
    init_db()
    create_initial_users()