import typer
import json
from pathlib import Path
from typing_extensions import Annotated
from pdfse.main import Entry, get_missing_fields, load_entries

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
    typer.echo(f"Starting dataset extraction: {dataset}")
    try:
        entries = load_entries(dataset)
    except KeyError as err:
        typer.secho(f"Error: Missing key in entry - {err}. Aborting.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except ValueError as err:
        typer.secho(f"Error: Type validation failed - {err}. Aborting.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as err:
        typer.secho(f"{err}. Aborting.", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
