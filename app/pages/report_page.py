from nicegui import ui
from app.components.base_layout import base_page_layout

@ui.page('/report')
def report_page():
    with base_page_layout('Report Preview'):
        ui.label('Summary Analysis & PDF Download (Task Week 10)')