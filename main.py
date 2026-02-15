# File: main.py
from nicegui import ui
from app.database.create_database import init_db, create_initial_users

# Import all page modules to register their @ui.page decorators.

from app.pages import (
    login_page,      # URL: /login
    setup_page,      # URL: /setup 
    dashboard_page,  # URL: /dashboard 
    viewer_page,     # URL: /viewer 
    settings_page,   # URL: /settings 
    report_page      # URL: /report
)

# Root route (Index) - Redirects new visitors to the Login page
@ui.page('/')
def index():
    """Redirects the base URL to the login page."""
    ui.navigate.to('/login')

# Application Theme and Branding for King Abdulaziz University
ui.colors(primary='#0056B3', secondary='#26A69A', accent='#9C27B0')

# Start the NiceGUI server
if __name__ in {"__main__", "__mp_main__"}:
    # 1. Initialize the database before the UI starts
    # This creates the .db file and the default admin if they don't exist.
    init_db()
    create_initial_users()

    # 2. Run the application with Storage Secret
    ui.run(
        title="Path-Benchmark Platform", 
        port=8080,
        reload=True,
        # MANDATORY for Task 5: Encrypts local WSI path settings
        storage_secret='kau_pathology_2026_secret_key' 
    )