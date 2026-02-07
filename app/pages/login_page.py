from nicegui import ui


@ui.page('/login')
def login():
    """Login page for the Digital Pathology Platform."""
    with ui.card().classes('absolute-center w-96 p-6 shadow-lg'):
        ui.label('Login to Workbench').classes('text-2xl mb-4')

        username = ui.input('Username').classes('w-full')

        # Use password=True to hide input characters
        password = ui.input('Password', password=True).classes('w-full')

        ui.button(
            'Sign In',
            on_click=lambda: handle_login(username.value, password.value)
        ).classes('w-full mt-4 bg-[#0056B3]')


def handle_login(user, pwd):
    """Handle basic login validation and navigation."""
    if not user or not pwd:
        # Toast notification for validation error
        ui.notify('Please fill in all fields.', type='negative')
    else:
        # Later, authentication logic will be handled via api_service.py
        ui.notify(f'Welcome, {user}!', type='positive')
        ui.navigate.to('/dashboard')
