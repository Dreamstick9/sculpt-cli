"""Rich console UI helpers for sculpt."""

from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    TimeElapsedColumn, TimeRemainingColumn
)
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live

from .models import AdapterHealth, ModelName, GenerationResult


console = Console()


def print_banner() -> None:
    """Print sculpt banner."""
    console.print(Panel.fit(
        "[bold cyan]sculpt[/bold cyan] — image/text → 3D via Hugging Face Spaces\n"
        "[dim]Free forever • No GPU needed • Zero accounts[/dim]",
        border_style="cyan"
    ))


def print_model_table(models: list[dict]) -> None:
    """Print model status table."""
    table = Table(title="Available Models")
    table.add_column("Model", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("License")
    table.add_column("Best For")
    table.add_column("Queue (est.)")
    
    for m in models:
        status = "[green]HEALTHY[/green]" if m["healthy"] else "[red]DOWN[/red]"
        table.add_row(m["name"], status, m["license"], m["best_for"], f"{m['queue']}s")
    
    console.print(table)


def print_generation_start(model: ModelName, input_type: str, prompt: str = "") -> None:
    """Print generation start info."""
    msg = f"[bold]Routing to:[/bold] {model.value.upper()}\n"
    msg += f"[bold]Input:[/bold] {input_type}"
    if prompt:
        msg += f"\n[bold]Prompt:[/bold] {prompt[:80]}"
    console.print(Panel(msg, title="Starting Generation", border_style="blue"))


@contextmanager
def progress_bar(description: str = "Generating", total: int = 100):
    """Context manager for a rich progress bar."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(description, total=total)
        yield progress, task


class QueueProgressBar:
    """Progress bar that shows queue position and ETA."""
    
    def __init__(self, console: Console = console):
        self.console = console
        self.progress = None
        self.task = None
    
    def __enter__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )
        self.progress.__enter__()
        self.task = self.progress.add_task("Connecting to Space...", total=100)
        return self
    
    def __exit__(self, *args):
        if self.progress:
            self.progress.__exit__(*args)
    
    def update_queue(self, position: int, total: int, eta_seconds: int) -> None:
        """Update queue position display."""
        if self.progress and self.task:
            pct = max(1, min(99, (1 - position / max(total, 1)) * 100))
            self.progress.update(
                self.task,
                completed=pct,
                description=f"Queue: {position}/{total} • ETA ~{eta_seconds}s",
            )
    
    def update_generating(self, elapsed: int) -> None:
        """Switch to generating state."""
        if self.progress and self.task:
            self.progress.update(
                self.task,
                completed=50,
                description=f"GPU running • {elapsed}s elapsed",
            )
    
    def complete(self, path: Path) -> None:
        """Mark complete."""
        if self.progress and self.task:
            self.progress.update(self.task, completed=100, description="Done!")
            self.console.print(f"[green]✓ Saved to {path}[/green]")


def print_result(result: GenerationResult) -> None:
    """Print generation result."""
    console.print(Panel(
        f"[green]✓[/green] Saved to [bold]{result.local_path}[/bold]\n"
        f"Model: {result.model_used.value} | "
        f"Queue wait: {result.queue_wait_seconds:.1f}s | "
        f"Inference: {result.inference_seconds:.1f}s | "
        f"Cached: {result.cached}",
        title="Generation Complete",
        border_style="green"
    ))


def print_error(message: str, hint: str = "") -> None:
    """Print error with optional hint."""
    msg = f"[red]✗[/red] {message}"
    if hint:
        msg += f"\n[dim]{hint}[/dim]"
    console.print(msg)


def confirm_overwrite(path: Path) -> bool:
    """Ask user to confirm overwrite."""
    from rich.prompt import Confirm
    return Confirm.ask(f"[yellow]{path}[/yellow] exists. Overwrite?", default=False)