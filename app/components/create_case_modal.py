from nicegui import ui

def create_case_modal():
    state = {'file_ready': False}

    with ui.dialog() as dialog, ui.card().classes('w-96 p-6'):
        ui.label('Create New Case').classes('text-xl font-bold mb-4 text-[#333333]')
        
        name_input = ui.input('Patient Name', 
                              on_change=lambda: update_button_state()) \
                        .classes('w-full')
        
        # We don't put 'on_added' inside ui.upload()
        uploader = ui.upload(label='Upload WSI (.svs)', 
                             auto_upload=True) \
                     .classes('w-full mt-4') \
                     .props('accept=.svs')
        
        # Use .on('added', ...) to detect file arrival instantly
        uploader.on('added', lambda e: handle_file_added(e))
        # -------------------------

        status_label = ui.label('Waiting for file...').classes('text-sm text-gray-500 mt-2')
        progress_bar = ui.linear_progress(value=0, show_value=False).classes('w-full mt-1')
        progress_bar.visible = False

        def handle_file_added(e):
            state['file_ready'] = True
            # Get the file name from the event
            file_name = e.args[0]['name'] if 'name' in e.args[0] else 'SVS File'
            status_label.set_text(f'Ready: {file_name}')
            status_label.classes(replace='text-gray-500 text-green-600')
            update_button_state()

        def update_button_state():
            has_name = len(name_input.value.strip()) > 0
            create_btn.enabled = has_name and state['file_ready']

        with ui.row().classes('w-full justify-end mt-6'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            create_btn = ui.button('CREATE', on_click=lambda: finalize_case())
            create_btn.classes('bg-[#0056B3]')
            create_btn.enabled = False 

        async def finalize_case():
            status_label.set_text('Extracting metadata...')
            progress_bar.visible = True
            progress_bar.set_value(0.5)
            await ui.run_javascript('await new Promise(r => setTimeout(r, 1500))')
            ui.notify(f"Case for {name_input.value} created!", type='positive')
            dialog.close()
            
    return dialog