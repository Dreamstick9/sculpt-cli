"""Cache keyer utilities."""

import json
import hashlib
from pathlib import Path

from ..models import GenerationParams


def make_cache_key(image_path: Path, model: str, params: GenerationParams) -> str:
    """Generate deterministic cache key from image content + model + params."""
    # Hash image content
    with open(image_path, "rb") as f:
        image_hash = hashlib.sha256(f.read()).hexdigest()[:16]
    
    # Create deterministic params representation
    param_dict = {
        "texture_resolution": params.texture_resolution,
        "remesh": params.remesh,
        "quality": params.quality,
        "geometry": params.geometry,
        "fast": params.fast,
    }
    params_json = json.dumps(param_dict, sort_keys=True)
    params_hash = hashlib.sha256(params_json.encode()).hexdigest()[:16]
    
    return f"{image_hash}_{model}_{params_hash}"