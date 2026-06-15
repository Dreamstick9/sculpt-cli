"""Tests for sculpt package."""

import pytest
from pathlib import Path
import tempfile
from PIL import Image

from sculpt.models import GenerationParams, ModelName, InputType, AdapterHealth
from sculpt.config import Config
from sculpt.output import validate_image, prepare_image
from sculpt.cache import get_cache_store
from sculpt.cache.keyer import make_cache_key
from sculpt.router import ModelRouter


class TestModels:
    """Test model enums and params."""
    
    def test_model_names(self):
        assert ModelName.SF3D.value == "sf3d"
        assert ModelName.TRELLIS2.value == "trellis2"
        assert ModelName.HI3DGEN.value == "hi3dgen"
        assert ModelName.TRELLIS_TEXT.value == "trellis_text"
        assert ModelName.TRIPO_SR.value == "triposr"
        assert ModelName.TWO_STAGE.value == "two_stage"
    
    def test_generation_params(self):
        params = GenerationParams(
            texture_resolution=1024,
            quality="high",
            model="sf3d"
        )
        assert params.texture_resolution == 1024
        assert params.quality == "high"
        assert params.model == "sf3d"
    
    def test_input_types(self):
        assert InputType.IMAGE.value == "image"
        assert InputType.TEXT.value == "text"
        assert InputType.MULTI_IMAGE.value == "multi_image"


class TestConfig:
    """Test config management."""
    
    def test_config_creation(self, tmp_path):
        config = Config()
        assert config.output_dir == Path("./outputs")
        assert config.default_model is None
        assert config.hf_token is None


class TestCacheKey:
    """Test cache key generation."""
    
    def test_cache_key_deterministic(self, tmp_path):
        # Create test image
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (256, 256), color="blue")
            img.save(f.name, "PNG")
            img_path = Path(f.name)
        
        params = GenerationParams(texture_resolution=1024, quality="normal")
        key1 = make_cache_key(img_path, "sf3d", params)
        key2 = make_cache_key(img_path, "sf3d", params)
        
        assert key1 == key2
        assert len(key1) > 0


class TestImageValidation:
    """Test image validation utilities."""
    
    def test_valid_image(self, tmp_path):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (512, 512), color="red")
            img.save(f.name, "PNG")
            
            valid, err = validate_image(Path(f.name))
            assert valid is True
            assert err == ""
    
    def test_invalid_image(self, tmp_path):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not an image")
            f.flush()
            
            valid, err = validate_image(Path(f.name))
            # txt files fail MIME check
            assert valid is False
    
    def test_prepare_image(self, tmp_path):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (2048, 2048), color="green")
            img.save(f.name, "PNG")
            
            prepared = prepare_image(Path(f.name), max_dim=512)
            assert prepared.exists()
            
            with Image.open(prepared) as img:
                assert max(img.size) <= 512


class TestRouter:
    """Test model router."""
    
    def test_router_creation(self):
        router = ModelRouter()
        assert hasattr(router, 'pick_model')
        assert hasattr(router, 'register')


class TestCacheStore:
    """Test cache store."""
    
    def test_cache_stats(self, tmp_path):
        from sculpt.cache import CacheStore
        store = CacheStore(tmp_path / "test_cache.sqlite")
        stats = store.stats()
        assert "entries" in stats
        assert "total_bytes" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])