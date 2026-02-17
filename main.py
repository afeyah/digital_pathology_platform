# File: main.py
from nicegui import ui
from app.database.create_database import init_db, create_initial_users

from app.pages import (
    login_page,      
    setup_page,      
    dashboard_page,  
    viewer_page,     
    settings_page,   
    report_page      
)

@ui.page('/')
def index():
    """Mengatur tema warna KAU dan mengarahkan ke Login."""
    ui.colors(primary='#0056B3', secondary='#26A69A', accent='#9C27B0')
    ui.navigate.to('/login')

# 3. Eksekusi Server
if __name__ in {"__main__", "__mp_main__"}:
    
    init_db()
    create_initial_users()

    
    ui.run(
        title="Path-Benchmark Platform", 
        port=8080,
        reload=True,
        storage_secret='kau_pathology_2026_secret_key' 
    )