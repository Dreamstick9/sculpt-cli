"""Auto-model picker — the core intelligence of sculpt."""

import time
from typing import Optional

from .models import (
    AdapterHealth, GenerationParams, InputType, ModelName, 
    BaseAdapter
)
from .reliability.breaker import CircuitBreaker
from .reliability.limiter import TokenBucket
from .reliability.health import HealthProbe


class ModelRouter:
    """Intelligent model selection based on input, flags, and live state."""
    
    def __init__(self):
        self.adapters: dict[ModelName, BaseAdapter] = {}
        self.health_states: dict[ModelName, AdapterHealth] = {}
        self.breakers: dict[ModelName, CircuitBreaker] = {}
        self.limiters: dict[ModelName, TokenBucket] = {}
        self.probes: dict[ModelName, HealthProbe] = {}
        
        # Hard-coded defaults per model
        self._default_limits = {
            ModelName.SF3D: 6,           # req/min
            ModelName.TRELLIS2: 2,
            ModelName.HI3DGEN: 2,
            ModelName.TRELLIS_TEXT: 2,
            ModelName.TRIPO_SR: 4,
            ModelName.TWO_STAGE: 1,      # uses 2 Spaces
        }
        self._quality_bias = {
            ModelName.TRELLIS2: 100,
            ModelName.HI3DGEN: 80,
            ModelName.SF3D: 40,
            ModelName.TRIPO_SR: 20,
            ModelName.TRELLIS_TEXT: 30,
            ModelName.TWO_STAGE: 70,
        }
    
    def register(self, adapter: BaseAdapter) -> None:
        """Register an adapter and its reliability components."""
        self.adapters[adapter.name] = adapter
        self.health_states[adapter.name] = AdapterHealth(name=adapter.name)
        self.breakers[adapter.name] = CircuitBreaker(
            threshold=5, window_seconds=300, half_open_timeout=60
        )
        self.limiters[adapter.name] = TokenBucket(
            rate_per_minute=self._default_limits.get(adapter.name, 4)
        )
        self.probes[adapter.name] = HealthProbe(adapter)
    
    async def refresh_health(self) -> None:
        """Probe all registered adapters for health."""
        for name, probe in self.probes.items():
            try:
                health = await probe.check()
                self.health_states[name] = health
                self.breakers[name].record_success() if health.breaker_closed else None
            except Exception as e:
                self.health_states[name] = AdapterHealth(
                    name=name, breaker_closed=False, last_error=str(e)
                )
                self.breakers[name].record_failure()
    
    def pick_model(self, input_type: InputType, params: GenerationParams) -> ModelName:
        """Select the best model for the given input and parameters."""
        
        # 1. Filter by hard constraints (input type)
        candidates = [
            m for m in self.adapters.keys() 
            if self.adapters[m].can_handle(input_type)
        ]
        
        # 2. Apply user override
        if params.pipeline == "1stage" and ModelName.TRELLIS_TEXT in candidates:
            candidates = [ModelName.TRELLIS_TEXT]
        elif params.pipeline == "2stage" and ModelName.TWO_STAGE in candidates:
            candidates = [ModelName.TWO_STAGE]
        elif params.model != "auto":
            try:
                override = ModelName(params.model)
                if override in candidates:
                    candidates = [override]
            except ValueError:
                pass
        
        # 3. Apply circuit breakers (hard filter)
        candidates = [
            m for m in candidates 
            if self.breakers[m].state == "closed"
        ]
        
        if not candidates:
            # All breakers open - return best available anyway
            candidates = [m for m in self.adapters.keys() 
                         if self.adapters[m].can_handle(input_type)]
            if not candidates:
                raise RuntimeError("No models available for input type")
        
        # 4. Score each candidate
        prompt = params.prompt or ""
        now = time.time()
        scored = []
        
        for m in candidates:
            health = self.health_states.get(m, AdapterHealth(name=m))
            breaker = self.breakers[m]
            
            score = 0
            
            # Base quality bias
            score += self._quality_bias.get(m, 0)
            
            # Flag modifiers
            if params.quality == "high" and m == ModelName.TRELLIS2:
                score += 100
            if params.geometry == "high" and m == ModelName.HI3DGEN:
                score += 100
            if params.fast and m in (ModelName.SF3D, ModelName.TRIPO_SR):
                score += 50
            
            # Prompt heuristic
            prompt_lower = prompt.lower()
            if any(kw in prompt_lower for kw in ("sharp", "edge", "mechanical", "rectangular", "architecture")):
                if m == ModelName.HI3DGEN:
                    score += 40
            if any(kw in prompt_lower for kw in ("smooth", "face", "organic", "skin")):
                if m in (ModelName.SF3D, ModelName.TRELLIS2):
                    score += 30
            
            # Penalize by estimated queue wait
            score -= health.queue_wait_estimate_seconds * 0.5
            
            # Penalize recent failures
            score -= health.failure_count_window * 10
            
            # Bonus for healthy breaker
            if breaker.state == "closed":
                score += 10
            
            scored.append((score, m))
        
        # Sort by score descending
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]
    
    def get_routing_explanation(self, chosen: ModelName, input_type: InputType, 
                                 params: GenerationParams) -> str:
        """Generate human-readable explanation of routing decision."""
        reasons = []
        
        if params.model != "auto":
            reasons.append(f"User override: {params.model}")
        else:
            if params.quality == "high" and chosen == ModelName.TRELLIS2:
                reasons.append("Quality=high → TRELLIS.2")
            if params.geometry == "high" and chosen == ModelName.HI3DGEN:
                reasons.append("Geometry=high → Hi3DGen")
            if params.fast and chosen in (ModelName.SF3D, ModelName.TRIPO_SR):
                reasons.append("Fast mode → SF3D/TripoSR")
            
            prompt = params.prompt or ""
            prompt_lower = prompt.lower()
            if any(kw in prompt_lower for kw in ("sharp", "edge", "mechanical")):
                if chosen == ModelName.HI3DGEN:
                    reasons.append("Prompt hints at geometric precision")
            
            health = self.health_states.get(chosen, AdapterHealth(name=chosen))
            if health.queue_wait_estimate_seconds < 30:
                reasons.append(f"Shortest queue (~{health.queue_wait_estimate_seconds}s)")
        
        return " → ".join(reasons) if reasons else "Auto-selected (default)"