# File: app/pages/settings_page.py
from nicegui import ui, app  # FIX: Explicitly import 'app' here
from app.components.base_layout import base_page_layout

@ui.page('/settings')
def settings_page():
    """
    Fulfills Task 5: Pathologists select a local directory for WSI files.
    This ensures large .svs files remain on the local disk.
    """
    with base_page_layout('Application Settings'):
        with ui.column().classes('w-full max-w-2xl mx-auto p-6 gap-6'):
            ui.label('Storage Configuration').classes('text-3xl font-bold text-[#333333]')

            # --- WSI Storage Section (Task 5) ---
            with ui.card().classes('w-full p-6 shadow-md border-t-4 border-[#0056B3]'):
                with ui.row().classes('items-center gap-2 mb-2'):
                    ui.icon('folder_open', size='sm').classes('text-[#0056B3]')
                    ui.label('WSI Image Directory').classes('text-xl font-semibold')
                
                ui.label('Set the local path where your pathology slides are stored.').classes('text-gray-500 mb-4')

                # Using app.storage.user to keep the path persistent
                # We use .get() to avoid errors if the key doesn't exist yet
                current_path = app.storage.user.get('wsi_path', '')

                path_input = ui.input(
                    label='Local Storage Path',
                    placeholder='e.g., C:/MedicalData/Slides/',
                    value=current_path
                ).props('outlined').classes('w-full')

                def save_settings():
                    if not path_input.value:
                        ui.notify('Please enter a valid directory path', type='warning')
                        return
                    
                    # Store the path in the app's persistent storage
                    app.storage.user['wsi_path'] = path_input.value
                    ui.notify(f'Storage path updated: {path_input.value}', type='positive')

                ui.button('Save Configuration', on_click=save_settings).classes('mt-4 bg-[#0056B3] text-white px-6')

            # --- System Information (Task 3: Complete Website) ---
            with ui.card().classes('w-full p-6 bg-gray-50 border-dashed border-2 border-gray-300'):
                ui.label('King Abdulaziz University').classes('font-bold text-gray-700')
                ui.label('Path-Benchmark Platform v1.0').classes('text-sm text-gray-600')

        # Navigation
        ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/dashboard')) \
            .props('fab color=primary').classes('fixed bottom-8 right-8')