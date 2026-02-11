# File: app/pages/viewer_page.py
from nicegui import ui
from app.components.base_layout import base_page_layout
from app.components.viewer_sidebar import viewer_sidebar
from app.components.viewer_canvas import viewer_canvas
from app.components.viewer_toolbar import viewer_toolbar # New import

@ui.page('/viewer')
def viewer_page():
    with base_page_layout('Interactive WSI Viewer'):
        # Add the toolbar at the top of the content area
        viewer_toolbar()

        # Split layout for Canvas and Sidebar
        with ui.splitter(value=75).classes('w-full h-[80vh] border shadow-lg bg-white') as splitter:
            
            with splitter.before:
                # Main WSI display area
                viewer_canvas()

            with splitter.after:
                # Metadata and ROI info panel
                viewer_sidebar()

        # Footer-style navigation
        with ui.row().classes('w-full justify-end mt-4'):
            ui.button('Back to Dashboard', icon='arrow_back', 
                      on_click=lambda: ui.navigate.to('/dashboard')) \
                .props('flat')