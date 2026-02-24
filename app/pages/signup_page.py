# File: app/pages/signup_page.py
from nicegui import ui
from app.database import crud
from app.database.create_database import SessionLocal, UserRole

@ui.page('/signup')
def signup_page():
    """Provides a simple account creation page for new users."""
    
    with ui.card().classes('absolute-center w-96 p-8 shadow-lg rounded-lg'):
        ui.label('Create Account').classes('text-2xl font-bold text-center w-full mb-4')

        full_name = ui.input('Full Name').classes('w-full').props('outlined')
        username = ui.input('Username').classes('w-full mt-2').props('outlined')
        password = ui.input('Password', password=True).classes('w-full mt-2').props('outlined')

        async def handle_signup():
            if not all([full_name.value, username.value, password.value]):
                ui.notify('Please fill all fields', type='warning')
                return

            try:
                with SessionLocal() as db:
                    # New users created here default to PATHOLOGIST role
                    new_user = crud.create_user(
                        db=db, 
                        name=full_name.value, 
                        username=username.value, 
                        password=password.value, 
                        role=UserRole.PATHOLOGIST 
                    )
                    
                    if new_user:
                        ui.notify('Account created! You can now login.', type='positive')
                        ui.navigate.to('/login') 
            except Exception as e:
                ui.notify(f'Error: {str(e)}', type='negative')

        ui.button('SIGN UP', on_click=handle_signup).classes('w-full mt-6 py-2 bg-[#26A69A] text-white')
        ui.link('Back to Login', '/login').classes('text-xs mt-4 block text-center')