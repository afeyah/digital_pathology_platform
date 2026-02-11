# File: app/components/viewer_toolbar.py
from nicegui import ui

def viewer_toolbar():
    """
    Top toolbar component for the viewer page.
    Includes a Fullscreen toggle for better diagnostic focus.
    """
    with ui.row().classes('w-full items-center justify-between p-2 bg-white border-b shadow-sm'):
        # Left side: Tool Selection & Case Info
        with ui.row().classes('items-center gap-2'):
            ui.button(icon='pan_tool').props('flat round').classes('text-gray-600')
            ui.button(icon='edit').props('flat round').classes('text-gray-600')
            ui.separator().props('vertical')
            ui.label('Case #12345').classes('font-bold text-slate-700 ml-2')

        # Right side: Action Buttons (AI, Export, and Fullscreen)
        with ui.row().classes('items-center gap-3'):
            # Run AI Analysis Placeholder
            ui.button('Run AI Analysis', icon='psychology', 
                      on_click=lambda: ui.notify('Running AI...')).props('outline')

            # --- NEW: Fullscreen Toggle Button ---
            ui.button(icon='fullscreen', 
                      on_click=lambda: ui.run_javascript('document.documentElement.requestFullscreen()')) \
                .props('flat round').classes('text-gray-600')

            # Export Menu
            with ui.button(icon='download', color='secondary').props('flat round'):
                with ui.menu():
                    ui.menu_item('Export PDF', on_click=lambda: ui.notify('Exporting...'))
            
            ui.button(icon='settings').props('flat round').classes('text-gray-400')