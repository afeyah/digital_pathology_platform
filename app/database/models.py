from __future__ import annotations

from datetime import datetime
import enum
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(enum.Enum):
    ADMIN = "admin"
    PATHOLOGIST = "pathologist"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    professional_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    reports: Mapped[list["Report"]] = relationship(back_populates="user")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    wsis: Mapped[list["WSI"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class WSI(Base):
    __tablename__ = "wsis"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)

    patient: Mapped["Patient"] = relationship(back_populates="wsis")
    reports: Mapped[list["Report"]] = relationship(back_populates="wsi", cascade="all, delete-orphan")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    wsi_id: Mapped[int] = mapped_column(ForeignKey("wsis.id"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")

    wsi: Mapped["WSI"] = relationship(back_populates="reports")
    user: Mapped["User | None"] = relationship(back_populates="reports")
    rois: Mapped[list["ROI"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class ROI(Base):
    __tablename__ = "rois"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), nullable=False, index=True)
    coordinates: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    report: Mapped["Report"] = relationship(back_populates="rois")
