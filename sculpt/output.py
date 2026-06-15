"""Output management for sculpt."""

import hashlib
import mimetypes
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from .models import GenerationParams, ModelName


class OutputManager:
    """Manages local file output and caching."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path.cwd() / "outputs"
    
    def save(self, temp_path: Path, input_path: Optional[Path], model: ModelName, 
             params: GenerationParams, force: bool = False) -> Path:
        """
        Save generated .glb to permanent location.
        
        Naming: <input_stem>__<model_slug>[_<param_hash>].glb
        For text input, uses "prompt" as stem.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build output filename
        if input_path and input_path.exists():
            base_stem = input_path.stem
        else:
            base_stem = "prompt"
        
        param_str = f"{model.value}_{params.texture_resolution}_{params.remesh}_{params.quality}"
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
        
        base_name = f"{base_stem}__{model.value}"
        if param_hash != hashlib.md5(f"{model.value}_1024_none_normal".encode()).hexdigest()[:8]:
            base_name += f"_{param_hash}"
        
        target = self.output_dir / f"{base_name}.glb"
        
        # Idempotent: if exists and not forcing, return existing
        if target.exists() and not force:
            return target
        
        # Move temp file to final location
        shutil.move(str(temp_path), str(target))
        return target
    
    def get_existing(self, input_path: Path, model: ModelName, 
                     params: GenerationParams) -> Optional[Path]:
        """Check if output already exists for this input+model+params."""
        param_str = f"{model.value}_{params.texture_resolution}_{params.remesh}_{params.quality}"
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
        
        base_name = f"{input_path.stem}__{model.value}"
        if param_hash != hashlib.md5(f"{model.value}_1024_none_normal".encode()).hexdigest()[:8]:
            base_name += f"_{param_hash}"
        
        target = self.output_dir / f"{base_name}.glb"
        return target if target.exists() else None


def validate_image(path: Path) -> tuple[bool, str]:
    """Validate image file. Returns (is_valid, error_message)."""
    if not path.exists():
        return False, f"File not found: {path}"
    
    # Check size
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > 20:
        return False, f"Image too large: {size_mb:.1f}MB (max 20MB)"
    
    # Check MIME type
    mime, _ = mimetypes.guess_type(str(path))
    if mime and not mime.startswith("image/"):
        return False, f"Not an image file: {mime}"
    
    # Check dimensions (requires PIL)
    try:
        from PIL import Image
        with Image.open(path) as img:
            w, h = img.size
            min_dim = min(w, h)
            max_dim = max(w, h)
            if min_dim < 128:
                return False, f"Image too small: {min_dim}px minimum dimension (need >= 128px)"
            if max_dim > 4096:
                # We'll resize, just warn
                pass
    except Exception:
        pass  # PIL not available, skip dimension check
    
    return True, ""


def prepare_image(path: Path, max_dim: int = 1024) -> Path:
    """Resize image if too large, return path to processed image."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            if img.mode in ("RGBA", "LA", "PA"):
                # Preserve alpha
                pass
            elif img.mode != "RGB":
                img = img.convert("RGB")
            
            w, h = img.size
            if max(w, h) <= max_dim:
                return path
            
            # Resize maintaining aspect ratio
            if w > h:
                new_w = max_dim
                new_h = int(h * max_dim / w)
            else:
                new_h = max_dim
                new_w = int(w * max_dim / h)
            
            img = img.resize((new_w, new_h), Image.LANCZOS)
            
            # Save to temp location
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                img.save(tmp.name, "PNG")
                return Path(tmp.name)
    except Exception:
        # If PIL fails, return original
        pass
    
    return path