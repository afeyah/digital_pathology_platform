# File: app/pages/login_page.py
from nicegui import ui
from app.database import crud
from app.database.create_database import SessionLocal, verify_password

@ui.page('/login')
def login_page():
    # Force a check: if no users exist in the DB, redirect to setup immediately
    with SessionLocal() as db:
        if not crud.get_all_users(db):
            ui.navigate.to('/setup')

    with ui.card().classes('absolute-center w-96 p-8 shadow-lg'):
        ui.label('Digital Pathology Platform').classes(
            'text-2xl font-bold mb-4 text-[#333333] text-center w-full'
        )

        # Input Fields
        username_input = ui.input('Username').classes('w-full').props('outlined')
        password_input = ui.input('Password', password=True).classes('w-full mt-2').props('outlined')

        spinner = ui.spinner(size='lg', color='#0056B3').classes('mt-4 mx-auto')
        spinner.visible = False  

        async def try_login():
            if not username_input.value or not password_input.value:
                ui.notify('Please fill in all fields!', type='warning')
                return

            login_btn.disable()
            spinner.visible = True

            try:
                # Use real database session
                with SessionLocal() as db:
                    user = crud.get_user_by_username(db, username_input.value)
                    
                    # Verify password using the bcrypt helper
                    if user and verify_password(password_input.value, user.password):
                        ui.notify(f"Welcome, {user.name}", type='positive')
                        ui.navigate.to('/dashboard') # Proceed to Task 1
                    else:
                        ui.notify('Invalid username or password', type='negative')

            except Exception as e:
                ui.notify(f'Database connection error: {str(e)}', type='negative')

            finally:
                spinner.visible = False
                login_btn.enable()

        login_btn = ui.button('Sign In', on_click=try_login).classes(
            'w-full mt-6 bg-[#0056B3] text-white'
        )