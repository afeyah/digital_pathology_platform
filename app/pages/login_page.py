# File: app/pages/login_page.py
from nicegui import ui, app
from app.database import crud
from app.database.create_database import SessionLocal, verify_password

@ui.page('/login')
def login_page():
    """
    Standard Login Page for the Path-Benchmark Platform.
    Includes a redirect to setup for new installations and a link for new user registration.
    """
    
    # Check if any users exist; if not, redirect to first-run setup
    with SessionLocal() as db:
        if not crud.has_any_user(db):
            ui.navigate.to('/setup')
            return

    with ui.card().classes('absolute-center w-96 p-8 shadow-xl rounded-xl'):
        ui.label('Digital Pathology Platform').classes(
            'text-2xl font-bold mb-4 text-[#0056B3] text-center w-full'
        )
        ui.label('Please sign in to access your dashboard.').classes('text-gray-500 text-center mb-6')

        # Credentials Input Fields
        username_input = ui.input('Username').classes('w-full').props('outlined dense')
        password_input = ui.input('Password', password=True).classes('w-full mt-2').props('outlined dense')

        # Loading Indicator
        spinner = ui.spinner(size='lg', color='#0056B3').classes('mt-4 mx-auto')
        spinner.visible = False  

        async def try_login():
            """Verifies user credentials and establishes a session."""
            if not username_input.value or not password_input.value:
                ui.notify('Please fill in all fields!', type='warning')
                return

            login_btn.disable()
            spinner.visible = True

            try:
                with SessionLocal() as db:
                    user = crud.get_user_by_username(db, username_input.value)
                    
                    # Verify password against hashed database entry
                    if user and verify_password(password_input.value, str(user.password)):
                        # Store session data
                        app.storage.user.update({
                            'username': user.username,
                            'authenticated': True
                        })
                        ui.notify(f"Welcome back, {user.name}", type='positive')
                        ui.navigate.to('/dashboard') 
                    else:
                        ui.notify('Invalid username or password', type='negative')

            except Exception as e:
                ui.notify(f'Authentication Error: {str(e)}', type='negative')
            finally:
                spinner.visible = False
                login_btn.enable()

        # Primary Sign In Button
        login_btn = ui.button('SIGN IN', on_click=try_login).classes(
            'w-full mt-6 bg-[#0056B3] text-white font-bold'
        )

        # Navigation link for the Sign Up page
        with ui.row().classes('w-full justify-center mt-4'):
            ui.label("Don't have an account?").classes('text-sm text-gray-500')
            ui.link('Sign up', '/signup').classes('text-sm font-bold text-[#0056B3]')