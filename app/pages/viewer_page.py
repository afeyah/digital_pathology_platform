import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from nicegui import app, run, ui

from app.components.base_layout import base_page_layout
from app.database import crud
from app.database.create_database import SessionLocal
from app.database.models import WSI
from app.services.wsi_service import convert_svs_to_dzi, dzi_assets_exist

try:
    import openslide
except Exception:  # pragma: no cover - graceful fallback when openslide is unavailable
    openslide = None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _event_payload(args: Any) -> Dict[str, Any]:
    payload = args[0] if isinstance(args, (list, tuple)) and args else args
    return payload if isinstance(payload, dict) else {}


def _resolve_wsi(db, identifier: int) -> Optional[WSI]:
    # Route parameter is patient_id; prefer patient lookup to avoid id-collision
    # ambiguity between patient IDs and WSI IDs.
    by_patient_id = db.query(WSI).filter(WSI.patient_id == identifier).order_by(WSI.id.desc()).first()
    if by_patient_id:
        return by_patient_id
    return db.query(WSI).filter(WSI.id == identifier).first()


def _get_current_user_id(db) -> Optional[int]:
    username = app.storage.user.get('username')
    user = crud.get_user_by_username(db, username) if username else None
    return user.id if user else None


def _extract_slide_metadata(svs_full_path: str) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        'magnification': 'Unknown',
        'scan_date': 'Unknown',
        'width': 0,
        'height': 0,
    }
    if not os.path.exists(svs_full_path):
        return metadata

    # Fallback scan date from filesystem when embedded metadata is missing.
    metadata['scan_date'] = datetime.fromtimestamp(os.path.getmtime(svs_full_path)).strftime('%Y-%m-%d %H:%M:%S')

    if openslide is None:
        return metadata

    slide = None
    try:
        slide = openslide.OpenSlide(svs_full_path)
        metadata['width'], metadata['height'] = slide.dimensions
        props = slide.properties or {}

        magnification = (
            props.get('aperio.AppMag')
            or props.get('openslide.objective-power')
            or props.get('hamamatsu.SourceLens')
        )
        if magnification:
            magnification_text = str(magnification).strip()
            metadata['magnification'] = magnification_text if magnification_text.lower().endswith('x') else f'{magnification_text}x'

        scan_date = props.get('aperio.Date') or props.get('tiff.DateTime') or props.get('openslide.date')
        if scan_date:
            metadata['scan_date'] = str(scan_date)
    except Exception:
        pass
    finally:
        if slide is not None:
            slide.close()

    return metadata


def _load_report_rois(db, report_id: int) -> List[Dict[str, Any]]:
    rois: List[Dict[str, Any]] = []
    for roi in crud.get_rois_for_report(db, report_id):
        coords = roi.coordinates if isinstance(roi.coordinates, dict) else {}
        x = _safe_float(coords.get('x'))
        y = _safe_float(coords.get('y'))
        width = _safe_float(coords.get('width', coords.get('w')))
        height = _safe_float(coords.get('height', coords.get('h')))
        if width <= 0 or height <= 0:
            continue
        rois.append(
            {
                'id': int(roi.id),
                'x': x,
                'y': y,
                'width': width,
                'height': height,
            }
        )
    return rois


def normalize_roi_coordinates(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Normalize browser-captured ROI drag coordinates into original image scale.
    """
    image_start = payload.get('image_start') or {}
    image_end = payload.get('image_end') or {}

    x1 = _safe_float(image_start.get('x'))
    y1 = _safe_float(image_start.get('y'))
    x2 = _safe_float(image_end.get('x'))
    y2 = _safe_float(image_end.get('y'))

    x = min(x1, x2)
    y = min(y1, y2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)

    image_dimensions = payload.get('image_dimensions') or {}
    image_width = _safe_float(image_dimensions.get('width'))
    image_height = _safe_float(image_dimensions.get('height'))

    if image_width > 0:
        x = max(0.0, min(x, image_width))
        width = max(0.0, min(width, image_width - x))
    if image_height > 0:
        y = max(0.0, min(y, image_height))
        height = max(0.0, min(height, image_height - y))

    if width < 5 or height < 5:
        return None

    return {
        'x': round(x, 2),
        'y': round(y, 2),
        'width': round(width, 2),
        'height': round(height, 2),
        'screen_start': payload.get('screen_start') or {},
        'screen_end': payload.get('screen_end') or {},
    }


def trigger_ai_analysis(update_status=None, notify: bool = True) -> str:
    status = 'ANALYZED'
    if callable(update_status):
        update_status(status)
    if notify:
        ui.notify('AI Analysis placeholder: Success', type='positive')
    return status


def load_heatmap_overlay() -> str:
    ui.notify('Heatmap Ready (placeholder)', type='info')
    return 'Heatmap Ready'


@ui.page('/viewer')
def viewer_landing_page():
    ui.notify('Please select a slide from the dashboard')
    ui.navigate.to('/dashboard')


@ui.page('/viewer/{patient_id}')
def viewer_page(patient_id: int):
    try:
        identifier = int(patient_id)
    except (TypeError, ValueError):
        ui.notify('Invalid viewer identifier', type='negative')
        ui.navigate.to('/dashboard')
        return

    with SessionLocal() as db:
        wsi = _resolve_wsi(db, identifier)
        if not wsi:
            ui.notify('WSI record not found', type='negative')
            ui.navigate.to('/dashboard')
            return

        wsi_id = int(wsi.id)
        patient_ref = int(wsi.patient_id) if wsi.patient_id is not None else None
        file_path = (wsi.file_path or '').strip()
        if not file_path:
            ui.notify('WSI file path is missing', type='negative')
            ui.navigate.to('/dashboard')
            return
        case_id = getattr(wsi.patient, 'case_id', f'WSI-{wsi.id}')
        storage_path = crud.get_effective_path(db)
        report = crud.get_or_create_report_for_wsi(db, wsi_id, user_id=_get_current_user_id(db))
        report_id = int(report.id)
        roi_items: List[Dict[str, Any]] = _load_report_rois(db, report_id)

    svs_full_path = os.path.join(storage_path, file_path)
    base_name, _ = os.path.splitext(file_path)
    dzi_file_name = f'{base_name}.dzi'
    viewer_identifier = patient_ref if patient_ref is not None else identifier
    dzi_url = f"/dzi/{viewer_identifier}/{quote(dzi_file_name.replace('\\', '/').lstrip('/'), safe='/')}"

    metadata = _extract_slide_metadata(svs_full_path)
    viewer_key = f'wsi_{wsi_id}'
    viewer_container_id = f'openseadragon_{wsi_id}'
    roi_event_name = f'roi_saved_{wsi_id}'
    viewer_key_js = json.dumps(viewer_key)

    with base_page_layout(f'WSI Viewer - {case_id}'):
        async def generate_tiles_and_reload() -> None:
            ui.notify('Generating Deep Zoom tiles...', type='info')
            success = await run.io_bound(convert_svs_to_dzi, file_path, storage_path)
            if success and dzi_assets_exist(file_path, storage_path):
                ui.notify('Tiles generated successfully', type='positive')
                ui.navigate.to(f'/viewer/{viewer_identifier}')
            else:
                ui.notify('Failed to generate tiles', type='negative')

        if not dzi_assets_exist(file_path, storage_path):
            with ui.column().classes('w-full items-center gap-3 p-12 bg-white rounded shadow'):
                ui.label('Tiles not processed yet').classes('text-xl text-gray-700')
                ui.label(f'File: {file_path}').classes('text-sm text-gray-500')
                ui.button('Generate Tiles', on_click=generate_tiles_and_reload).classes('bg-[#0056B3] text-white')
                ui.button('Back to Dashboard', on_click=lambda: ui.navigate.to('/dashboard')).props('flat')
            return

        analysis_state = {'status': 'PENDING'}
        analysis_label: Optional[Any] = None

        def set_analysis_status(status: str) -> None:
            analysis_state['status'] = status
            if analysis_label is not None:
                analysis_label.set_text(f'AI Status: {status}')

        def refresh_saved_overlays() -> None:
            rois_js = json.dumps(
                [
                    {
                        'id': item['id'],
                        'x': item['x'],
                        'y': item['y'],
                        'width': item['width'],
                        'height': item['height'],
                    }
                    for item in roi_items
                ]
            )
            ui.run_javascript(
                f'''
                const viewerApi = window.digitalPathViewer?.[{viewer_key_js}];
                if (viewerApi) {{
                    viewerApi.renderSavedRois({rois_js});
                    viewerApi.forceRefresh?.();
                }}
                '''
            )

        def set_draw_mode(enabled: bool) -> None:
            js_bool = 'true' if enabled else 'false'
            ui.run_javascript(
                f'''
                const viewerApi = window.digitalPathViewer?.[{viewer_key_js}];
                if (viewerApi) {{
                    viewerApi.setDrawMode({js_bool});
                    viewerApi.forceRefresh?.();
                }}
                '''
            )

        def cancel_draft_roi() -> None:
            ui.run_javascript(
                f'''
                const viewerApi = window.digitalPathViewer?.[{viewer_key_js}];
                if (viewerApi) {{
                    viewerApi.cancelDraft();
                    viewerApi.forceRefresh?.();
                }}
                '''
            )
            ui.notify('Draft ROI canceled', type='warning')

        def delete_roi(roi_id: int) -> None:
            with SessionLocal() as db:
                deleted = crud.delete_roi(db, roi_id, report_id=report_id)
                if not deleted:
                    ui.notify('ROI not found in database', type='warning')
                    return

            roi_items[:] = [item for item in roi_items if item['id'] != roi_id]
            roi_list_component.refresh()
            refresh_saved_overlays()
            ui.notify(f'ROI #{roi_id} deleted', type='positive')

        @ui.refreshable
        def roi_list_component() -> None:
            if not roi_items:
                with ui.column().classes('w-full items-center py-3'):
                    ui.icon('crop_square').classes('text-gray-300')
                    ui.label('No saved ROIs').classes('text-sm text-gray-500 italic')
                return

            for item in roi_items:
                with ui.card().classes('w-full p-3 border-l-4 border-yellow-400'):
                    with ui.row().classes('w-full justify-between items-center'):
                        ui.label(f'ROI #{item["id"]}').classes('text-sm font-semibold')
                        ui.button(
                            icon='delete',
                            on_click=lambda _, rid=item['id']: delete_roi(rid),
                        ).props('flat round dense').classes('text-red-500')
                    ui.label(
                        f"Image Scale: x={item['x']:.1f}, y={item['y']:.1f}, w={item['width']:.1f}, h={item['height']:.1f}"
                    ).classes('text-xs text-gray-600 break-all')

        def handle_roi_saved(event) -> None:
            payload = _event_payload(event.args)
            normalized = normalize_roi_coordinates(payload)
            if normalized is None:
                ui.notify('ROI too small, please draw a larger box', type='warning')
                return

            with SessionLocal() as db:
                roi = crud.create_roi(db, report_id, normalized)

            roi_items.append(
                {
                    'id': int(roi.id),
                    'x': normalized['x'],
                    'y': normalized['y'],
                    'width': normalized['width'],
                    'height': normalized['height'],
                }
            )
            roi_list_component.refresh()
            refresh_saved_overlays()
            ui.notify(f'ROI #{int(roi.id)} saved', type='positive')

        ui.on(roi_event_name, handle_roi_saved)

        with ui.row().classes('w-full items-center justify-between gap-2 flex-wrap mb-2'):
            ui.label(f'Slide: {file_path}').classes('text-sm text-gray-600 break-all')
            with ui.row().classes('items-center gap-2 flex-wrap'):
                ui.switch('Draw ROI', value=False, on_change=lambda e: set_draw_mode(bool(e.value)))
                ui.button('Cancel Draft', icon='close', on_click=cancel_draft_roi).props('outline')
                ui.button(
                    'Run AI Analysis',
                    icon='psychology',
                    on_click=lambda: trigger_ai_analysis(update_status=set_analysis_status),
                ).props('outline')
                ui.button('Heatmap Overlay', icon='layers', on_click=load_heatmap_overlay).props('outline')
                ui.button('Back', icon='arrow_back', on_click=lambda: ui.navigate.to('/dashboard')).props('flat')

        with ui.row().classes('w-full items-start gap-4 flex-wrap'):
            with ui.card().classes('grow min-w-[320px] p-0 overflow-hidden'):
                ui.html(
                    f'<div id="{viewer_container_id}" style="width:100%; height:72vh; background:#111827; position:relative; z-index:1;"></div>'
                ).classes('w-full')

            with ui.column().classes('w-full max-w-[360px] gap-4'):
                with ui.card().classes('w-full'):
                    ui.label('Slide Metadata').classes('text-lg font-semibold')
                    ui.separator()
                    ui.label(f'Magnification Level: {metadata["magnification"]}').classes('text-sm')
                    ui.label(f'Scan Date: {metadata["scan_date"]}').classes('text-sm')
                    if metadata['width'] and metadata['height']:
                        ui.label(f'Image Size: {metadata["width"]} x {metadata["height"]} px').classes('text-xs text-gray-600')
                    if patient_ref is not None:
                        ui.label(f'Patient ID: {patient_ref}').classes('text-xs text-gray-500')

                with ui.card().classes('w-full'):
                    ui.label('ROI List').classes('text-lg font-semibold')
                    ui.separator()
                    roi_list_component()

                with ui.card().classes('w-full'):
                    ui.label('AI Analysis').classes('text-lg font-semibold')
                    ui.separator()
                    analysis_label = ui.label(f'AI Status: {analysis_state["status"]}').classes('text-sm')

        trigger_ai_analysis(update_status=set_analysis_status, notify=False)

        ui.add_head_html(
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/openseadragon.min.js"></script>'
        )

        init_payload = {
            'viewerKey': viewer_key,
            'containerId': viewer_container_id,
            'tileSource': dzi_url,
            'eventName': roi_event_name,
            'imageWidth': metadata['width'],
            'imageHeight': metadata['height'],
            'initialRois': [
                {
                    'id': item['id'],
                    'x': item['x'],
                    'y': item['y'],
                    'width': item['width'],
                    'height': item['height'],
                }
                for item in roi_items
            ],
        }

        init_script = """
        (() => {
            const cfg = __CFG__;
            window.digitalPathViewer = window.digitalPathViewer || {};

            const mountViewer = () => {
                const container = document.getElementById(cfg.containerId);
                if (!container || typeof OpenSeadragon === 'undefined' || typeof emitEvent !== 'function') {
                    return false;
                }

                const existingViewer = window.digitalPathViewer[cfg.viewerKey];
                if (existingViewer?.destroy) {
                    try {
                        existingViewer.destroy();
                    } catch (error) {
                    }
                } else if (existingViewer?.viewer) {
                    try {
                        existingViewer.viewer.destroy();
                    } catch (error) {
                    }
                }

                const viewer = OpenSeadragon({
                    id: cfg.containerId,
                    tileSources: cfg.tileSource,
                    prefixUrl: 'https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/images/',
                    showNavigator: true,
                    maxZoomPixelRatio: 2,
                    visibilityRatio: 0.8,
                    minZoomImageRatio: 0.9,
                    animationTime: 0.6,
                });

                const state = {
                    viewer,
                    drawMode: false,
                    dragging: false,
                    startScreen: null,
                    startImage: null,
                    draftElement: null,
                    savedElements: [],
                };
                let openAttempts = 0;
                let hasOpened = false;
                let resizeObserver = null;
                let resizeTimer = null;

                const ensureVisible = (element, fallbackDisplay = 'block') => {
                    if (!element) {
                        return;
                    }
                    const style = window.getComputedStyle(element);
                    if (style.display === 'none') {
                        element.style.display = fallbackDisplay;
                    }
                    if (style.visibility === 'hidden') {
                        element.style.visibility = 'visible';
                    }
                    if (Number(style.opacity) === 0) {
                        element.style.opacity = '1';
                    }
                };

                const forceViewerRefresh = () => {
                    try {
                        const containerElement = viewer.container || document.getElementById(cfg.containerId);
                        const rect = containerElement.getBoundingClientRect();
                        if (rect.width < 20 || rect.height < 20) {
                            return;
                        }
                        ensureVisible(containerElement);
                        ensureVisible(viewer.canvas);

                        if (containerElement) {
                            if (!containerElement.style.position) {
                                containerElement.style.position = 'relative';
                            }
                            if (!containerElement.style.width) {
                                containerElement.style.width = '100%';
                            }
                            if (!containerElement.style.height) {
                                containerElement.style.height = '72vh';
                            }
                            containerElement.style.zIndex = '1';
                        }
                        if (viewer.canvas) {
                            viewer.canvas.style.zIndex = '1';
                        }
                        if (viewer.overlaysContainer) {
                            viewer.overlaysContainer.style.zIndex = '10';
                        }

                        const size = viewer.viewport.getContainerSize ? viewer.viewport.getContainerSize() : null;
                        if (size && size.x > 10 && size.y > 10) {
                            viewer.viewport.resize();
                        } else if (!size && viewer.viewport.resize) {
                            viewer.viewport.resize();
                        }

                        if (typeof viewer.forceRedraw === 'function') {
                            viewer.forceRedraw();
                        }
                    } catch (error) {
                    }
                };

                const safeRefresh = () => {
                    clearTimeout(resizeTimer);
                    resizeTimer = setTimeout(() => {
                        forceViewerRefresh();
                    }, 80);
                };

                const resetWorldItems = () => {
                    if (!viewer.world) {
                        return;
                    }
                    if (typeof viewer.world.resetItems === 'function') {
                        viewer.world.resetItems();
                        return;
                    }
                    if (typeof viewer.world.removeAll === 'function') {
                        viewer.world.removeAll();
                    }
                };

                const openTileSource = () => {
                    openAttempts += 1;
                    try {
                        resetWorldItems();
                        viewer.open(cfg.tileSource);
                    } catch (error) {
                    }
                };

                const retryOpenIfNeeded = (delayMs = 220) => {
                    setTimeout(() => {
                        const count = viewer.world && typeof viewer.world.getItemCount === 'function'
                            ? viewer.world.getItemCount()
                            : 0;
                        if (!hasOpened && count === 0 && openAttempts < 4) {
                            openTileSource();
                            safeRefresh();
                            retryOpenIfNeeded(Math.min(delayMs * 2, 1200));
                        }
                    }, delayMs);
                };

                const openWhenContainerReady = (attempt = 0) => {
                    const rect = container.getBoundingClientRect();
                    if ((rect.width <= 0 || rect.height <= 0) && attempt < 24) {
                        setTimeout(() => openWhenContainerReady(attempt + 1), 80);
                        return;
                    }
                    safeRefresh();
                    openTileSource();
                    retryOpenIfNeeded();
                };

                const imageBounds = () => {
                    let width = Number(cfg.imageWidth || 0);
                    let height = Number(cfg.imageHeight || 0);
                    const firstItem = viewer.world.getItemAt(0);
                    if ((!width || !height) && firstItem) {
                        const size = firstItem.getContentSize();
                        width = size.x;
                        height = size.y;
                    }
                    return { width, height };
                };

                const clampPoint = (point) => {
                    const bounds = imageBounds();
                    let x = Number(point.x || 0);
                    let y = Number(point.y || 0);
                    if (bounds.width > 0) {
                        x = Math.max(0, Math.min(bounds.width, x));
                    }
                    if (bounds.height > 0) {
                        y = Math.max(0, Math.min(bounds.height, y));
                    }
                    return { x, y };
                };

                const toImagePoint = (clientX, clientY) => {
                    const rect = viewer.canvas.getBoundingClientRect();
                    const localPoint = new OpenSeadragon.Point(clientX - rect.left, clientY - rect.top);
                    const viewportPoint = viewer.viewport.pointFromPixel(localPoint);
                    const imagePoint = viewer.viewport.viewportToImageCoordinates(viewportPoint);
                    return clampPoint(imagePoint);
                };

                const toImageRect = (a, b) => {
                    const p1 = clampPoint(a);
                    const p2 = clampPoint(b);
                    const x = Math.min(p1.x, p2.x);
                    const y = Math.min(p1.y, p2.y);
                    return {
                        x,
                        y,
                        width: Math.abs(p2.x - p1.x),
                        height: Math.abs(p2.y - p1.y),
                    };
                };

                const removeDraft = () => {
                    if (!state.draftElement) {
                        return;
                    }
                    try {
                        viewer.removeOverlay(state.draftElement);
                    } catch (error) {
                    }
                    state.draftElement.remove();
                    state.draftElement = null;
                };

                const renderDraft = (rect) => {
                    removeDraft();
                    const draft = document.createElement('div');
                    draft.style.border = '2px dashed #FBBF24';
                    draft.style.background = 'rgba(250, 204, 21, 0.14)';
                    draft.style.boxSizing = 'border-box';
                    draft.style.pointerEvents = 'none';
                    draft.style.zIndex = '10';
                    const viewportRect = viewer.viewport.imageToViewportRectangle(
                        rect.x,
                        rect.y,
                        rect.width,
                        rect.height,
                    );
                    viewer.addOverlay({ element: draft, location: viewportRect });
                    state.draftElement = draft;
                };

                const clearSaved = () => {
                    state.savedElements.forEach((element) => {
                        try {
                            viewer.removeOverlay(element);
                        } catch (error) {
                        }
                        element.remove();
                    });
                    state.savedElements = [];
                };

                const renderSavedRois = (rois) => {
                    clearSaved();
                    if (!Array.isArray(rois)) {
                        safeRefresh();
                        return;
                    }
                    rois.forEach((roi) => {
                        const x = Number(roi.x || 0);
                        const y = Number(roi.y || 0);
                        const width = Number(roi.width || 0);
                        const height = Number(roi.height || 0);
                        if (width <= 0 || height <= 0) {
                            return;
                        }

                        const element = document.createElement('div');
                        element.style.border = '2px solid #FACC15';
                        element.style.background = 'rgba(250, 204, 21, 0.08)';
                        element.style.boxShadow = '0 0 0 1px rgba(255, 255, 255, 0.45) inset';
                        element.style.boxSizing = 'border-box';
                        element.style.pointerEvents = 'none';
                        element.style.zIndex = '10';

                        const viewportRect = viewer.viewport.imageToViewportRectangle(x, y, width, height);
                        viewer.addOverlay({ element, location: viewportRect });
                        state.savedElements.push(element);
                    });
                    safeRefresh();
                };

                const cancelDraft = () => {
                    removeDraft();
                    safeRefresh();
                };

                const setDrawMode = (enabled) => {
                    state.drawMode = Boolean(enabled);
                    state.dragging = false;
                    state.startImage = null;
                    state.startScreen = null;
                    viewer.setMouseNavEnabled(!state.drawMode);
                    viewer.canvas.style.cursor = state.drawMode ? 'crosshair' : 'grab';
                    if (!state.drawMode) {
                        removeDraft();
                    }
                    safeRefresh();
                    setTimeout(() => {
                        if (viewer.viewport?.resize) {
                            viewer.viewport.resize();
                        }
                        if (typeof viewer.forceRedraw === 'function') {
                            viewer.forceRedraw();
                        }
                    }, 50);
                    setTimeout(() => {
                        if (viewer.viewport?.resize) {
                            viewer.viewport.resize();
                        }
                        if (typeof viewer.forceRedraw === 'function') {
                            viewer.forceRedraw();
                        }
                    }, 150);
                };

                const tracker = new OpenSeadragon.MouseTracker({
                    element: viewer.canvas,
                    pressHandler: (event) => {
                        if (!state.drawMode) {
                            return;
                        }
                        if (typeof event.button === 'number' && event.button !== 0) {
                            return;
                        }
                        const original = event.originalEvent;
                        if (!original) {
                            return;
                        }

                        state.dragging = true;
                        state.startScreen = { x: original.clientX, y: original.clientY };
                        state.startImage = toImagePoint(original.clientX, original.clientY);
                        removeDraft();
                    },
                    dragHandler: (event) => {
                        if (!state.drawMode || !state.dragging || !state.startImage) {
                            return;
                        }
                        const original = event.originalEvent;
                        if (!original) {
                            return;
                        }
                        const currentImage = toImagePoint(original.clientX, original.clientY);
                        const draftRect = toImageRect(state.startImage, currentImage);
                        if (draftRect.width > 2 && draftRect.height > 2) {
                            renderDraft(draftRect);
                        }
                    },
                    releaseHandler: (event) => {
                        if (!state.drawMode || !state.dragging || !state.startImage || !state.startScreen) {
                            return;
                        }
                        state.dragging = false;

                        const original = event.originalEvent;
                        if (!original) {
                            removeDraft();
                            return;
                        }

                        const endScreen = { x: original.clientX, y: original.clientY };
                        const endImage = toImagePoint(original.clientX, original.clientY);
                        const rect = toImageRect(state.startImage, endImage);
                        removeDraft();

                        if (rect.width < 5 || rect.height < 5) {
                            state.startImage = null;
                            state.startScreen = null;
                            return;
                        }

                        emitEvent(cfg.eventName, {
                            screen_start: state.startScreen,
                            screen_end: endScreen,
                            image_start: state.startImage,
                            image_end: endImage,
                            image_dimensions: imageBounds(),
                        });

                        state.startImage = null;
                        state.startScreen = null;
                    },
                });
                tracker.setTracking(true);

                const onWindowResize = () => safeRefresh();
                const onFullscreenChange = () => safeRefresh();
                window.addEventListener('resize', onWindowResize);
                document.addEventListener('fullscreenchange', onFullscreenChange);

                const handleContainerResize = (entry) => {
                    const width = Number(entry?.contentRect?.width || 0);
                    const height = Number(entry?.contentRect?.height || 0);
                    if (width <= 0 || height <= 0) {
                        return;
                    }
                    if (viewer.viewport?.resize) {
                        viewer.viewport.resize();
                    }
                    if (typeof viewer.forceRedraw === 'function') {
                        viewer.forceRedraw();
                    }
                    safeRefresh();
                };

                if (typeof ResizeObserver !== 'undefined') {
                    resizeObserver = new ResizeObserver((entries) => {
                        for (const entry of entries) {
                            handleContainerResize(entry);
                        }
                    });
                    resizeObserver.observe(container);
                }

                const destroy = () => {
                    window.removeEventListener('resize', onWindowResize);
                    document.removeEventListener('fullscreenchange', onFullscreenChange);
                    if (resizeObserver) {
                        try {
                            resizeObserver.disconnect();
                        } catch (error) {
                        }
                        resizeObserver = null;
                    }
                    try {
                        tracker.destroy();
                    } catch (error) {
                    }
                    removeDraft();
                    clearSaved();
                    try {
                        viewer.destroy();
                    } catch (error) {
                    }
                };

                window.digitalPathViewer[cfg.viewerKey] = {
                    viewer,
                    setDrawMode,
                    cancelDraft,
                    renderSavedRois,
                    forceRefresh: safeRefresh,
                    destroy,
                };

                viewer.addHandler('open', () => {
                    hasOpened = true;
                    viewer.canvas.style.cursor = 'grab';
                    renderSavedRois(cfg.initialRois || []);
                    safeRefresh();
                });
                viewer.addHandler('open-failed', () => {
                    if (openAttempts < 4) {
                        setTimeout(() => {
                            openTileSource();
                            safeRefresh();
                        }, Math.min(250 * openAttempts, 1000));
                    }
                });
                viewer.addHandler('resize', safeRefresh);
                window.requestAnimationFrame(() => openWhenContainerReady());

                return true;
            };

            let retries = 0;
            const timer = setInterval(() => {
                retries += 1;
                if (mountViewer() || retries > 40) {
                    clearInterval(timer);
                }
            }, 75);
        })();
        """.replace('__CFG__', json.dumps(init_payload))

        ui.run_javascript(init_script)
