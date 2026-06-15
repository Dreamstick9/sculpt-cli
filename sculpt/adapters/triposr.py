"""TripoSR adapter (fallback)."""

import asyncio
import time
from pathlib import Path

from gradio_client import Client as GradioClient, handle_file

from .base import BaseAdapter
from ..models import ModelName, LicenseType, GenerationParams, AdapterHealth


class TripoSRAdapter(BaseAdapter):
    """Adapter for stabilityai/TripoSR Space."""
    
    name = ModelName.TRIPO_SR
    license = LicenseType.MIT
    space_id = "stabilityai/TripoSR"
    api_name = "/generate"
    
    def __init__(self, hf_token: str | None = None):
        super().__init__()
        self.hf_token = hf_token
    
    async def generate(self, input_path: Path, params: GenerationParams) -> Path:
        """Generate 3D model using TripoSR."""
        loop = asyncio.get_event_loop()
        
        def _sync_generate():
            client = GradioClient(self.space_id, hf_token=self.hf_token)
            
            job = client.submit(
                image=handle_file(str(input_path)),
                remove_background=True,
                foreground_ratio=0.85,
                marching_cubes_resolution=256,
                api_name=self.api_name,
            )
            
            while True:
                status = job.status()
                if status.code.value == "completed":
                    return job.result()
                elif status.code.value in ("failed", "error"):
                    raise RuntimeError(f"TripoSR generation failed: {status}")
                time.sleep(2)
        
        result = await asyncio.get_event_loop().run_in_executor(None, _sync_generate)
        return Path(result)
    
    async def health_check(self) -> AdapterHealth:
        from ..models import AdapterHealth
        import time
        
        health = AdapterHealth(name=self.name)
        
        try:
            client = GradioClient(self.space_id, hf_token=self.hf_token)
            await asyncio.get_event_loop().run_in_executor(None, client.view_api)
            health.breaker_closed = True
            health.last_success_ts = time.time()
            health.queue_wait_estimate_seconds = 20
        except Exception as e:
            health.breaker_closed = False
            health.last_error = str(e)
        
        return health