# File: app/components/viewer_sidebar.py
from nicegui import ui
from app.state import viewer_state

@ui.refreshable
def roi_list_component():
    """
    Component to display the list of Regions of Interest (ROIs).
    Refreshes automatically when viewer_state.annotations changes.
    """
    with ui.column().classes('w-full gap-2'):
        if not viewer_state.annotations:
            # Empty state UI
            with ui.column().classes('w-full items-center py-4'):
                ui.icon('layers', size='lg').classes('text-gray-300')
                ui.label('No ROIs drawn yet').classes('text-gray-400 italic text-sm')
        else:
            # Render a card for each ROI
            for i, ann in enumerate(viewer_state.annotations):
                with ui.card().classes('w-full p-2 bg-slate-50 border-l-4 border-primary'):
                    with ui.row().classes('w-full justify-between items-center'):
                        ui.label(f'ROI #{i+1}').classes('font-bold text-xs text-primary')
                        
                        # FIX: Added '_' to capture the ClickEventArguments and ignore it.
                        # This ensures 'idx' keeps its default integer value 'i'.
                        ui.button(icon='delete', on_click=lambda _, idx=i: remove_roi(idx)) \
                            .props('flat round dense').classes('text-red-400')
                    
                    # Displaying coordinates captured in Week 6
                    ui.label(f"Pos: ({ann['x']:.0f}, {ann['y']:.0f})").classes('text-[10px] text-gray-600')
                    ui.label(f"Size: {ann['w']:.0f} x {ann['h']:.0f}").classes('text-[10px] text-gray-600')

def remove_roi(index: int):
    """
    Remove an ROI from the global state by its index.
    Triggers UI refresh via roi_list_component.refresh().
    """
    if 0 <= index < len(viewer_state.annotations):
        viewer_state.annotations.pop(index)
        roi_list_component.refresh()

def viewer_sidebar():
    """
    Main Sidebar layout for the viewer page.
    Initializes the refresh callback for real-time updates.
    """
    # Map the refresh function to the global state callback
    viewer_state.refresh_sidebar_callback = roi_list_component.refresh

    with ui.column().classes('w-full p-4 gap-4'):
        # Slide Metadata Section
        with ui.card().classes('w-full shadow-none border'):
            ui.label('Slide Metadata').classes('text-lg font-bold text-primary')
            ui.separator()
            ui.label('Magnification: 40x').classes('text-sm font-medium mt-2')

        # ROI Management Section
        with ui.card().classes('w-full shadow-none border'):
            ui.label('ROI List').classes('text-lg font-bold text-primary')
            ui.separator()
            roi_list_component()

        # AI Prediction Placeholder
        with ui.card().classes('w-full shadow-none border bg-blue-50'):
            ui.label('AI Analysis').classes('text-lg font-bold text-blue-800')
            ui.separator()
            ui.label('Status: Ready for MIL/CLAM').classes('text-sm italic mt-2')