import typer
import asyncio
import rich
from pathlib import Path
from typing_extensions import Annotated
from pdfse.core import run_extraction
from pdfse.extract import clear_heuristics_cache

app = typer.Typer()

@app.command()
def extract(
    dataset: Annotated[Path, typer.Option(
        "--dataset",
        "-d",
        help="Path to the dataset JSON file",
        exists=True,
        readable=True,
    )],
    output: Annotated[Path, typer.Option(
        "--output",
        "-o",
        help="Path to save the results as JSON",
        writable=True
    )],
    samples: Annotated[int, typer.Option(
        "--samples",
        "-s",
        help="Number of sample PDFs to send to the LLM for heuristic generation",
        min=1,
    )] = 3,
    image_mode: Annotated[bool, typer.Option(
        "--image-mode",
        help="Use image-based (PNG) samples for the LLM instead of text.",
        is_flag=True,
    )] = False
):
    """
    Extracts data from PDFs based on a dataset file.

    It uses cached heuristics if available, or generates new ones
    via LLM if they are missing for a specific document label.
    """
    asyncio.run(run_extraction(dataset, output, samples, image_mode))


@app.command()
def clear(
    all_flag: Annotated[bool, typer.Option(
        "--all",
        help="Clear the entire heuristics cache.",
        is_flag=True,
    )] = False,
    labels: Annotated[list[str], typer.Option(
        "--label",
        "-l",
        help="Clear only the specified label(s) from the cache. Can be used multiple times.",
    )] = []
):
    """
    Clears the saved heuristics cache file.

    Use --all to clear everything, or --label to clear specific entries.
    """
    if all_flag:
        clear_heuristics_cache(all_flag=True)
    elif labels:
        clear_heuristics_cache(labels_to_clear=labels)
    else:
        rich.print("[yellow]! No action specified. Use --all to clear everything or --label <name> to clear specific labels.")


if __name__ == "__main__":
    app()
