import os
import asyncio
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Optional

process_pool = ProcessPoolExecutor(max_workers=1)


async def run_tiling_process(file_name, storage_path):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        process_pool,
        convert_svs_to_dzi,
        file_name,
        storage_path,
    )

# -------------------------------------------------------------------------
# 1. OPENSLIDE SETUP FOR WINDOWS
# -------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
openslide_bin_path = os.path.join(BASE_DIR, 'libs', 'openslide-win64', 'bin')


if os.path.exists(openslide_bin_path):
    os.add_dll_directory(openslide_bin_path)

import openslide
from openslide.deepzoom import DeepZoomGenerator

# -------------------------------------------------------------------------
# 2. CORE LOGIC: DEEP ZOOM GENERATION
# -------------------------------------------------------------------------

def _emit_progress(progress_callback: Optional[Callable[[float], None]], value: float) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(max(0.0, min(1.0, float(value))))
    except Exception:
        # Progress updates should never break tiling.
        pass


def convert_svs_to_dzi(
    svs_file_name: str,
    storage_folder: str,
    progress_callback: Optional[Callable[[float], None]] = None,
):
    """
    Generates Deep Zoom Image (DZI) tiles from an SVS file.
    Required for high-performance viewing in OpenSeadragon [cite: 2026-02-18].
    
    Args:
        svs_file_name (str): Nama file .svs di folder storage.
        storage_folder (str): Jalur folder (biasanya di Documents).
    """
    if not isinstance(svs_file_name, str) or not svs_file_name.strip():
        print('Deep Zoom Error: invalid SVS file name')
        return False
    if not isinstance(storage_folder, str) or not storage_folder.strip():
        print('Deep Zoom Error: invalid storage folder')
        return False

    slide = None
    try:
        _emit_progress(progress_callback, 0.0)
        svs_path = os.path.join(storage_folder, svs_file_name)
        if not os.path.exists(svs_path):
            print(f'Error: File not found at {svs_path}')
            return False

        slide = openslide.OpenSlide(svs_path)
        tiles = DeepZoomGenerator(slide, tile_size=256, overlap=1, limit_bounds=False)

        base_name = os.path.splitext(svs_file_name)[0]
        dzi_path = os.path.join(storage_folder, f'{base_name}.dzi')
        folder_path = os.path.join(storage_folder, f'{base_name}_files')

        with open(dzi_path, 'w', encoding='utf-8') as f:
            f.write(tiles.get_dzi('jpeg'))

        os.makedirs(folder_path, exist_ok=True)
        total_tiles = 0
        for level in range(tiles.level_count):
            cols, rows = tiles.level_tiles[level]
            total_tiles += cols * rows

        processed_tiles = 0

        for level in range(tiles.level_count):
            level_dir = os.path.join(folder_path, str(level))
            os.makedirs(level_dir, exist_ok=True)

            cols, rows = tiles.level_tiles[level]
            for col in range(cols):
                for row in range(rows):
                    processed_tiles += 1
                    tile_path = os.path.join(level_dir, f'{col}_{row}.jpeg')
                    if os.path.exists(tile_path):
                        if total_tiles > 0 and processed_tiles % 16 == 0:
                            _emit_progress(progress_callback, processed_tiles / total_tiles)
                        continue

                    tile = None
                    try:
                        tile = tiles.get_tile(level, (col, row))
                        tile.save(tile_path, 'JPEG', quality=90)
                    finally:
                        if tile is not None and hasattr(tile, 'close'):
                            tile.close()

                    if total_tiles > 0 and processed_tiles % 16 == 0:
                        _emit_progress(progress_callback, processed_tiles / total_tiles)

                    if processed_tiles % 32 == 0:
                        time.sleep(0.01)

        _emit_progress(progress_callback, 1.0)
        print(f'Success: Deep Zoom Tiles created for {svs_file_name}')
        return True
    except Exception as e:
        print(f'Deep Zoom Error: {str(e)}')
        return False
    finally:
        if slide is not None:
            try:
                slide.close()
            except Exception:
                pass


def get_dzi_paths(svs_file_name: str, storage_folder: str):
    """Return expected DZI file path and Deep Zoom tile folder path."""
    base_name = os.path.splitext(svs_file_name)[0]
    dzi_path = os.path.join(storage_folder, f"{base_name}.dzi")
    tiles_dir = os.path.join(storage_folder, f"{base_name}_files")
    return dzi_path, tiles_dir


def dzi_assets_exist(svs_file_name: str, storage_folder: str) -> bool:
    """Check if both .dzi descriptor and tile folder exist."""
    dzi_path, tiles_dir = get_dzi_paths(svs_file_name, storage_folder)
    if not os.path.exists(dzi_path):
        return False
    if not os.path.isdir(tiles_dir):
        return False
    try:
        return any(os.scandir(tiles_dir))
    except Exception:
        return False


async def wait_for_dzi_assets(
    svs_file_name: str,
    storage_folder: str,
    timeout_seconds: float = 3.0,
    poll_interval: float = 0.1,
) -> bool:
    """
    Poll for DZI artifacts with cooperative sleep to keep the event loop responsive.
    """
    elapsed = 0.0
    while elapsed <= timeout_seconds:
        if dzi_assets_exist(svs_file_name, storage_folder):
            return True
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return False

# -------------------------------------------------------------------------
# 3. AI ANALYSIS PLACEHOLDER
# -------------------------------------------------------------------------

def generate_heatmap_layer(wsi_id, storage_folder):
    """
    Placeholder for future AI Multiple Instance Learning (MIL) analysis.
    Will generate heatmap overlays for tumor detection in Task 3.
    """
    print(f"Starting AI analysis for WSI ID: {wsi_id} in {storage_folder}")
    
    return True
