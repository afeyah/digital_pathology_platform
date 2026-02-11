# File: app/state/viewer_state.py
from typing import List, Dict, Callable, Optional

# Global list to store ROI data: [{'x': 0, 'y': 0, 'w': 100, 'h': 100}, ...]
annotations: List[Dict[str, float]] = []

# Reference to the sidebar refresh function
refresh_sidebar_callback: Optional[Callable] = None

def add_annotation(new_box: Dict[str, float]):
    """Add a new ROI and trigger sidebar update"""
    annotations.append(new_box)
    if refresh_sidebar_callback:
        refresh_sidebar_callback()

def clear_annotations():
    """Clear all ROIs and trigger sidebar update"""
    annotations.clear()
    if refresh_sidebar_callback:
        refresh_sidebar_callback()