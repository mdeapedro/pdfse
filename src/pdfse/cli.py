import typer
import asyncio
from pathlib import Path
from typing_extensions import Annotated
from pdfse.extractor import async_extract


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
    asyncio.run(async_extract(dataset, output))


if __name__ == "__main__":
    app()
