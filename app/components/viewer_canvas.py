# File: app/components/viewer_canvas.py
from nicegui import ui
from app.state import viewer_state
from app.database import crud
from app.database.create_database import SessionLocal

def viewer_canvas():
    """
    Advanced WSI Viewer with OSD and Database Persistence.
    Menghubungkan anotasi frontend ke backend database.
    """
    # 1. Load OSD and Annotation Plugin
    ui.add_head_html('<script src="https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/openseadragon.min.js"></script>')
    ui.add_head_html('<script src="https://cdn.jsdelivr.net/npm/openseadragon-annotations@latest/dist/openseadragon-annotations.min.js"></script>')

    # 2. Container for the viewer
    ui.html('<div id="openseadragon-viewer" style="width: 100%; height: 100%; background: #000;"></div>') \
        .classes('w-full h-full')

    # 3. OpenSeadragon Initialization Script
    ui.run_javascript('''
        var viewer = OpenSeadragon({
            id: "openseadragon-viewer",
            prefixUrl: "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/images/",
            tileSources: {
                type: 'image',
                url: 'https://images.fineartamerica.com/images/artworkimages/mediumprime/2/1-histology-of-human-tissue-science-photo-library.jpg'
            },
            showNavigationControl: true
        });

        var annotations = new OpenSeadragon.Annotations({
            viewer: viewer,
            showControls: true
        });

        // Event listener: Mengirim data koordinat ke Python saat kotak selesai digambar
        annotations.on('annotation-created', function(event) {
            const bounds = event.annotation.getBounds();
            emitEvent('roi_to_db', {
                x: bounds.x, 
                y: bounds.y, 
                width: bounds.width, 
                height: bounds.height
            });
        });
    ''')


    ui.on('roi_to_db', lambda e: handle_save_roi(e.args))

async def handle_save_roi(data):
    """
    Menyimpan koordinat ROI ke database dan memperbarui state global.
    """
    try:

        viewer_state.add_annotation({
            'x': data['x'], 'y': data['y'], 
            'w': data['width'], 'h': data['height']
        })


        with SessionLocal() as db:
            success = await crud.save_roi(
                db=db,            
                report_id=1,       
                coordinates=data  
            )

        if success:
            ui.notify("ROI saved to database!", type='positive')
        else:
            ui.notify("Database error: Could not save ROI", type='negative')

    except Exception as err:
        ui.notify(f"System Error: {str(err)}", type='negative')