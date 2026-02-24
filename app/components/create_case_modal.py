import asyncio
import os

from nicegui import run, ui

from app.database import crud
from app.database.create_database import SessionLocal, WSI
from app.services.wsi_service import convert_svs_to_dzi, dzi_assets_exist


_tiling_tasks = {}


def _safe_log(message: str) -> None:
    """Log safely even when terminal encoding cannot represent some characters."""
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode('ascii', errors='backslashreplace').decode('ascii'))


def _start_background_tiling(file_name: str, storage_path: str) -> bool:
    """Trigger DZI generation in background without blocking current UI flow."""
    job_key = os.path.normcase(os.path.abspath(os.path.join(storage_path, file_name)))
    existing = _tiling_tasks.get(job_key)
    if existing and not existing.done():
        return False

    async def _runner():
        try:
            if dzi_assets_exist(file_name, storage_path):
                return
            await run.io_bound(convert_svs_to_dzi, file_name, storage_path)
        except Exception as ex:
            _safe_log(f'BACKGROUND TILING ERROR -> {ex}')
        finally:
            _tiling_tasks.pop(job_key, None)

    _tiling_tasks[job_key] = asyncio.create_task(_runner())
    return True


def create_case_modal():
    """Dialog untuk membuat case baru + upload WSI (NiceGUI modern API)."""

    # -------------------------
    # Local UI state
    # -------------------------
    state = {
        'file_ready': False,
        'filename': None,
    }

    # -------------------------
    # Dialog UI
    # -------------------------
    with ui.dialog() as dialog, ui.card().classes('w-96 p-6'):
        ui.label('Create New Case').classes('text-xl font-bold mb-4')

        # -------------------------
        # Button state controller
        # -------------------------
        def update_button_state():
            create_btn.enabled = (
                bool(name_input.value.strip()) and state['file_ready']
            )

        # -------------------------
        # Patient name input
        # -------------------------
        name_input = ui.input('Patient Name').classes('w-full')

        # NiceGUI modern event system
        name_input.on('update:model-value', lambda e: update_button_state())

        # -------------------------
        # Upload status label
        # -------------------------
        status_label = ui.label('Waiting for file...').classes(
            'text-sm text-gray-500 mt-2'
        )

        # -------------------------
        # Upload handler
        # -------------------------
        async def handle_upload(e):
            try:
                file_name = None
                file_content = None

                # NiceGUI version kamu
                if hasattr(e, 'file') and e.file:
                    uploaded = e.file

                    if hasattr(uploaded, 'name'):
                        file_name = uploaded.name
                    elif hasattr(uploaded, 'filename'):
                        file_name = uploaded.filename

                    file_content = uploaded

                if not file_name or not file_content:
                    raise RuntimeError('Could not read uploaded file')

                # get storage path
                with SessionLocal() as db:
                    storage_path = crud.get_effective_path(db)

                os.makedirs(storage_path, exist_ok=True)
                save_path = os.path.join(storage_path, file_name)

                # IMPORTANT: await read()
                data = await file_content.read()

                with open(save_path, 'wb') as f:
                    f.write(data)

                state['file_ready'] = True
                state['filename'] = file_name

                status_label.set_text(f'Ready: {file_name}')
                status_label.classes(replace='text-green-600')

                update_button_state()

                ui.notify('File uploaded successfully', type='positive')
                _safe_log(f'UPLOAD SUCCESS -> {save_path}')
                if _start_background_tiling(file_name, storage_path):
                    ui.notify(
                        'Background tiling started. You can continue using the dashboard.',
                        type='info',
                    )

            except Exception as ex:
                ui.notify(f'Upload failed: {ex}', type='negative')
                _safe_log(f'UPLOAD ERROR -> {ex}')


        # -------------------------
        # Upload component
        # -------------------------
        ui.upload(
            label='Upload WSI (.svs)',
            auto_upload=True,
            max_files=1,
            on_upload=handle_upload,
        ).props('accept=.svs').classes('w-full mt-4')

        # -------------------------
        # Finalize case creation
        # -------------------------
        async def finalize_case():
            try:
                with SessionLocal() as db:
                    gen_id = f"CASE-{id(name_input.value) % 1000}"

                    patient = crud.create_patient(
                        db,
                        name_input.value,
                        gen_id,
                    )

                    if not patient:
                        raise RuntimeError('Failed to create patient')

                    db.add(
                        WSI(
                            file_path=state['filename'],
                            patient_id=patient.id,
                        )
                    )
                    db.commit()

                ui.notify(f'Case {gen_id} created!', type='positive')
                dialog.close()
                ui.navigate.to('/dashboard')

            except Exception as ex:
                ui.notify(f'Database error: {ex}', type='negative')
                _safe_log(f'DATABASE ERROR -> {ex}')

        # -------------------------
        # Action buttons
        # -------------------------
        with ui.row().classes('w-full justify-end mt-6'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            create_btn = ui.button('CREATE', on_click=finalize_case)
            create_btn.enabled = False

    return dialog
