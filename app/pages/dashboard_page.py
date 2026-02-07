from nicegui import ui
from app.components.base_layout import base_page_layout


@ui.page('/dashboard')
def dashboard():
    with base_page_layout('Case Management Dashboard'):
        ui.label('The list of patient cases will appear here.')
