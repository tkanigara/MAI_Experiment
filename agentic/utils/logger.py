from rich.console import Console
from contextlib import contextmanager
import time

console = Console()

@contextmanager
def node(name: str):
    console.print(f"[cyan]Starting[/cyan] [bold]{name}[/bold]")

    start = time.perf_counter()

    try:
        yield

        elapsed = time.perf_counter() - start

        console.print(
            f"[green]Finished[/green] [bold]{name}[/bold] "
            f"[dim]({elapsed:.2f}s)[/dim]"
        )

    except Exception as e:
        console.print(f"[red]Failed[/red] {name}")
        console.print(f"[red]{e}[/red]")
        raise