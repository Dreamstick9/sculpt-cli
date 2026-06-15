"""Core data models for sculpt."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ModelName(str, Enum):
    """Supported model slugs."""
    SF3D = "sf3d"
    TRELLIS2 = "trellis2"
    HI3DGEN = "hi3dgen"
    TRELLIS_TEXT = "trellis_text"
    TRIPO_SR = "triposr"
    TWO_STAGE = "two_stage"


class LicenseType(str, Enum):
    """License categories."""
    MIT = "MIT"
    STABILITY_COMMUNITY = "Stability Community (non-commercial OK)"
    TENCENT_NONCOMMERCIAL = "Tencent Non-Commercial (excluded from v1)"


class InputType(str, Enum):
    IMAGE = "image"
    TEXT = "text"
    MULTI_IMAGE = "multi_image"


@dataclass
class GenerationParams:
    """Parameters passed to the generation adapter."""
    texture_resolution: int = 1024
    remesh: str = "none"
    quality: str = "normal"
    geometry: str = "normal"
    fast: bool = False
    prompt: str = ""
    pipeline: str = "auto"
    force: bool = False
    timeout: int = 600
    model: str = "auto"
    
    def to_adapter_dict(self, model: ModelName) -> dict:
        """Convert to model-specific parameter dict."""
        base = {
            "texture_resolution": self.texture_resolution,
            "remesh_option": self.remesh,
        }
        if model == ModelName.HI3DGEN:
            base.update({"guidance": 7.5, "steps": 50})
        return base


@dataclass
class AdapterHealth:
    """Health state for a model adapter."""
    name: ModelName
    breaker_closed: bool = True
    last_success_ts: float = 0.0
    queue_wait_estimate_seconds: int = 30
    failure_count_window: int = 0
    last_error: str = ""


@dataclass 
class GenerationResult:
    """Result of a generation job."""
    local_path: Path
    model_used: ModelName
    input_type: InputType
    queue_wait_seconds: float = 0.0
    inference_seconds: float = 0.0
    cached: bool = False


class BaseAdapter(ABC):
    """Abstract base class for all model adapters."""
    
    name: ModelName
    license: LicenseType
    space_id: str
    api_name: str = "/generate"
    
    @abstractmethod
    async def generate(self, input_path: Path, params: GenerationParams) -> Path:
        """Generate 3D model, return local .glb path."""
        ...
    
    @abstractmethod
    async def health_check(self) -> AdapterHealth:
        """Check Space availability and estimate queue."""
        ...
    
    def can_handle(self, input_type: InputType) -> bool:
        """Whether this adapter can handle the input type."""
        if self.name == ModelName.TRELLIS_TEXT:
            return input_type == InputType.TEXT
        if self.name == ModelName.TWO_STAGE:
            return input_type == InputType.TEXT
        return input_type == InputType.IMAGE