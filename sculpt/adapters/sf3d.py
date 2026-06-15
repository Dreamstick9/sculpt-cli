"""Stable Fast 3D adapter."""

import asyncio
import time
from pathlib import Path

from gradio_client import Client as GradioClient, handle_file

from .base import BaseAdapter
from ..models import ModelName, LicenseType, GenerationParams, AdapterHealth


class SF3DAdapter(BaseAdapter):
    """Adapter for stabilityai/stable-fast-3d Space."""
    
    name = ModelName.SF3D
    license = LicenseType.STABILITY_COMMUNITY
    space_id = "stabilityai/stable-fast-3d"
    api_name = "/generate"
    
    def __init__(self, hf_token: str | None = None):
        super().__init__()
        self.hf_token = hf_token
    
    async def generate(self, input_path: Path, params: GenerationParams) -> Path:
        """Generate 3D model using SF3D."""
        loop = asyncio.get_event_loop()
        
        def _sync_generate():
            client = GradioClient(self.space_id, hf_token=self.hf_token)
            job = client.submit(
                image=handle_file(str(input_path)),
                texture_resolution=params.texture_resolution,
                remesh_option=params.remesh,
                api_name=self.api_name,
            )
            
            # Poll for completion
            while True:
                status = job.status()
                if status.code.value == "completed":
                    return job.result()
                elif status.code.value in ("failed", "error"):
                    raise RuntimeError(f"SF3D generation failed: {status}")
                time.sleep(2)
        
        result = await loop.run_in_executor(None, _sync_generate)
        
        # Result is path to downloaded .glb file
        return Path(result)
    
    async def health_check(self) -> AdapterHealth:
        """Check SF3D Space health."""
        health = AdapterHealth(name=self.name)
        
        try:
            client = GradioClient(self.space_id, hf_token=self.hf_token)
            start = time.time()
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, client.view_api),
                timeout=15.0
            )
            health.breaker_closed = True
            health.last_success_ts = time.time()
            health.queue_wait_estimate_seconds = 30
        except Exception as e:
            health.breaker_closed = False
            health.last_error = str(e)
        
        return health