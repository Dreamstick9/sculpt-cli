"""Configuration management for sculpt."""

import json
import os
from pathlib import Path
from typing import Any, Optional

import platformdirs

from .models import ModelName


CONFIG_DIR = Path(platformdirs.user_config_dir("sculpt"))
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path(platformdirs.user_cache_dir("sculpt"))
CACHE_FILE = CACHE_DIR / "cache.sqlite"
HEALTH_FILE = CACHE_DIR / "health.json"
LICENSES_FILE = CACHE_DIR / "licenses.json"


DEFAULT_OUTPUT_DIR = Path("./outputs")


class Config:
    """User configuration for sculpt."""
    
    def __init__(self):
        self.default_model: Optional[str] = None
        self.output_dir: Path = DEFAULT_OUTPUT_DIR
        self.hf_token: Optional[str] = None
        self._load()
    
    def _load(self) -> None:
        """Load config from disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                self.default_model = data.get("default_model")
                if data.get("output_dir"):
                    self.output_dir = Path(data["output_dir"]).expanduser()
                self.hf_token = data.get("hf_token")
            except (json.JSONDecodeError, KeyError):
                pass
    
    def save(self) -> None:
        """Save config to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "default_model": self.default_model,
            "output_dir": str(self.output_dir),
            "hf_token": self.hf_token,
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2))
    
    def get_default_model(self) -> Optional[ModelName]:
        """Get default model as enum."""
        if self.default_model:
            try:
                return ModelName(self.default_model)
            except ValueError:
                return None
        return None
    
    def set_default_model(self, model: ModelName) -> None:
        """Set default model."""
        self.default_model = model.value
        self.save()
    
    def set_output_dir(self, path: Path) -> None:
        """Set default output directory."""
        self.output_dir = path.expanduser()
        self.save()
    
    def set_hf_token(self, token: str) -> None:
        """Set Hugging Face token."""
        self.hf_token = token
        self.save()


# Global config instance
config = Config()


def get_config() -> Config:
    """Get global config instance."""
    return config