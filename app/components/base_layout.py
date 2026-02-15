# File: app/components/base_layout.py
from nicegui import ui
from contextlib import contextmanager

@contextmanager
def base_page_layout(title: str):
    """
    Base layout for the Path-Benchmark Platform.
    Provides consistent navigation for Dashboard, Viewer, and Settings.
    """

    # 1. Header Section
    with ui.header().classes('items-center justify-between bg-[#0056B3] text-white shadow-md'):
        with ui.row().classes('items-center gap-4'):
            # Toggle for the Sidebar
            ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
            ui.label('Path-Benchmark Platform').classes('text-xl font-bold')

        with ui.row().classes('items-center'):
            # Quick Logout
            ui.button(icon='logout', on_click=lambda: ui.navigate.to('/login')) \
                .props('flat color=white') \
                .tooltip('Logout')

    # 2. Sidebar / Navigation Drawer (Task 3: Completing the site)
    with ui.left_drawer(value=False).classes('bg-[#F8FAFC] border-r') as left_drawer:
        with ui.list().classes('w-full'):
            ui.item_label('NAVIGATION').classes('text-xs text-gray-500 font-bold p-4')
            
            # Dashboard Link
            with ui.item(on_click=lambda: ui.navigate.to('/dashboard')).classes('hover:bg-blue-50'):
                with ui.item_section().props('avatar'):
                    ui.icon('dashboard', color='primary')
                with ui.item_section():
                    ui.item_label('Dashboard')

            # Viewer Link (Task 2: OpenSeadragon)
            with ui.item(on_click=lambda: ui.navigate.to('/viewer')).classes('hover:bg-blue-50'):
                with ui.item_section().props('avatar'):
                    ui.icon('microscope', color='primary')
                with ui.item_section():
                    ui.item_label('WSI Viewer')

            # Settings Link (Task 5: WSI Path Settings)
            with ui.item(on_click=lambda: ui.navigate.to('/settings')).classes('hover:bg-blue-50'):
                with ui.item_section().props('avatar'):
                    ui.icon('settings', color='primary')
                with ui.item_section():
                    ui.item_label('Settings')

    # 3. Main Page Container
    with ui.column().classes('w-full p-8 bg-[#F3F5F9] min-h-screen'):
        # Breadcrumb style header
        with ui.row().classes('items-center gap-2 mb-4'):
            ui.label('Home').classes('text-gray-400 text-sm')
            ui.label('/').classes('text-gray-400 text-sm')
            ui.label(title).classes('text-sm font-medium text-[#0056B3]')
        
        ui.label(title).classes('text-3xl font-bold text-[#333333] mb-6')
        
        yield  # Page-specific content is injected here