# File: app/components/viewer_sidebar.py

from nicegui import ui
from app.state import viewer_state


def viewer_sidebar():
    """
    Main Sidebar layout for the viewer page.
    Safe version (no global UI creation).
    """

    # -----------------------------------------------------
    # REFRESHABLE COMPONENT (defined INSIDE function)
    # -----------------------------------------------------
    @ui.refreshable
    def roi_list_component():
        with ui.column().classes('w-full gap-2'):

            if not viewer_state.annotations:
                with ui.column().classes('w-full items-center py-4'):
                    ui.icon('layers', size='lg').classes('text-gray-300')
                    ui.label('No ROIs drawn yet') \
                        .classes('text-gray-400 italic text-sm')
            else:
                for i, ann in enumerate(viewer_state.annotations):
                    with ui.card().classes(
                        'w-full p-2 bg-slate-50 border-l-4 border-primary'
                    ):
                        with ui.row().classes(
                            'w-full justify-between items-center'
                        ):
                            ui.label(f'ROI #{i+1}') \
                                .classes('font-bold text-xs text-primary')

                            ui.button(
                                icon='delete',
                                on_click=lambda _, idx=i: remove_roi(idx)
                            ).props('flat round dense') \
                             .classes('text-red-400')

                        ui.label(
                            f"Pos: ({ann['x']:.0f}, {ann['y']:.0f})"
                        ).classes('text-[10px] text-gray-600')

                        ui.label(
                            f"Size: {ann['w']:.0f} x {ann['h']:.0f}"
                        ).classes('text-[10px] text-gray-600')

    # connect refresh callback
    viewer_state.refresh_sidebar_callback = roi_list_component.refresh

    # -----------------------------------------------------
    # Sidebar Layout
    # -----------------------------------------------------
    with ui.column().classes('w-full p-4 gap-4'):

        # Metadata
        with ui.card().classes('w-full shadow-none border'):
            ui.label('Slide Metadata').classes('text-lg font-bold text-primary')
            ui.separator()
            ui.label('Magnification: 40x').classes('text-sm font-medium mt-2')

        # ROI Section
        with ui.card().classes('w-full shadow-none border'):
            ui.label('ROI List').classes('text-lg font-bold text-primary')
            ui.separator()
            roi_list_component()

        # AI Section
        with ui.card().classes('w-full shadow-none border bg-blue-50'):
            ui.label('AI Analysis').classes('text-lg font-bold text-blue-800')
            ui.separator()
            ui.label('Status: Ready for MIL/CLAM') \
                .classes('text-sm italic mt-2')


def remove_roi(index: int):
    if 0 <= index < len(viewer_state.annotations):
        viewer_state.annotations.pop(index)
        if callable(viewer_state.refresh_sidebar_callback):
            viewer_state.refresh_sidebar_callback()
