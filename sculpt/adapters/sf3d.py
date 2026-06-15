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
    
    # Try these parameter names in order
    PARAM_NAMES = ["input_image", "image", "img", "file", "input", "upload", "image_input"]
    
    async def generate(self, input_path: Path, params: GenerationParams) -> Path:
        """Generate 3D model using SF3D."""
        loop = asyncio.get_event_loop()
        
        def _sync_generate():
            client = GradioClient(self.space_id)
            
            # Try each parameter name
            for param_name in ["input_image", "image", "img", "file", "input", "upload", "image_input", "image_input_path"]:
                try:
                    kwargs = {
                        param_name: handle_file(str(input_path)),
                        "texture_resolution": params.texture_resolution,
                        "remesh_option": params.remesh,
                    }
                    
                    job = client.submit(fn_index=0, **kwargs)
                    
                    # Poll for completion
                    while True:
                        status = job.status()
                        if status.code.value == "completed":
                            return job.result()
                        elif status.code.value in ("failed", "error"):
                            # Try next parameter name
                            break
                        time.sleep(2)
                    
                    return job.result()
                except TypeError as e:
                    # Parameter name not valid, try next
                    continue
                except Exception as e:
                    # Other error, re-raise
                    raise
            
            raise RuntimeError("No valid parameter name found for image input")
        
        result = await asyncio.get_event_loop().run_in_executor(None, _sync_generate)
        return Path(result)
    
    async def health_check(self) -> AdapterHealth:
        from ..models import AdapterHealth
        import time
        
        health = AdapterHealth(name=self.name)
        
        try:
            client = GradioClient(self.space_id)
            await asyncio.get_event_loop().run_in_executor(None, client.view_api)
            health.breaker_closed = True
            health.last_success_ts = time.time()
            health.queue_wait_estimate_seconds = 30
        except Exception as e:
            health.breaker_closed = False
            health.last_error = str(e)
        
        return health