from nicegui import ui
from app.services.api_service import api


@ui.page('/login')
def login_page():
    with ui.card().classes('absolute-center w-96 p-8 shadow-lg'):
        ui.label('Digital Pathology Workbench').classes(
            'text-2xl font-bold mb-4 text-[#333333]'
        )

        # Input Fields
        username = ui.input('Username').classes('w-full')
        password = ui.input('Password', password=True).classes('w-full')

        # Use the `visible` property for the spinner
        spinner = ui.spinner(size='lg', color='#2563EB').classes('mt-4')
        spinner.visible = False  # initially hidden

        async def try_login():
            # Input validation
            if not username.value or not password.value:
                ui.notify('Please fill in all fields!', type='warning')
                return

            # Start login process: disable button & show spinner
            login_btn.disable()
            spinner.visible = True

            try:
                # Call API asynchronously [cite: 49]
                result = await api.login(username.value, password.value)

                if result['success']:
                    ui.notify(f"Welcome, {result['data']['name']}", type='positive')
                    ui.navigate.to('/dashboard')
                else:
                    ui.notify(result['error'], type='negative')

            except Exception as e:
                ui.notify(f'System error occurred: {str(e)}', type='negative')

            finally:
                # Reset UI regardless of outcome
                spinner.visible = False
                login_btn.enable()

        login_btn = ui.button('Sign In', on_click=try_login).classes(
            'w-full mt-6 bg-[#0056B3]'
        )
