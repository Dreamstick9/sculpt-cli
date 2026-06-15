"""Hi3DGen adapter."""

import asyncio
import time
from pathlib import Path

from gradio_client import Client as GradioClient, handle_file

from .base import BaseAdapter
from ..models import ModelName, LicenseType, GenerationParams, AdapterHealth


class Hi3DGenAdapter(BaseAdapter):
    """Adapter for Stable-X/Hi3DGen Space."""
    
    name = ModelName.HI3DGEN
    license = LicenseType.MIT
    space_id = "Stable-X/Hi3DGen"
    api_name = "/generate"
    
    def __init__(self, hf_token: str | None = None):
        super().__init__()
        self.hf_token = hf_token
    
    async def generate(self, input_path: Path, params: GenerationParams) -> Path:
        """Generate 3D model using Hi3DGen."""
        loop = asyncio.get_event_loop()
        
        def _sync_generate():
            client = GradioClient(self.space_id, hf_token=self.hf_token)
            
            job = client.submit(
                image=handle_file(str(input_path)),
                seed=-1,
                stage1_guidance_scale=7.5,
                stage1_steps=50,
                stage2_guidance_scale=3.0,
                stage2_steps=50,
                api_name=self.api_name,
            )
            
            while True:
                status = job.status()
                if status.code.value == "completed":
                    return job.result()
                elif status.code.value in ("failed", "error"):
                    raise RuntimeError(f"Hi3DGen generation failed: {status}")
                time.sleep(3)
        
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
            health.queue_wait_estimate_seconds = 45
        except Exception as e:
            health.breaker_closed = False
            health.last_error = str(e)
        
        return health