import asyncio
import os
from nicegui import ui, run
from app.components.base_layout import base_page_layout
from app.components.create_case_modal import create_case_modal
from app.database import crud
from app.database.create_database import SessionLocal 
from app.services.wsi_service import get_dzi_paths, run_tiling_process

@ui.page('/dashboard')
def dashboard_page():
    """
    Halaman Dashboard Manajemen Kasus.
    Menggunakan penyimpanan otomatis di Documents dan navigasi berbasis Patient ID.
    """
    
    new_case_modal = create_case_modal()
    view_lock = asyncio.Lock()

    with ui.dialog().props('persistent no-esc-dismiss no-backdrop-dismiss no-route-dismiss') as loading_dialog, ui.card().classes('w-[520px] p-6'):
        with ui.row().classes('items-center gap-3'):
            ui.spinner(size='lg', color='primary')
            ui.label('Optimizing Slide for High-Resolution Viewing... Please wait.').classes('text-sm')

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
            dialog_open = False
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

                loading_dialog.open()
                dialog_open = True
                await asyncio.sleep(0.5)

                try:
                    success = await run_tiling_process(wsi.file_path, storage_path)
                except Exception as ex:
                    ui.notify(f"Slide optimization failed: {ex}", type="negative")
                    return

                if not success:
                    ui.notify("Failed to optimize slide for viewing", type="negative")
                    return

                if not os.path.exists(dzi_path):
                    ui.notify("Slide optimization finished but .dzi file was not found", type="negative")
                    return

                loading_dialog.close()
                dialog_open = False
                ui.navigate.to(f"/viewer/{normalized_patient_id}")
            except Exception as ex:
                ui.notify(f"Unable to open viewer: {ex}", type="negative")
            finally:
                if dialog_open:
                    loading_dialog.close()

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
