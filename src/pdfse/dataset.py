import rich
import typer
from pathlib import Path
from pydantic import TypeAdapter, ValidationError
from .models import DatasetEntry, Entry

dataset_adapter = TypeAdapter(list[DatasetEntry])

def load_dataset(dataset: Path) -> list[Entry]:
    try:
        with open(dataset, "r") as f:
            data = dataset_adapter.validate_json(f.read())
    except ValidationError as e:
        rich.print(f"[red]✗ Failed to load or validate dataset: {dataset}")
        rich.print(e)
        raise typer.Exit(code=1)
    except FileNotFoundError:
        rich.print(f"[red]✗ Dataset file not found: {dataset}")
        raise typer.Exit(code=1)

    entries = [
        Entry(
            id=idx,
            label=entry.label,
            pdf_path=dataset.parent / entry.pdf_path,
            extraction_schema=entry.extraction_schema
        ) for idx, entry in enumerate(data, start=1)
    ]

    rich.print(f"[green]✓ Loaded {len(entries)} entries from dataset")
    return entries
