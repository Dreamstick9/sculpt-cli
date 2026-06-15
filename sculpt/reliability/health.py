"""Health probe for model adapters."""

import asyncio
import time
from typing import Optional

from gradio_client import Client as GradioClient

from ..models import AdapterHealth, BaseAdapter, ModelName


class HealthProbe:
    """Probes a model adapter's Space for health and queue estimation."""
    
    def __init__(self, adapter: BaseAdapter):
        self.adapter = adapter
        self._client: Optional[GradioClient] = None
    
    async def check(self) -> AdapterHealth:
        """Check adapter health and estimate queue wait."""
        health = AdapterHealth(name=self.adapter.name)
        start = time.time()
        
        try:
            # Try to connect and get API info
            client = await self._get_client()
            
            # For a quick health check, just try to get the API schema
            # This is fast and doesn't consume much queue
            await asyncio.wait_for(
                client.view_api(),
                timeout=30.0
            )
            
            health.breaker_closed = True
            health.last_success_ts = time.time()
            
            # Estimate queue - we can't know for sure without submitting
            # Use historical data or default
            health.queue_wait_estimate_seconds = 30  # baseline
            
            # If we have historical success, use that
            if health.last_success_ts:
                elapsed = time.time() - health.last_success_ts
                if elapsed < 300:  # recent success
                    health.queue_wait_estimate_seconds = min(30, int(elapsed))
                    
        except asyncio.TimeoutError:
            health.breaker_closed = False
            health.last_error = "Timeout connecting to Space"
        except Exception as e:
            health.breaker_closed = False
            health.last_error = str(e)
        
        return health
    
    async def _get_client(self) -> "GradioClient":
        """Get or create Gradio client for the Space."""
        if self._client is None:
            self._client = await GradioClient.connect(self.adapter.space_id)
        return self._client


async def probe_all(adapters: dict) -> dict:
    """Probe all adapters concurrently."""
    tasks = {}
    for name, adapter in adapters.items():
        probe = HealthProbe(adapter)
        tasks[name] = asyncio.create_task(probe.check())
    
    results = {}
    for name, task in tasks.items():
        try:
            results[name] = await task
        except Exception as e:
            from ..models import AdapterHealth
            results[name] = AdapterHealth(name=name, breaker_closed=False, last_error=str(e))
    
    return results