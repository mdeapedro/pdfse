import typer
import asyncio
import rich
from pathlib import Path
from typing_extensions import Annotated
from pdfse.core import run_extraction

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
    )]
):
    asyncio.run(run_extraction(dataset, output))


if __name__ == "__main__":
    app()
