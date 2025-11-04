import typer
import json
import asyncio
from pathlib import Path
from typing_extensions import Annotated
from pdfse.main import (
    Entry,
    load_entries,
    load_heuristics_cache,
    separate_entries,
    fetch_and_save_missing_heuristics,
    process_entry
)

app = typer.Typer()

async def async_extract(dataset: Path, output: Path):
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

    indexed_entries = list(enumerate(entries))
    heuristics = load_heuristics_cache()

    good_indexed_entries = []
    bad_indexed_entries = []
    bad_entries_for_llm = []

    for index, entry in indexed_entries:
        is_good = True
        if entry.label not in heuristics:
            is_good = False
        else:
            is_good = all(field in heuristics[entry.label] for field in entry.extraction_schema)

        if is_good:
            good_indexed_entries.append((index, entry))
        else:
            bad_indexed_entries.append((index, entry))
            bad_entries_for_llm.append(entry)

    results: list[dict | None] = [None] * len(entries)

    typer.echo(f"Found {len(good_indexed_entries)} entries with cached heuristics and {len(bad_indexed_entries)} without.")

    llm_task = asyncio.create_task(
        fetch_and_save_missing_heuristics(bad_entries_for_llm, heuristics)
    )

    typer.echo("Processing entries with cached heuristics...")
    for index, entry in good_indexed_entries:
        extracted_data = await asyncio.to_thread(process_entry, entry, heuristics)
        results[index] = {
            "label": entry.label,
            "pdf_path": str(entry.pdf_path.relative_to(dataset.parent)),
            "extraction": extracted_data
        }
        typer.echo(f"  [CACHE] Processed: {entry.pdf_path.name}")

    typer.echo("Waiting for LLM to generate missing heuristics...")
    updated_heuristics = await llm_task

    typer.echo("Processing entries with new LLM heuristics...")
    for index, entry in bad_indexed_entries:
        extracted_data = await asyncio.to_thread(process_entry, entry, updated_heuristics)
        results[index] = {
            "label": entry.label,
            "pdf_path": str(entry.pdf_path.relative_to(dataset.parent)),
            "extraction": extracted_data
        }
        typer.echo(f"  [LLM] Processed: {entry.pdf_path.name}")

    try:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        typer.secho(f"Successfully saved results to {output}", fg=typer.colors.GREEN)
    except IOError as e:
        typer.secho(f"Error: Could not write results to {output}: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


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
