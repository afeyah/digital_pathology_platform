# File: app/components/viewer_canvas.py

from nicegui import ui
from app.state import viewer_state
from app.database.create_database import SessionLocal
from app.database.models import ROI


def viewer_canvas():
    """
    OpenSeadragon viewer component.
    SAFE version for NiceGUI lifecycle.
    """

    # -----------------------------------------------------
    # Create container FIRST (important for NiceGUI)
    # -----------------------------------------------------
    with ui.column().classes('w-full h-full') as container:

        # Viewer HTML container
        ui.html(
            '<div id="openseadragon-viewer" '
            'style="width:100%; height:100%; background:#000;"></div>'
        ).classes('w-full h-full')

    # -----------------------------------------------------
    # Inject scripts ONLY after page render
    # -----------------------------------------------------
    ui.add_head_html("""
        <script src="https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/openseadragon.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/openseadragon-annotations@latest/dist/openseadragon-annotations.min.js"></script>
    """)

    # Delay execution so DOM exists (VERY IMPORTANT)
    ui.run_javascript("""
        setTimeout(() => {

            const viewer = OpenSeadragon({
                id: "openseadragon-viewer",
                prefixUrl:
                  "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/images/",
                tileSources: {
                    type: 'image',
                    url: 'https://images.fineartamerica.com/images/artworkimages/mediumprime/2/1-histology-of-human-tissue-science-photo-library.jpg'
                },
                showNavigationControl: true
            });

            const annotations = new OpenSeadragon.Annotations({
                viewer: viewer,
                showControls: true
            });

            annotations.on('annotation-created', function(event) {
                const bounds = event.annotation.getBounds();

                emitEvent('roi_to_db', {
                    x: bounds.x,
                    y: bounds.y,
                    width: bounds.width,
                    height: bounds.height
                });
            });

        }, 150);
    """)

    # -----------------------------------------------------
    # Python event listener (registered AFTER render)
    # -----------------------------------------------------
    ui.on('roi_to_db', lambda e: handle_save_roi(e.args or {}))


# =========================================================
# BACKEND HANDLER
# =========================================================
def handle_save_roi(data):
    """Save ROI to DB + update frontend state."""

    try:
        x = float(data.get('x', 0))
        y = float(data.get('y', 0))
        width = float(data.get('width', 0))
        height = float(data.get('height', 0))

        # update frontend state
        viewer_state.add_annotation({
            'x': x,
            'y': y,
            'w': width,
            'h': height,
        })

        # save to database
        with SessionLocal() as db:
            new_roi = ROI(
                report_id=1,  # TODO: replace with active report later
                coordinates={
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                },
            )
            db.add(new_roi)
            db.commit()

        ui.notify("ROI saved to database!", type='positive')

    except Exception as err:
        ui.notify(f"System Error: {err}", type='negative')
