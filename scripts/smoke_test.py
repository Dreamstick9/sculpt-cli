#!/usr/bin/env python3
"""Smoke test for sculpt package."""

import asyncio
from pathlib import Path
import sys

# Add package to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sculpt.config import config
from sculpt.models import GenerationParams, ModelName, InputType
from sculpt.router import ModelRouter
from sculpt.adapters import SF3DAdapter, TRELLIS2Adapter, Hi3DGenAdapter
from sculpt.cache import get_cache_store
from sculpt.output import validate_image, prepare_image


async def test_imports():
    """Test all imports work."""
    print("✓ Imports successful")


async def test_config():
    """Test config loading."""
    assert config.output_dir.exists() or config.output_dir == Path("./outputs")
    print("✓ Config loads")


async def test_models():
    """Test model enums and params."""
    params = GenerationParams(texture_resolution=1024, quality="high")
    assert params.texture_resolution == 1024
    assert params.quality == "high"
    
    assert ModelName.SF3D.value == "sf3d"
    assert ModelName.TRELLIS2.value == "trellis2"
    print("✓ Models and params work")


async def test_output_validation():
    """Test image validation."""
    # Create a tiny test image
    from PIL import Image
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGB", (512, 512), color="red")
        img.save(f.name, "PNG")
        
        valid, err = validate_image(Path(f.name))
        assert valid, f"Validation failed: {err}"
        
        prepared = prepare_image(Path(f.name))
        assert prepared.exists()
        print("✓ Image validation works")


async def test_cache_store():
    """Test cache store imports."""
    from sculpt.cache import get_cache_store
    cache = get_cache_store()
    stats = cache.stats()
    assert isinstance(stats, dict)
    print("✓ Cache store accessible")


async def test_router():
    """Test router imports."""
    from sculpt.router import ModelRouter
    router = ModelRouter()
    assert hasattr(router, 'pick_model')
    print("✓ Router imports")


async def main():
    """Run all smoke tests."""
    print("Running smoke tests...")
    print("=" * 40)
    
    await test_imports()
    await test_config()
    await test_models()
    await test_output_validation()
    await test_cache_store()
    await test_router()
    
    print("=" * 40)
    print("All smoke tests passed!")


if __name__ == "__main__":
    asyncio.run(main())