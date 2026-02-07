from nicegui import ui
from contextlib import contextmanager


@contextmanager
def base_page_layout(title: str):
    """
    Base layout for all pages in the Digital Pathology Platform.
    Provides a consistent header and page container.
    """

    # Main header - Uses blue color to match the Digital Pathology Platform identity
    with ui.header().classes('items-center justify-between bg-[#0056B3] text-white'):
        ui.label('Digital Pathology Platform').classes('text-xl font-bold')

        with ui.row():
            ui.button(
                'Dashboard',
                on_click=lambda: ui.navigate.to('/dashboard')
            ).props('flat color=white')

            ui.button(
                'Logout',
                on_click=lambda: ui.navigate.to('/login')
            ).props('flat color=white')

    # Page container
    with ui.column().classes('w-full p-8 bg-[#F3F5F9] min-h-screen'):
        ui.label(title).classes('text-2xl font-semibold text-[#333333]')
        yield  # Page-specific content will be inserted here
