# File: app/pages/setup_page.py
from nicegui import ui
from app.database import crud
from app.database.create_database import SessionLocal, UserRole

@ui.page('/setup')
def setup_page():
    """
    Onboarding Setup Page: Triggered when the database is empty.
    Allows the user to set their own initial Administrator credentials.
    """
    
    # Page layout with a centered, styled card
    with ui.card().classes('absolute-center w-96 p-8 shadow-xl rounded-xl'):
        ui.label('Platform Onboarding').classes('text-2xl font-bold text-center w-full mb-2 text-[#0056B3]')
        ui.label('Create your primary Administrator account to get started.')\
            .classes('text-gray-500 text-center mb-6')

        # Credentials Input with Outlined Styling
        full_name = ui.input('Full Name').classes('w-full').props('outlined dense')
        username = ui.input('Choose Username').classes('w-full mt-2').props('outlined dense')
        
        # Masked password field for security
        password = ui.input('Create Password', password=True)\
            .classes('w-full mt-2')\
            .props('outlined dense password-toggle-button')

        async def handle_setup():
            """
            Validates inputs and creates the first system user.
            """
            if not all([full_name.value.strip(), username.value.strip(), password.value.strip()]):
                ui.notify('All fields are required to secure the platform.', type='warning')
                return

            try:
                with SessionLocal() as db:
                    # Create the first user and assign ADMIN privileges
                    new_user = crud.create_user(
                        db=db, 
                        name=full_name.value.strip(), 
                        username=username.value.strip(), 
                        password=password.value, 
                        role=UserRole.ADMIN 
                    )
                    
                    if new_user:
                        ui.notify('Setup complete! Welcome to the platform.', type='positive')
                        # Navigate to the login page to start the session
                        ui.navigate.to('/login') 
            except Exception as e:
                ui.notify(f'Critical Setup Error: {str(e)}', type='negative')

        # Primary Action Button
        ui.button('FINALIZE SYSTEM SETUP', on_click=handle_setup)\
            .classes('w-full mt-6 py-3 bg-[#0056B3] text-white font-bold')