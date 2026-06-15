"""Two-stage text→image→3D adapter."""

import asyncio
import tempfile
import time
from pathlib import Path

from gradio_client import Client as GradioClient, handle_file

from .base import BaseAdapter
from ..models import ModelName, LicenseType, GenerationParams, AdapterHealth, InputType
from .sf3d import SF3DAdapter
from .trellis2 import TRELLIS2Adapter


class TwoStageAdapter(BaseAdapter):
    """Two-stage adapter: text → image (FLUX/SDXL) → 3D (SF3D/TRELLIS.2)."""
    
    name = ModelName.TWO_STAGE
    license = LicenseType.MIT  # Both components are MIT
    space_id = "two_stage"  # virtual
    api_name = "/generate"
    
    def __init__(self, hf_token: str | None = None, image_model: str = "black-forest-labs/FLUX.1-schnell"):
        super().__init__()
        self.hf_token = hf_token
        self.image_model_space = image_model
        self._image_adapter = None
        self._model3d_adapter = None
    
    def _get_image_adapter(self):
        if self._image_adapter is None:
            # Use FLUX.1-schnell or SDXL-turbo for fast image generation
            self._image_adapter = GradioClient(self.image_model_space, hf_token=self.hf_token)
        return self._image_adapter
    
    def _get_3d_adapter(self, params: "GenerationParams"):
        if self._model3d_adapter is None:
            if params.quality == "high":
                self._model3d_adapter = TRELLIS2Adapter(hf_token=self.hf_token)
            else:
                self._model3d_adapter = SF3DAdapter(hf_token=self.hf_token)
        return self._model3d_adapter
    
    async def generate(self, input_path: Path, params: "GenerationParams") -> Path:
        """Two-stage: text → image → 3D."""
        import asyncio
        
        loop = asyncio.get_event_loop()
        
        def _sync_generate():
            prompt = params.prompt
            if not prompt and input_path.exists():
                prompt = input_path.read_text().strip()
            
            if not prompt:
                raise ValueError("No prompt provided for two-stage text→3D")
            
            # Stage 1: text → image
            image_client = self._get_image_adapter()
            
            # FLUX.1-schnell parameters
            image_job = image_client.submit(
                prompt=prompt,
                seed=-1,
                width=1024,
                height=1024,
                num_inference_steps=4,  # FLUX.1-schnell uses 4 steps
                guidance_scale=0.0,
                api_name="/infer",
            )
            
            while True:
                status = image_job.status()
                if status.code.value == "completed":
                    image_path = image_job.result()
                    break
                elif status.code.value in ("failed", "error"):
                    raise RuntimeError(f"Image generation failed: {status}")
                time.sleep(2)
            
            # Stage 2: image → 3D
            model3d = self._get_3d_adapter(params)
            
            # This is sync call - we need to run in executor
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    model3d.generate(Path(image_path), params)
                )
            finally:
                loop.close()
            
            return result
        
        return await asyncio.get_event_loop().run_in_executor(None, _sync_generate)
    
    async def health_check(self) -> AdapterHealth:
        from ..models import AdapterHealth
        import time
        
        health = AdapterHealth(name=self.name)
        
        try:
            # Check both stages
            await asyncio.get_event_loop().run_in_executor(None, self._get_image_adapter().view_api)
            model3d = self._get_3d_adapter(None)
            await model3d.health_check()
            
            health.breaker_closed = True
            health.last_success_ts = time.time()
            health.queue_wait_estimate_seconds = 90  # sum of both stages
        except Exception as e:
            health.breaker_closed = False
            health.last_error = str(e)
        
        return health
    
    def can_handle(self, input_type: str) -> bool:
        return input_type == InputType.TEXT