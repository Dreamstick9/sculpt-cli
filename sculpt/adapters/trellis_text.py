"""TRELLIS Text adapter (direct text→3D)."""

import asyncio
import time
from pathlib import Path

from gradio_client import Client as GradioClient

from .base import BaseAdapter
from ..models import ModelName, LicenseType, GenerationParams, AdapterHealth


class TRELLISTextAdapter(BaseAdapter):
    """Adapter for JeffreyXiang/TRELLIS (text→3D) Space."""
    
    name = ModelName.TRELLIS_TEXT
    license = LicenseType.MIT
    space_id = "JeffreyXiang/TRELLIS"
    api_name = "/generate"
    
    def __init__(self, hf_token: str | None = None):
        super().__init__()
        self.hf_token = hf_token
    
    async def generate(self, input_path: Path, params: GenerationParams) -> Path:
        """
        For text adapter, input_path is actually a text file with the prompt.
        The actual prompt is in params.prompt.
        """
        loop = asyncio.get_event_loop()
        
        def _sync_generate():
            client = GradioClient(self.space_id, hf_token=self.hf_token)
            
            # Read prompt from params
            prompt = params.prompt
            if not prompt and input_path.exists():
                prompt = input_path.read_text().strip()
            
            if not prompt:
                raise ValueError("No prompt provided for text→3D generation")
            
            job = client.submit(
                prompt=prompt,
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
                    raise RuntimeError(f"TRELLIS text→3D generation failed: {status}")
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
            health.queue_wait_estimate_seconds = 60
        except Exception as e:
            health.breaker_closed = False
            health.last_error = str(e)
        
        return health