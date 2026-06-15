"""CLI entry point and commands for sculpt."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.prompt import Confirm

from .config import config, get_config
from .models import GenerationParams, ModelName, InputType
from .router import ModelRouter
from .ui import (
    console, print_banner, print_model_table, print_generation_start,
    print_result, print_error, QueueProgressBar, confirm_overwrite
)
from .output import validate_image, prepare_image
from .reliability import execute_with_reliability
from .cache import get_cache_store, make_cache_key
from .adapters import (
    SF3DAdapter, TRELLIS2Adapter, Hi3DGenAdapter,
    TRELLISTextAdapter, TripoSRAdapter, TwoStageAdapter
)
from .models import ModelName, AdapterHealth, InputType
from .reliability.breaker import CircuitBreaker
from .reliability.limiter import TokenBucket
from .cache import get_cache_store, make_cache_key
from .output import OutputManager


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version and exit")
@click.pass_context
def main(ctx: click.Context, version: bool) -> None:
    """sculpt — free CLI for image→3D and text→3D via Hugging Face Spaces."""
    if version:
        from . import __version__
        console.print(f"sculpt {__version__}")
        ctx.exit()
    
    if ctx.invoked_subcommand is None:
        print_banner()
        console.print("\nRun [bold]sculpt --help[/bold] for commands.")


@main.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=False)
@click.option("--prompt", "-p", type=str, help="Text prompt for text→3D generation")
@click.option("--model", "-m", default="auto", 
              type=click.Choice(["auto", "sf3d", "trellis2", "hi3dgen", "trellis_text", "triposr", "two_stage"]),
              help="Model to use (default: auto-select)")
@click.option("--quality", type=click.Choice(["normal", "high"]), default="normal")
@click.option("--geometry", type=click.Choice(["normal", "high"]), default="normal")
@click.option("--fast/--no-fast", default=False, help="Force fastest model (SF3D)")
@click.option("--texture-res", type=click.IntRange(256, 2048), default=1024)
@click.option("--remesh", type=click.Choice(["none", "triangle", "quad"]), default="none")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output directory")
@click.option("--timeout", type=int, default=600, help="Max seconds to wait")
@click.option("--force/--no-force", default=False, help="Overwrite existing output")
def generate(
    input: Optional[Path],
    prompt: Optional[str],
    model: str,
    quality: str,
    geometry: str,
    fast: bool,
    texture_res: int,
    remesh: str,
    output: Optional[Path],
    timeout: int,
    force: bool,
) -> None:
    """Generate a 3D model from an image or text prompt."""
    
    # Determine input type
    if prompt or model in ("trellis_text", "two_stage"):
        input_type = InputType.TEXT
        if not prompt and input is None:
            print_error("Text prompt required. Use --prompt or provide a text file as input.")
            sys.exit(1)
    elif input:
        input_type = InputType.IMAGE
    else:
        print_error("Either provide an image file or a text prompt (--prompt).")
        sys.exit(1)
    
    # Build params
    params = GenerationParams(
        texture_resolution=texture_res,
        remesh=remesh,
        quality=quality,
        geometry=geometry,
        fast=fast,
        prompt=prompt or "",
        pipeline="auto",
        force=force,
        timeout=timeout,
        model=model,
    )
    
    # Validate image if provided
    if input:
        valid, err = validate_image(input)
        if not valid:
            print_error(err)
            sys.exit(1)
        
        # Prepare image (resize if needed)
        input = prepare_image(input)
    
    # Run generation
    asyncio.run(_run_generate(input, input_type, params, output or config.output_dir, model, force))


async def _run_generate(
    input_path,
    input_type,
    params: GenerationParams,
    out_dir: Path,
    model_override: str,
    force: bool,
) -> None:
    """Async generation runner."""
    
    # Create router and register adapters
    router = ModelRouter()
    
    # Register all adapters
    router.register(SF3DAdapter())
    router.register(TRELLIS2Adapter())
    router.register(Hi3DGenAdapter())
    router.register(TripoSRAdapter())
    router.register(TRELLISTextAdapter())
    router.register(TwoStageAdapter())
    
    # Refresh health
    await router.refresh_health()
    
    # Pick model
    chosen_model = router.pick_model(input_type, params)
    explanation = router.get_routing_explanation(chosen_model, input_type, params)
    
    console.print()
    print_generation_start(chosen_model, "text" if input_type == InputType.TEXT else "image", params.prompt)
    console.print(f"[dim]Reason: {explanation}[/dim]")
    console.print()
    
    # Get adapter class
    adapter_class_map = {
        ModelName.SF3D: SF3DAdapter,
        ModelName.TRELLIS2: TRELLIS2Adapter,
        ModelName.HI3DGEN: Hi3DGenAdapter,
        ModelName.TRELLIS_TEXT: TRELLISTextAdapter,
        ModelName.TRIPO_SR: TripoSRAdapter,
        ModelName.TWO_STAGE: TwoStageAdapter,
    }
    adapter_class = adapter_class_map.get(chosen_model, SF3DAdapter)
    adapter = adapter_class()
    
    # Check cache first
    cache = get_cache_store()
    if input_path:
        cache_key = make_cache_key(input_path, chosen_model.value, params)
        cached = cache.get(cache_key)
        if cached and not force:
            console.print(f"[green]✓[/green] Cache hit! Using [bold]{cached}[/bold]")
            return
    
    # Progress UI
    with QueueProgressBar() as progress:
        from .reliability import execute_with_reliability
        from .reliability.breaker import CircuitBreaker
        from .reliability.limiter import TokenBucket
        
        # Get breaker/limiter for chosen model from a temp router
        temp_router = ModelRouter()
        temp_router.register(SF3DAdapter())
        temp_router.register(TRELLIS2Adapter())
        temp_router.register(Hi3DGenAdapter())
        temp_router.register(TripoSRAdapter())
        temp_router.register(TRELLISTextAdapter())
        temp_router.register(TwoStageAdapter())
        
        breaker = temp_router.breakers.get(chosen_model)
        limiter = temp_router.limiters.get(chosen_model)
        
        if not breaker:
            breaker = CircuitBreaker()
        if not limiter:
            limiter = TokenBucket(rate_per_minute=6)
        
        from pathlib import Path
        try:
            result = await execute_with_reliability(
                adapter=adapter,
                input_path=input_path,
                params=params,
                breaker=breaker,
                limiter=limiter,
                input_type="text" if input_type == InputType.TEXT else "image"
            )
            
            # Save to output directory
            output_manager = OutputManager(Path("outputs"))
            
            # Need to get the adapter name for the output_manager.save
            output_manager.save(result.local_path, Path("prompt") if not input_path else input_path, chosen_model.value)
            
            print_result(result)
            
        except Exception as e:
            print_error(f"Generation failed: {e}")
            raise


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--model", "-m", default="auto")
@click.option("--delay", type=int, default=10, help="Seconds between submissions")
@click.option("--resume/--no-resume", default=True, help="Skip already cached")
@click.option("--output", "-o", type=click.Path(path_type=Path))
def batch(directory: Path, model: str, delay: int, resume: bool, output: Optional[Path]) -> None:
    """Batch process all images in a directory."""
    console.print(f"[bold]Batch processing[/bold] {directory}")
    console.print("[dim]Batch mode not fully implemented yet — use 'sculpt generate' for single images[/dim]")


@main.command()
def models() -> None:
    """List available models and their status."""
    model_info = [
        {"name": "SF3D (Stable Fast 3D)", "healthy": True, "license": "Stability Community", "best_for": "Speed, default", "queue": 30},
        {"name": "TRELLIS.2", "healthy": True, "license": "MIT", "best_for": "Quality, PBR", "queue": 60},
        {"name": "Hi3DGen", "healthy": True, "license": "MIT", "best_for": "Geometry, sharp edges", "queue": 45},
        {"name": "TRELLIS-text", "healthy": True, "license": "MIT", "best_for": "Text→3D direct", "queue": 60},
        {"name": "TripoSR", "healthy": True, "license": "MIT", "best_for": "Fallback, low VRAM", "queue": 20},
        {"name": "Two-Stage (FLUX→3D)", "healthy": True, "license": "MIT", "best_for": "Text→3D quality", "queue": 90},
    ]
    print_model_table(model_info)


@main.command(name="models-use")
@click.argument("name", type=click.Choice(["sf3d", "trellis2", "hi3dgen", "trellis_text", "triposr", "two_stage"]))
def models_use(name: str) -> None:
    """Set default model for future runs."""
    cfg = get_config()
    from .models import ModelName
    try:
        model_enum = ModelName(name)
    except ValueError:
        console.print(f"[red]Invalid model: {name}[/red]")
        return
    cfg.set_default_model(model_enum)
    console.print(f"[green]✓[/green] Default model set to [bold]{name}[/bold]")


@main.command()
def doctor() -> None:
    """Health check on all registered models."""
    console.print("[bold]Running health checks...[/bold]")
    console.print("[dim]Not fully implemented — run a generation to test[/dim]")


@main.command()
@click.argument("token")
def auth(token: str) -> None:
    """Store Hugging Face token for private Spaces."""
    cfg = get_config()
    cfg.set_hf_token(token)
    console.print("[green]✓[/green] Hugging Face token saved")


@main.group(name="cache")
def cache_group() -> None:
    """Cache management commands."""
    pass


@cache_group.command(name="stats")
def cache_stats() -> None:
    from .cache import get_cache_store
    cache = get_cache_store()
    stats = cache.stats()
    console.print(f"[bold]Cache Stats:[/bold]")
    console.print(f"  Entries: {stats['entries']}")
    console.print(f"  Total size: {stats['total_bytes'] / 1024 / 1024:.1f} MB")
    console.print(f"  Total hits: {stats['total_hits']}")


@cache_group.command(name="purge")
@click.option("--confirm/--no-confirm", default=False)
def cache_purge(confirm: bool) -> None:
    if not confirm:
        if not Confirm.ask("Delete all cached results?"):
            console.print("Cancelled.")
            return
    
    from .cache import get_cache_store
    cache = get_cache_store()
    count = cache.purge()
    console.print(f"[green]✓[/green] Purged {count} cache entries")


@main.command(name="show-config")
def show_config() -> None:
    """Show current configuration."""
    cfg = get_config()
    console.print(f"[bold]Config:[/bold]")
    console.print(f"  Default model: {cfg.default_model.value if cfg.default_model else 'auto'}")
    console.print(f"  Output dir: {cfg.output_dir}")
    console.print(f"  HF token: {'set' if cfg.hf_token else 'not set'}")


if __name__ == "__main__":
    main()