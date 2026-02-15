# File: app/pages/dashboard_page.py
from nicegui import ui
from app.components.base_layout import base_page_layout
from app.components.create_case_modal import create_case_modal
from app.database import crud
from app.database.session import SessionLocal  # Ensures DB connection is handled

@ui.page('/dashboard')
def dashboard_page():
    # Initialize the modal for adding new pathology cases
    new_case_modal = create_case_modal()

    # Define navigation logic for the viewer and report pages
    def open_viewer(case_id):
        ui.notify(f'Opening Viewer for {case_id}')
        ui.navigate.to(f'/viewer?id={case_id}')

    def open_report(case_id):
        ui.notify(f'Viewing Report for {case_id}')
        ui.navigate.to(f'/report?id={case_id}')

    # --- Fetch Live Data from Database ---
    # This function replaces dummy data with real entries from Suhail's CRUD
    def get_db_rows():
        try:
            with SessionLocal() as db:
                # Fetching all patient records from the database
                patients = crud.get_all_patients(db)
                
                # Mapping database objects to a dictionary format compatible with ui.table
                return [
                    {
                        'id': p.case_id, 
                        'patient': p.name, 
                        'date': '2026-02-15', # Placeholder date, can be updated in models.py later
                        'status': 'NEW',       # Default clinical status
                        'tag': 'PENDING'       # Default AI diagnosis tag
                    } for p in patients
                ]
        except Exception as e:
            # UI notification in case of database connectivity issues
            ui.notify(f'Database Error: {e}', type='negative')
            return []

    with base_page_layout('Case Management Dashboard'):
        # --- Section: Search Bar & Action Buttons ---
        with ui.row().classes('w-full justify-between items-center mb-6'):
            # Reactive search input for filtering the patient list
            search_input = ui.input(placeholder='Search by Name or Case ID...') \
                .props('outlined dense') \
                .classes('w-80')
            
            # Adding a search icon using Quasar slots
            search_input.add_slot('prepend', '<q-icon name="search" />')

            # Button to trigger the 'Create New Case' modal
            ui.button(
                'Create New Case', 
                icon='add', 
                on_click=new_case_modal.open
            ).classes('bg-[#0056B3] text-white')

        # --- Table Configuration ---
        columns = [
            {'name': 'id', 'label': 'Case ID', 'field': 'id', 'align': 'left', 'sortable': True},
            {'name': 'patient', 'label': 'Patient Name', 'field': 'patient', 'align': 'left', 'sortable': True},
            {'name': 'date', 'label': 'Date', 'field': 'date', 'align': 'left'},
            {'name': 'status', 'label': 'Status', 'field': 'status', 'align': 'left'},
            {'name': 'tag', 'label': 'Final Tag', 'field': 'tag', 'align': 'center'},
            {'name': 'action', 'label': 'Actions', 'field': 'action', 'align': 'center'},
        ]

        # Populate the table with dynamic data from the database
        rows = get_db_rows()

        # --- Rendering the Data Table ---
        # Binds the filter directly to the search input for real-time results
        table = ui.table(columns=columns, rows=rows, row_key='id') \
            .classes('w-full shadow-md') \
            .bind_filter_from(search_input, 'value')
            
        # UI Slot: Diagnosis Badges (Vue/Quasar template for dynamic coloring)
        table.add_slot('body-cell-tag', '''
            <q-td :props="props">
                <q-badge :color="props.value === 'CANCER' ? 'red' : (props.value === 'NORMAL' ? 'green' : 'grey')">
                    {{ props.value }}
                </q-badge>
            </q-td>
        ''')

        # UI Slot: Action Buttons (Using $emit to communicate with Python functions)
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

        # Python Event Listeners for the Vue $emit calls
        table.on('view', lambda msg: open_viewer(msg.args))
        table.on('report', lambda msg: open_report(msg.args))