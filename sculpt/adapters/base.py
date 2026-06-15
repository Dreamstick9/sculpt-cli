"""Base adapter abstract class."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from ..models import BaseAdapter as ModelsBaseAdapter, AdapterHealth, ModelName, LicenseType, GenerationParams

if TYPE_CHECKING:
    from ..models import GenerationParams


class BaseAdapter(ModelsBaseAdapter, ABC):
    """Base class for all model adapters."""
    
    name: ModelName
    license: LicenseType
    space_id: str
    api_name: str = "/generate"
    
    def __init__(self):
        self._client = None
    
    @abstractmethod
    async def generate(self, input_path: Path, params: GenerationParams) -> Path:
        """Generate 3D model, return local .glb path."""
        ...
    
    @abstractmethod
    async def health_check(self) -> AdapterHealth:
        """Check Space availability and estimate queue."""
        ...
    
    def can_handle(self, input_type: str) -> bool:
        """Whether this adapter can handle the input type."""
        from ..models import InputType, ModelName
        if self.name == ModelName.TRELLIS_TEXT:
            return input_type == InputType.TEXT
        if self.name == ModelName.TWO_STAGE:
            return input_type == InputType.TEXT
        return input_type == InputType.IMAGE