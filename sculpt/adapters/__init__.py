"""Adapters package exports."""

from .base import BaseAdapter
from .sf3d import SF3DAdapter
from .trellis2 import TRELLIS2Adapter
from .hi3dgen import Hi3DGenAdapter
from .trellis_text import TRELLISTextAdapter
from .triposr import TripoSRAdapter
from .two_stage import TwoStageAdapter

__all__ = [
    "BaseAdapter",
    "SF3DAdapter",
    "TRELLIS2Adapter",
    "Hi3DGenAdapter",
    "TRELLISTextAdapter",
    "TripoSRAdapter",
    "TwoStageAdapter",
]

ADAPTER_REGISTRY = {}