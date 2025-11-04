import typer
import json
from pathlib import Path
from typing_extensions import Annotated
from dataclasses import dataclass

@dataclass
class Entry:
    label: str
    extraction_schema: dict[str, str]
    pdf_path: Path

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
    """
    Extract data from PDFs based on dataset JSON.
    Processes each entry serially and saves outputs to the specified file.
    """
    typer.echo(f"Starting dataset extraction: {dataset}")
    try:
        with open(dataset, 'r', encoding='utf-8') as f:
            data: list[dict] = json.load(f)  # List of dicts: [{"label": str, "extraction_schema": dict, "pdf": str}, ...]

        entries: list[Entry] = []

        for entry in data:
            try:
                label = entry["label"]
                extraction_schema = entry["extraction_schema"]
                pdf_relative = entry["pdf_path"]

                # Check types
                if not isinstance(label, str):
                    raise ValueError(f"Invalid type for 'label': expected str, got {type(label).__name__}")
                if not isinstance(extraction_schema, dict):
                    raise ValueError(f"Invalid type for 'extraction_schema': expected dict, got {type(extraction_schema).__name__}")
                if not isinstance(pdf_relative, str):
                    raise ValueError(f"Invalid type for 'pdf_path': expected str, got {type(pdf_relative).__name__}")

                pdf_path = dataset.parent / pdf_relative

                if not pdf_path.exists():
                    typer.secho(f"Error: PDF not found at {pdf_path}. Aborting.", fg=typer.colors.RED)
                    raise typer.Exit(code=1)

                entries.append(Entry(label, extraction_schema, pdf_path))

            except KeyError as err:
                typer.secho(f"Error: Missing key in entry - {err}. Aborting.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            except ValueError as err:
                typer.secho(f"Error: Type validation failed in entry - {err}. Aborting.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        # results: list[dict] = []
        typer.echo(f"Processing {len(entries)} entries...")

        for entry in entries:
            typer.secho("Not implemented yet. Skipping...", fg=typer.colors.YELLOW)
            # extracted_schema = extract(entry)
            # results.append(extracted_schema)

        # Save all results as a JSON list
        # output.parent.mkdir(parents=True, exist_ok=True)
        # with open(output, 'w', encoding='utf-8') as f:
        #     json.dump(results, f, indent=2, ensure_ascii=False)

        # typer.secho(f"Results successfully saved to {output}", fg=typer.colors.GREEN)

    except json.JSONDecodeError:
        typer.secho("Error: Invalid JSON in dataset file.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"Unexpected error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
