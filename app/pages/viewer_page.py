from nicegui import ui, app
from app.components.base_layout import base_page_layout
from app.components.viewer_sidebar import viewer_sidebar
from app.components.viewer_canvas import viewer_canvas
from app.components.viewer_toolbar import viewer_toolbar
from app.database import crud
from app.database.create_database import SessionLocal

@ui.page('/viewer')
def viewer_page(id: str = 'Unknown'): # Capture 'id' from URL
    # Fetch patient name from DB to show in the title
    patient_name = "Loading..."
    with SessionLocal() as db:
        patient = crud.get_all_patients(db) # In a real scenario, use get_patient_by_id
        # For now, let's just display the ID in the layout
    
    with base_page_layout(f'Viewer: Case {id}'):
        viewer_toolbar()

        with ui.splitter(value=75).classes('w-full h-[80vh] border shadow-lg bg-white') as splitter:
            with splitter.before:
                viewer_canvas()

            with splitter.after:
                # You can pass the ID to the sidebar to show specific ROI data
                viewer_sidebar()

        with ui.row().classes('w-full justify-end mt-4'):
            ui.button('Back to Dashboard', icon='arrow_back', 
                      on_click=lambda: ui.navigate.to('/dashboard')) \
                .props('flat')