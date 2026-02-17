# File: app/database/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Enum
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    ADMIN = "admin"
    PATHOLOGIST = "pathologist"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    professional_id = Column(String, unique=True, nullable=True) 
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