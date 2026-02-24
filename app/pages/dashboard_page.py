import asyncio
import os
import threading
from nicegui import ui, run
from app.components.base_layout import base_page_layout
from app.components.create_case_modal import create_case_modal
from app.database import crud
from app.database.create_database import SessionLocal
from app.services.wsi_service import convert_svs_to_dzi, get_dzi_paths

@ui.page('/dashboard')
def dashboard_page():
    """
    Halaman Dashboard Manajemen Kasus.
    Menggunakan penyimpanan otomatis di Documents dan navigasi berbasis Patient ID.
    """
    
    new_case_modal = create_case_modal()
    view_lock = asyncio.Lock()

    def _event_value(args):
        """Normalize NiceGUI table slot event args (often wrapped in a list)."""
        if isinstance(args, (list, tuple)):
            return args[0] if args else None
        return args

    def _event_row(args):
        """Extract row payload emitted from table action buttons."""
        value = _event_value(args)
        return value if isinstance(value, dict) else None

    def _event_field(args, key):
        """Read a field from emitted row payload, with fallback to raw event value."""
        row = _event_row(args)
        if row is not None:
            return row.get(key)
        return _event_value(args)

    def _normalize_int(value):
        """Convert emitted value to int or return None when invalid."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    async def open_viewer(patient_id):
        """Auto-prepare tiles (if needed) then open viewer by patient ID."""
        normalized_patient_id = _normalize_int(patient_id)
        if normalized_patient_id is None:
            ui.notify("No WSI file available for this case", type="warning")
            return

        if view_lock.locked():
            ui.notify("Another slide is being prepared. Please wait...", type="warning")
            return

        async with view_lock:
            try:
                with SessionLocal() as db:
                    wsi = crud.get_latest_wsi_for_patient(db, normalized_patient_id)
                    storage_path = crud.get_effective_path(db)

                if not wsi or not wsi.file_path:
                    ui.notify("No WSI file available for this case", type="warning")
                    return

                dzi_path, _ = get_dzi_paths(wsi.file_path, storage_path)
                if os.path.exists(dzi_path):
                    ui.navigate.to(f"/viewer/{normalized_patient_id}")
                    return

                progress_state = {'value': 0.0, 'ready': False, 'failed': False}
                progress_lock = threading.Lock()

                def update_progress(value: float) -> None:
                    with progress_lock:
                        progress_state['value'] = max(0.0, min(1.0, float(value)))

                with ui.card().classes('fixed bottom-4 right-4 z-50 w-72 p-4 shadow-lg bg-white border rounded-lg') as progress_card:
                    ui.label('Optimizing slide tiles...').classes('text-xs text-gray-700')
                    progress_bar = ui.linear_progress(value=0.0).props('color=primary').classes('w-full')
                    progress_label = ui.label('0%').classes('text-xs text-gray-600 mt-1')
                    open_button = ui.button(
                        'Open Viewer',
                        on_click=lambda: ui.navigate.to(f"/viewer/{normalized_patient_id}"),
                    ).classes('w-full mt-2 bg-[#0056B3] text-white text-xs')
                    open_button.visible = False

                def refresh_progress_card() -> None:
                    with progress_lock:
                        value = float(progress_state['value'])
                        ready = bool(progress_state['ready'])
                        failed = bool(progress_state['failed'])

                    progress_bar.value = value
                    if ready:
                        progress_bar.value = 1.0
                        progress_label.set_text('Ready!')
                        open_button.visible = True
                        progress_timer.active = False
                        return
                    if failed:
                        progress_label.set_text('Failed to optimize slide')
                        progress_timer.active = False
                        return
                    progress_label.set_text(f'{int(value * 100)}%')

                progress_timer = ui.timer(0.2, refresh_progress_card)

                try:
                    success = await run.io_bound(convert_svs_to_dzi, wsi.file_path, storage_path, update_progress)
                except Exception as ex:
                    with progress_lock:
                        progress_state['failed'] = True
                    refresh_progress_card()
                    ui.notify(f"Slide optimization failed: {ex}", type="negative")
                    return

                if not success:
                    with progress_lock:
                        progress_state['failed'] = True
                    refresh_progress_card()
                    ui.notify("Failed to optimize slide for viewing", type="negative")
                    return

                if not os.path.exists(dzi_path):
                    with progress_lock:
                        progress_state['failed'] = True
                    refresh_progress_card()
                    ui.notify("Slide optimization finished but .dzi file was not found", type="negative")
                    return

                with progress_lock:
                    progress_state['value'] = 1.0
                    progress_state['ready'] = True
                refresh_progress_card()
            except Exception as ex:
                ui.notify(f"Unable to open viewer: {ex}", type="negative")

    def open_report(case_id):
        """Membuka halaman laporan berdasarkan Case ID."""
        ui.navigate.to(f"/report?id={case_id}")

    async def on_view_event(msg):
        await open_viewer(_event_field(msg.args, "patient_id"))

    def on_report_event(msg):
        open_report(_event_field(msg.args, "case_id"))

    def get_db_rows():
        """Mengambil data pasien dari database untuk ditampilkan di tabel."""
        try:
            with SessionLocal() as db:
                patients = crud.get_all_patients(db)
                rows = []
                for p in patients:
                    wsi = p.wsis[0] if p.wsis else None
                    file_name = wsi.file_path if wsi else "No File"
                    wsi_id = wsi.id if wsi else None
                    
                    rows.append({
                        "id": wsi_id,
                        "patient_id": p.id,
                        "case_id": p.case_id, 
                        "patient": p.name, 
                        "file": file_name,
                        "tag": "PENDING"
                    })
                return rows
        except Exception as e:
            ui.notify(f"Database Error: {str(e)}", type="negative")
            return []

  
    with base_page_layout("Case Management Dashboard"):
     
        with ui.row().classes("w-full justify-between items-center mb-6"):
            search_input = ui.input(placeholder="Search cases...").props("outlined dense").classes("w-80")
            search_input.add_slot("prepend", '<q-icon name="search" />')
            ui.button("Create New Case", icon="add", on_click=new_case_modal.open)\
                .classes("bg-[#0056B3] text-white")

        columns = [
            {"name": "case_id", "label": "Case ID", "field": "case_id", "align": "left", "sortable": True},
            {"name": "patient", "label": "Patient Name", "field": "patient", "align": "left", "sortable": True},
            {"name": "file", "label": "SVS File", "field": "file", "align": "left"},
            {"name": "tag", "label": "Final Tag", "field": "tag", "align": "center"},
            {"name": "action", "label": "Actions", "field": "action", "align": "center"},
        ]


        table = ui.table(columns=columns, rows=get_db_rows(), row_key="case_id") \
            .classes("w-full shadow-md") \
            .bind_filter_from(search_input, "value")

        table.add_slot('body-cell-tag', '''
            <q-td :props="props">
                <q-badge :color="props.value === 'CANCER' ? 'red' : (props.value === 'NORMAL' ? 'green' : 'grey')">
                    {{ props.value }}
                </q-badge>
            </q-td>
        ''')


        table.add_slot('body-cell-action', '''
            <q-td :props="props" class="text-center">
                <q-btn flat round color="primary" icon="visibility" @click="$parent.$emit('view', props.row)">
                    <q-tooltip>Open WSI Viewer</q-tooltip>
                </q-btn>
                <q-btn flat round color="secondary" icon="description" @click="$parent.$emit('report', props.row)">
                    <q-tooltip>View Pathology Report</q-tooltip>
                </q-btn>
            </q-td>
        ''')

        # Event listeners
        table.on("view", on_view_event)
        table.on("report", on_report_event)
