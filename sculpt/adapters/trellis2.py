"""TRELLIS.2 adapter."""

import asyncio
import time
from pathlib import Path

from gradio_client import Client as GradioClient, handle_file

from .base import BaseAdapter
from ..models import ModelName, LicenseType, GenerationParams, AdapterHealth


class TRELLIS2Adapter(BaseAdapter):
    """Adapter for microsoft/TRELLIS.2 Space."""
    
    name = ModelName.TRELLIS2
    license = LicenseType.MIT
    space_id = "microsoft/TRELLIS.2"
    api_name = "/generate"
    
    def __init__(self, hf_token: str | None = None):
        super().__init__()
        self.hf_token = hf_token
    
    async def generate(self, input_path: Path, params: GenerationParams) -> Path:
        """Generate 3D model using TRELLIS.2."""
        loop = asyncio.get_event_loop()
        
        def _sync_generate():
            client = GradioClient(self.space_id, hf_token=self.hf_token)
            
            # TRELLIS.2 API parameters (from Space "Use via API")
            job = client.submit(
                image=handle_file(str(input_path)),
                seed=-1,
                ss_guidance_strength=7.5,
                ss_sampling_steps=12,
                slat_guidance_strength=3.0,
                slat_sampling_steps=12,
                simplify=0.95,
                texture_size=params.texture_resolution,
                api_name=self.api_name,
            )
            
            while True:
                status = job.status()
                if status.code.value == "completed":
                    return job.result()
                elif status.code.value in ("failed", "error"):
                    raise RuntimeError(f"TRELLIS.2 generation failed: {status}")
                time.sleep(3)
        
        result = await asyncio.get_event_loop().run_in_executor(None, _sync_generate)
        return Path(result)
    
    async def health_check(self) -> AdapterHealth:
        from ..models import AdapterHealth
        import time
        
        health = AdapterHealth(name=self.name)
        
        try:
            client = GradioClient(self.space_id, hf_token=self.hf_token)
            start = time.time()
            await asyncio.get_event_loop().run_in_executor(None, client.view_api)
            health.breaker_closed = True
            health.last_success_ts = time.time()
            health.queue_wait_estimate_seconds = 60  # TRELLIS.2 typically slower
        except Exception as e:
            health.breaker_closed = False
            health.last_error = str(e)
        
        return health