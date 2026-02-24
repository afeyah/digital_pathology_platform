import os
import sys
from fastapi import HTTPException
from fastapi.responses import FileResponse
from nicegui import ui, app as ng_app

from app.database import crud
from app.database.create_database import init_db, SessionLocal

# ---------------------------------------------------------
# Import pages individually (IMPORTANT for NiceGUI routing)
# ---------------------------------------------------------
import app.pages.login_page
import app.pages.setup_page
import app.pages.signup_page
import app.pages.dashboard_page
import app.pages.viewer_page
import app.pages.report_page
import app.pages.settings_page


@ng_app.get('/dzi/{patient_id}/{asset_path:path}')
def serve_dzi_asset(patient_id: int, asset_path: str):
    if not asset_path:
        raise HTTPException(status_code=404)

    with SessionLocal() as db:
        storage_path = crud.get_effective_path(db)

    storage_root = os.path.normpath(storage_path)
    requested_path = os.path.normpath(os.path.join(storage_path, asset_path))

    if not requested_path.startswith(storage_root):
        raise HTTPException(status_code=404)

    if not os.path.isfile(requested_path):
        raise HTTPException(status_code=404)

    response = FileResponse(requested_path)
    response.headers['x-patient-id'] = str(patient_id)
    return response


def _configure_stdio_for_unicode() -> None:
    """Avoid Windows charmap failures when logging non-ASCII text."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass


_configure_stdio_for_unicode()


# =========================================================
# ROOT ROUTER
# =========================================================
@ui.page('/')
def index():
    """Main entry router."""

    with SessionLocal() as db:

        # First run -> setup
        if not crud.has_any_user(db):
            ui.navigate.to('/setup')
            return

        # Existing session
        if ng_app.storage.user.get('username'):
            ui.navigate.to('/dashboard')
        else:
            ui.navigate.to('/login')


# =========================================================
# APPLICATION STARTUP
# =========================================================
def startup():
    """Initialize database and storage directory."""

    # App-wide theme configuration (does not create UI elements).
    ng_app.colors(
        primary='#0056B3',
        secondary='#26A69A',
        accent='#9C27B0',
    )

    # 1️⃣ Initialize database
    init_db()

    # 2️⃣ Load settings
    with SessionLocal() as db:
        crud.get_or_create_settings(db)
        storage_path = crud.get_effective_path(db)

    # 3️⃣ Ensure storage directory exists
    os.makedirs(storage_path, exist_ok=True)

    try:
        ng_app.add_static_files('/wsi_static', storage_path, follow_symlink=True, max_cache_age=0)
    except Exception as ex:
        print(f'WSI static route registration warning: {ex}')

    # 4️⃣ Diagnostics
    print("\n--- DIGITAL PATHOLOGY PLATFORM ONLINE ---")
    print(f"Project Directory : {os.getcwd()}")
    print(f"WSI Storage Path  : {storage_path}")
    print("Static folder     : /wsi_static")
    print("------------------------------------------\n")

    return storage_path


# =========================================================
# RUN SERVER
# =========================================================
if __name__ in {"__main__", "__mp_main__"}:

    startup()

    ui.run(
        title="Digital Pathology Platform",
        port=8080,
        storage_secret='kau_pathology_2026_secure_key',
    )
