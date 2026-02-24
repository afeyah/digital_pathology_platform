from datetime import datetime

from fastapi import Request
from nicegui import ui

from app.components.base_layout import base_page_layout
from app.database.create_database import SessionLocal
from app.database.models import Patient, Report, ROI, WSI


def _format_datetime(value) -> str:
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return 'Not available'


@ui.page('/report')
def report_page(request: Request):
    case_id = (request.query_params.get('id') or '').strip()

    with base_page_layout('Report Preview'):
        if not case_id:
            ui.label('No case selected').classes('text-lg text-red-600')
            ui.label('Open report from the dashboard Report icon.').classes('text-sm text-gray-600')
            ui.button('Back to Dashboard', icon='arrow_back', on_click=lambda: ui.navigate.to('/dashboard')).props('flat')
            return

        with SessionLocal() as db:
            patient = db.query(Patient).filter(Patient.case_id == case_id).first()
            if patient is None:
                ui.label(f'Case not found: {case_id}').classes('text-lg text-red-600')
                ui.button('Back to Dashboard', icon='arrow_back', on_click=lambda: ui.navigate.to('/dashboard')).props('flat')
                return

            latest_wsi = db.query(WSI).filter(WSI.patient_id == patient.id).order_by(WSI.id.desc()).first()
            latest_report = None
            roi_count = 0
            if latest_wsi is not None:
                latest_report = db.query(Report).filter(Report.wsi_id == latest_wsi.id).order_by(Report.created_at.desc()).first()
                if latest_report is not None:
                    roi_count = db.query(ROI).filter(ROI.report_id == latest_report.id).count()

        ui.label('Structured Clinical Report Preview').classes('text-2xl font-bold mb-2')

        with ui.row().classes('w-full items-start gap-4 flex-wrap'):
            with ui.card().classes('w-full max-w-[420px]'):
                ui.label('Patient Data').classes('text-lg font-semibold')
                ui.separator()
                ui.label(f'Case ID: {patient.case_id}').classes('text-sm')
                ui.label(f'Patient Name: {patient.name}').classes('text-sm')
                ui.label(f'Patient ID: {patient.id}').classes('text-sm')

            with ui.card().classes('w-full max-w-[420px]'):
                ui.label('Slide & Report Metadata').classes('text-lg font-semibold')
                ui.separator()
                if latest_wsi is None:
                    ui.label('No WSI uploaded for this case').classes('text-sm text-red-600')
                else:
                    ui.label(f'WSI ID: {latest_wsi.id}').classes('text-sm')
                    ui.label(f'WSI File: {latest_wsi.file_path}').classes('text-sm break-all')
                    if latest_report is None:
                        ui.label('No report generated yet').classes('text-sm text-amber-700')
                    else:
                        ui.label(f'Report ID: {latest_report.id}').classes('text-sm')
                        ui.label(f'Report Timestamp: {_format_datetime(latest_report.created_at)}').classes('text-sm')
                        ui.label(f'Saved ROIs: {roi_count}').classes('text-sm')

        with ui.card().classes('w-full mt-4'):
            ui.label('AI Result Placeholders').classes('text-lg font-semibold')
            ui.separator()
            ui.label('Primary Classification: PENDING').classes('text-sm')
            ui.label('Malignancy Probability: PENDING').classes('text-sm')
            ui.label('Heatmap Overlay: NOT GENERATED').classes('text-sm')
            ui.label('Model Confidence: PENDING').classes('text-sm')
            ui.label('Pathologist Final Decision: PENDING').classes('text-sm')

        with ui.row().classes('w-full justify-end mt-4'):
            ui.button('Back to Dashboard', icon='arrow_back', on_click=lambda: ui.navigate.to('/dashboard')).props('flat')
