import os
from sqlalchemy.orm import Session
from typing import Optional, List, Any
from app.database.create_database import User, Patient, WSI, Setting, Report, ROI, hash_password


# =========================================================
# 1. SYSTEM STATUS & USER MANAGEMENT
# =========================================================

def has_any_user(db: Session) -> bool:
    """Checks if any user exists (used for first-run setup)."""
    return db.query(User).first() is not None


def create_user(
    db: Session,
    name: str,
    username: str,
    password: str,
    role: str,
    professional_id: Optional[str] = None
) -> User:
    """Creates a new user with secure hashed password."""
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


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Fetch user by unique username."""
    return db.query(User).filter(User.username == username).first()


def get_all_users(db: Session) -> List[User]:
    """Admin use: list all pathologists."""
    return db.query(User).all()


# =========================================================
# 2. PATIENT & WSI MANAGEMENT
# =========================================================

def create_patient(db: Session, name: str, case_id: str) -> Optional[Patient]:
    """Create patient if case_id not already used."""
    existing = db.query(Patient).filter(Patient.case_id == case_id).first()
    if existing:
        return None

    new_patient = Patient(name=name, case_id=case_id)
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    return new_patient


def get_all_patients(db: Session) -> List[Patient]:
    """Dashboard case list."""
    return db.query(Patient).all()


def add_wsi_to_patient(db: Session, patient_id: int, file_path: str) -> WSI:
    """Attach WSI file to patient."""
    new_wsi = WSI(patient_id=patient_id, file_path=file_path)
    db.add(new_wsi)
    db.commit()
    db.refresh(new_wsi)
    return new_wsi


def get_latest_wsi_for_patient(db: Session, patient_id: int) -> Optional[WSI]:
    """Get latest uploaded WSI by patient ID."""
    return db.query(WSI).filter(WSI.patient_id == patient_id).order_by(WSI.id.desc()).first()


def get_or_create_report_for_wsi(db: Session, wsi_id: int, user_id: Optional[int] = None) -> Report:
    """Ensure a report row exists for a given WSI."""
    report = db.query(Report).filter(Report.wsi_id == wsi_id).order_by(Report.created_at.desc()).first()
    if report:
        return report

    report = Report(wsi_id=wsi_id, user_id=user_id)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_rois_for_report(db: Session, report_id: int) -> List[ROI]:
    """List ROIs for a report."""
    return db.query(ROI).filter(ROI.report_id == report_id).order_by(ROI.id.asc()).all()


def create_roi(db: Session, report_id: int, coordinates: Any) -> ROI:
    """Create ROI record."""
    roi = ROI(report_id=report_id, coordinates=coordinates)
    db.add(roi)
    db.commit()
    db.refresh(roi)
    return roi


def delete_roi(db: Session, roi_id: int, report_id: Optional[int] = None) -> bool:
    """Delete ROI by ID; optionally constrain by report ID."""
    query = db.query(ROI).filter(ROI.id == roi_id)
    if report_id is not None:
        query = query.filter(ROI.report_id == report_id)

    roi = query.first()
    if roi is None:
        return False

    db.delete(roi)
    db.commit()
    return True


# =========================================================
# 3. STORAGE AUTOMATION
# =========================================================

def get_automated_path() -> str:
    """
    Default storage location:
    ~/Documents/DigitalPathology/WSI_Storage
    """
    home = os.path.expanduser("~")

    base_folder = os.path.join(
        home,
        "Documents",
        "DigitalPathology",
        "WSI_Storage"
    ).replace("\\", "/")

    os.makedirs(base_folder, exist_ok=True)
    return base_folder


def get_effective_path(db: Session) -> str:
    """
    Returns active storage path.
    If DB has no setting -> fallback to automated path.
    """
    settings = get_settings(db)

    if settings is None:
        return get_automated_path()

    path_value = getattr(settings, "wsi_storage_path", None)

    if isinstance(path_value, str) and path_value.strip():
        return path_value

    return get_automated_path()

# =========================================================
# 4. GLOBAL SETTINGS MANAGEMENT (TYPE-SAFE)
# =========================================================

def get_settings(db: Session) -> Optional[Setting]:
    """Retrieve global system configuration row."""
    return db.query(Setting).first()


def create_default_settings(db: Session) -> Setting:
    """Create default settings if not exists."""
    settings = Setting()

    # SAFE assignment using setattr (SQLAlchemy typing safe)
    setattr(settings, "wsi_storage_path", get_automated_path())
    setattr(settings, "ai_threshold", 0.5)
    setattr(settings, "hospital_name", "")
    setattr(settings, "show_magnification", True)
    setattr(settings, "show_scan_date", True)

    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def get_or_create_settings(db: Session) -> Setting:
    """Ensure settings row always exists."""
    settings = get_settings(db)

    if settings is None:
        settings = create_default_settings(db)

    return settings


def update_storage_path(db: Session, path: str) -> Setting:
    """Update WSI storage path safely."""
    settings = get_or_create_settings(db)

    safe_path = str(path).strip()

    # SAFE assignment
    setattr(settings, "wsi_storage_path", safe_path)

    db.commit()
    db.refresh(settings)
    return settings


# =========================================================
# GENERIC FIELD UPDATE (TYPE SAFE)
# =========================================================

def update_setting_field(db: Session, field: str, value) -> Setting:
    """
    Generic safe update for any Setting column.
    """
    settings = get_or_create_settings(db)

    if not hasattr(settings, field):
        raise AttributeError(f"Setting has no attribute '{field}'")

    setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return settings
