# File: app/database/crud.py
from sqlalchemy.orm import Session
# FIX: Use underscore instead of hyphen and absolute path for reliability
from app.database.create_database import User, Patient, WSI, Report, ROI, Heatmap, hash_password
from datetime import datetime

# ------------------------------------------
# 1. USER MANAGEMENT (Admin & Pathologist)
# ------------------------------------------

def create_user(db: Session, name: str, username: str, password: str, role, professional_id: str = None):
    """Creates a new user with a hashed password for the pathology platform."""
    # Hash the password before saving to the database
    hashed_pw = hash_password(password)
    
    new_user = User(
        name=name,
        username=username,
        password=hashed_pw,
        role=role,
        professional_id=professional_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def get_user_by_username(db: Session, username: str):
    """Finds a specific user by their username (primary login method)."""
    return db.query(User).filter(User.username == username).first()

def get_all_users(db: Session):
    """Returns a comprehensive list of all registered users."""
    return db.query(User).all()

def delete_user(db: Session, user_id: int):
    """Removes a user from the system by their primary ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
        return True
    return False

# ------------------------------------------
# 2. PATIENT & WSI MANAGEMENT
# ------------------------------------------

def create_patient(db: Session, name: str, case_id: str):
    """Adds a new patient clinical case to the dashboard."""
    # Check if case_id already exists to prevent duplicate entries
    existing = db.query(Patient).filter(Patient.case_id == case_id).first()
    if existing:
        return None 
        
    new_patient = Patient(name=name, case_id=case_id)
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    return new_patient

def get_all_patients(db: Session):
    """Retrieves all patient records for the main management dashboard."""
    return db.query(Patient).all()

def add_wsi_to_patient(db: Session, patient_id: int, file_path: str):
    """Links a Whole Slide Image (WSI) file path to a specific patient case."""
    new_wsi = WSI(patient_id=patient_id, file_path=file_path)
    db.add(new_wsi)
    db.commit()
    db.refresh(new_wsi)
    return new_wsi

def delete_patient(db: Session, patient_id: int):
    """Deletes a patient and triggers cascade deletion of slides and reports."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient:
        db.delete(patient)
        db.commit()
        return True
    return False

# ------------------------------------------
# 3. REPORT & ANALYSIS LOGIC
# ------------------------------------------

def create_report(db: Session, user_id: int, wsi_id: int):
    """Initializes a new analysis report for a pathology slide."""
    new_report = Report(
        user_id=user_id,
        wsi_id=wsi_id,
        created_at=datetime.now()
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report

def save_roi(db: Session, report_id: int, coordinates: dict):
    """Saves a Region of Interest (ROI) box coordinates to a specific report."""
    new_roi = ROI(
        report_id=report_id,
        coordinates=coordinates 
    )
    db.add(new_roi)
    db.commit()
    return new_roi

def save_heatmap(db: Session, report_id: int, image_path: str):
    """Stores the file path of a generated AI heatmap for an analysis."""
    new_heatmap = Heatmap(
        report_id=report_id,
        image_path=image_path
    )
    db.add(new_heatmap)
    db.commit()
    return new_heatmap

def get_report_details(db: Session, report_id: int):
    """Retrieves full report details including all associated ROIs."""
    return db.query(Report).filter(Report.id == report_id).first()