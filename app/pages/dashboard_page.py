# File: app/pages/dashboard_page.py
from nicegui import ui
from app.components.base_layout import base_page_layout
from app.components.create_case_modal import create_case_modal

@ui.page('/dashboard')
def dashboard_page():
    # Initialize the modal dialog
    new_case_modal = create_case_modal()

    # Define navigation functions
    def open_viewer(case_id):
        ui.notify(f'Opening Viewer for {case_id}')
        ui.navigate.to('/viewer')

    def open_report(case_id):
        ui.notify(f'Viewing Report for {case_id}')
        ui.navigate.to('/report')

    with base_page_layout('Case Management Dashboard'):
        # --- Section: Search Bar & Add Case Button ---
        with ui.row().classes('w-full justify-between items-center mb-6'):
            search_input = ui.input(placeholder='Search by Name or Case ID...') \
                .props('outlined dense') \
                .classes('w-80')
            
            # Add search icon to the input
            search_input.add_slot('prepend', '<q-icon name="search" />')

            ui.button(
                'Create New Case', 
                icon='add', 
                on_click=new_case_modal.open
            ).classes('bg-[#0056B3] text-white')

        # --- Table Structure ---
        columns = [
            {'name': 'id', 'label': 'Case ID', 'field': 'id', 'align': 'left', 'sortable': True},
            {'name': 'patient', 'label': 'Patient Name', 'field': 'patient', 'align': 'left', 'sortable': True},
            {'name': 'date', 'label': 'Date', 'field': 'date', 'align': 'left'},
            {'name': 'status', 'label': 'Status', 'field': 'status', 'align': 'left'},
            {'name': 'tag', 'label': 'Final Tag', 'field': 'tag', 'align': 'center'},
            {'name': 'action', 'label': 'Actions', 'field': 'action', 'align': 'center'},
        ]

        # Dummy data for Ahmed, Fatima, and Omar
        rows = [
            {'id': 'Case-001', 'patient': 'Ahmed Al-Farsi', 'date': '2023-10-27', 'status': 'ANALYZED', 'tag': 'CANCER'},
            {'id': 'Case-002', 'patient': 'Fatima Al-Zahra', 'date': '2023-10-28', 'status': 'NEW', 'tag': 'PENDING'},
            {'id': 'Case-003', 'patient': 'Omar Al-Masri', 'date': '2023-10-29', 'status': 'ANALYZED', 'tag': 'NORMAL'},
        ]

        # --- Render Data Table with Filter Binding ---
        table = ui.table(columns=columns, rows=rows, row_key='id') \
            .classes('w-full shadow-md') \
            .bind_filter_from(search_input, 'value')
            
        # Slot for diagnosis badges using Vue template (No Python 'slot.row' needed)
        table.add_slot('body-cell-tag', '''
            <q-td :props="props">
                <q-badge :color="props.value === 'CANCER' ? 'red' : (props.value === 'NORMAL' ? 'green' : 'grey')">
                    {{ props.value }}
                </q-badge>
            </q-td>
        ''')

        # Slot for action buttons using $emit to talk to Python
        table.add_slot('body-cell-action', '''
            <q-td :props="props" class="text-center">
                <q-btn flat round color="primary" icon="visibility" @click="$emit('view', props.row.id)">
                    <q-tooltip>Open Viewer</q-tooltip>
                </q-btn>
                <q-btn flat round color="secondary" icon="description" @click="$emit('report', props.row.id)">
                    <q-tooltip>View Report</q-tooltip>
                </q-btn>
            </q-td>
        ''')

        # Listen for the 'view' and 'report' events from the table
        table.on('view', lambda msg: open_viewer(msg.args))
        table.on('report', lambda msg: open_report(msg.args))