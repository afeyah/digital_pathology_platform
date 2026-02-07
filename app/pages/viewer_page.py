from nicegui import ui
from app.components.base_layout import base_page_layout

@ui.page('/viewer')
def viewer_page():
    with base_page_layout('Interactive WSI Viewer'):
        ui.label('Area Zoom/Pan Slide SVS (Task Week 5)')
        ui.button('Back to Dashboard', on_click=lambda: ui.navigate.to('/dashboard'))