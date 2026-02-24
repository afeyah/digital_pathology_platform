# File: app/pages/settings_page.py

from nicegui import ui, app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from typing import Optional

from app.database.create_database import SessionLocal, hash_password, User, Setting
from app.database import crud

# FIX import path sesuai project kamu
from app.components.base_layout import base_page_layout   # â† sesuaikan nama file layout kamu


APP_VERSION = "1.0.0"


# =========================================================
# HELPERS
# =========================================================

def get_current_user(db) -> Optional[User]:
    username = app.storage.user.get('username')
    if not username:
        return None
    return crud.get_user_by_username(db, username)


def get_or_create_settings(db) -> Setting:
    return crud.get_or_create_settings(db)


def safe_str(value) -> str:
    """Convert SQLAlchemy column or None â†’ str safely"""
    if isinstance(value, str):
        return value
    return ""


def safe_bool(value) -> bool:
    return bool(value) if isinstance(value, bool) else False


# =========================================================
# PAGE
# =========================================================

@ui.page('/settings')
def settings_page():

    with base_page_layout("Settings"):

        # -------------------------------------------------
        # SESSION + USER LOAD
        # -------------------------------------------------
        with SessionLocal() as db:

            current_user = get_current_user(db)

            if current_user is None:
                ui.notify("Session expired. Please login again.", type='negative')
                ui.navigate.to('/login')
                return

            settings = get_or_create_settings(db)
            is_admin = safe_str(getattr(current_user, "role", "")) == "ADMIN"

        # -------------------------------------------------
        # TABS
        # -------------------------------------------------
        tabs = ui.tabs().classes('w-full')
        tab_profile = ui.tab('Profile')
        tab_ai = ui.tab('AI Model')
        tab_branding = ui.tab('Branding')
        tab_metadata = ui.tab('Metadata')
        tab_system = ui.tab('System Status')

        tab_admin = None
        if is_admin:
            tab_admin = ui.tab('User Management')

        # -------------------------------------------------
        # PANELS
        # -------------------------------------------------
        with ui.tab_panels(tabs, value=tab_profile).classes('w-full bg-white shadow rounded p-6'):

            # =================================================
            # PROFILE
            # =================================================
            with ui.tab_panel(tab_profile):

                name_input = ui.input(
                    "Full Name",
                    value=safe_str(getattr(current_user, "name", ""))
                ).classes('w-96')

                prof_id_input = ui.input(
                    "Pathologist ID",
                    value=safe_str(getattr(current_user, "professional_id", ""))
                ).classes('w-96')

                def save_profile():
                    with SessionLocal() as db:
                        user = get_current_user(db)
                        if user:
                            setattr(user, "name", name_input.value.strip())
                            setattr(user, "professional_id", prof_id_input.value.strip())
                            db.commit()
                            ui.notify("Profile updated", type='positive')

                ui.button("Save Profile", on_click=save_profile, color='primary')

                ui.separator()

                current_pw = ui.input("Current Password", password=True).classes('w-96')
                new_pw = ui.input("New Password", password=True).classes('w-96')
                confirm_pw = ui.input("Confirm Password", password=True).classes('w-96')

                def change_password():
                    if new_pw.value != confirm_pw.value:
                        ui.notify("Password mismatch", type='negative')
                        return

                    with SessionLocal() as db:
                        user = get_current_user(db)
                        if user:
                            setattr(user, "password", hash_password(new_pw.value))
                            db.commit()

                    ui.notify("Password updated", type='positive')

                ui.button("Update Password", on_click=change_password, color='primary')

            # =================================================
            # AI THRESHOLD
            # =================================================
            with ui.tab_panel(tab_ai):

                threshold_value = getattr(settings, "ai_threshold", 0.5)
                if not isinstance(threshold_value, float):
                    threshold_value = 0.5

                slider = ui.slider(min=0.0, max=1.0, step=0.01, value=threshold_value).classes('w-96')
                label = ui.label(f"{threshold_value:.2f}")

                slider.on_value_change(lambda e: label.set_text(f"{e.value:.2f}"))

                def save_threshold():
                    with SessionLocal() as db:
                        s = get_or_create_settings(db)
                        setattr(s, "ai_threshold", float(slider.value))
                        db.commit()
                        ui.notify("AI threshold saved", type='positive')

                ui.button("Save", on_click=save_threshold)

            # =================================================
            # BRANDING
            # =================================================
            with ui.tab_panel(tab_branding):

                hospital_input = ui.input(
                    "Hospital / Clinic Name",
                    value=safe_str(getattr(settings, "hospital_name", ""))
                ).classes('w-96')

                def save_branding():
                    with SessionLocal() as db:
                        s = get_or_create_settings(db)
                        setattr(s, "hospital_name", hospital_input.value.strip())
                        db.commit()
                        ui.notify("Branding saved", type='positive')

                ui.button("Save Branding", on_click=save_branding)

            # =================================================
            # METADATA
            # =================================================
            with ui.tab_panel(tab_metadata):

                show_mag = ui.checkbox(
                    "Show Magnification",
                    value=safe_bool(getattr(settings, "show_magnification", True))
                )

                show_scan = ui.checkbox(
                    "Show Scan Date",
                    value=safe_bool(getattr(settings, "show_scan_date", True))
                )

                def save_metadata():
                    with SessionLocal() as db:
                        s = get_or_create_settings(db)
                        setattr(s, "show_magnification", bool(show_mag.value))
                        setattr(s, "show_scan_date", bool(show_scan.value))
                        db.commit()
                        ui.notify("Metadata saved", type='positive')

                ui.button("Save Preferences", on_click=save_metadata)

            # =================================================
            # ADMIN USERS
            # =================================================
            if tab_admin:
                with ui.tab_panel(tab_admin):

                    with SessionLocal() as db:
                        users = crud.get_all_users(db)

                    rows = [
                        dict(
                            name=safe_str(getattr(u, "name", "")),
                            username=safe_str(getattr(u, "username", "")),
                            role=safe_str(getattr(u, "role", "")),
                            professional_id=safe_str(getattr(u, "professional_id", ""))
                        )
                        for u in users
                    ]

                    columns = [
                        dict(name="name", label="Name", field="name"),
                        dict(name="username", label="Username", field="username"),
                        dict(name="role", label="Role", field="role"),
                        dict(name="professional_id", label="ID", field="professional_id"),
                    ]

                    ui.table(columns=columns, rows=rows)

            # =================================================
            # SYSTEM STATUS
            # =================================================
            with ui.tab_panel(tab_system):

                try:
                    with SessionLocal() as db:
                        db.execute(text("SELECT 1"))
                    db_status = "Connected"
                    color = "green"
                except SQLAlchemyError:
                    db_status = "Disconnected"
                    color = "red"

                storage_path = crud.get_automated_path()

                with ui.card():
                    ui.label(f"Version: {APP_VERSION}")
                    ui.label(f"Database: {db_status}").style(f"color:{color}")
                    ui.label(storage_path)
