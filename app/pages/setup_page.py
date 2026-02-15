# File: app/pages/setup_page.py
from nicegui import ui
from app.database import crud
# Import SessionLocal and UserRole from the main database file
from app.database.create_database import SessionLocal, UserRole

@ui.page('/setup')
def setup_page():
    """
    Fulfills Task 4: Redirects here on first login to create credentials.
    """
    
    with ui.card().classes('absolute-center w-96 p-8 shadow-lg rounded-lg'):
        ui.label('Account Setup').classes('text-2xl font-bold text-center w-full mb-2')
        ui.label('Create your administrative credentials.').classes('text-gray-500 text-center mb-6')

        # UI Input fields
        full_name = ui.input('Full Name').classes('w-full').props('outlined')
        username = ui.input('New Username').classes('w-full mt-2').props('outlined')
        password = ui.input('New Password', password=True).classes('w-full mt-2').props('outlined')

        async def handle_setup():
            if not all([full_name.value, username.value, password.value]):
                ui.notify('Please fill in all fields', type='warning')
                return

            try:
                with SessionLocal() as db:
                    # Use the UserRole enum instead of a string
                    new_user = crud.create_user(
                        db=db, 
                        name=full_name.value, 
                        username=username.value, 
                        password=password.value, 
                        role=UserRole.PATHOLOGIST 
                    )
                    
                    if new_user:
                        ui.notify('Account successfully created!', type='positive')
                        ui.navigate.to('/login') 
            except Exception as e:
                ui.notify(f'Database error: {str(e)}', type='negative')

        ui.button('Finish Setup', on_click=handle_setup).classes('w-full mt-6 py-2 bg-[#0056B3] text-white')