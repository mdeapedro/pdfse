import random
import json
import rich
import typer
from pathlib import Path
from pydantic import BaseModel, TypeAdapter, ValidationError
from dataclasses import dataclass

CACHE_FILE = Path(__file__).parent / "heuristics.json"

Heuristics = dict[str, dict[str, list[dict]]]
ExtractionSchema = dict[str, str]

class DatasetEntry(BaseModel):
    label: str
    pdf_path: Path
    extraction_schema: ExtractionSchema

class Entry(DatasetEntry):
    id: int

@dataclass
class LLMTask:
    label: str
    schema_to_fetch: ExtractionSchema
    pdf_paths: list[Path]


heuristics_adapter = TypeAdapter(Heuristics)
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


def separate_good_bad_entries(entries: list[Entry], heuristics: Heuristics) -> tuple[list[Entry], list[Entry]]:
    good_entries = []
    bad_entries = []
    for entry in entries:
        if is_entry_good(entry, heuristics):
            good_entries.append(entry)
        else:
            bad_entries.append(entry)

    if not bad_entries:
        rich.print("[green]✓ All heuristics needed are cached!")
    else:
        rich.print(f"‧ Need heuristics for {len(bad_entries)} entries")
    return good_entries, bad_entries


def prepare_llm_tasks(bad_entries: list[Entry], heuristics: Heuristics) -> list[LLMTask]:
    unknown_label_fields: dict[str, ExtractionSchema] = get_unknown_label_fields(bad_entries, heuristics)
    tasks = []

    label_to_entries_map: dict[str, list[Entry]] = {}
    for entry in bad_entries:
        if entry.label not in label_to_entries_map:
            label_to_entries_map[entry.label] = []
        label_to_entries_map[entry.label].append(entry)

    for label, schema_to_fetch in unknown_label_fields.items():
        if label in label_to_entries_map:
            all_paths_for_label = list(set(entry.pdf_path for entry in label_to_entries_map[label]))

            k = min(len(all_paths_for_label), 3)
            selected_paths = random.sample(all_paths_for_label, k)

            tasks.append(LLMTask(
                label=label,
                schema_to_fetch=schema_to_fetch,
                pdf_paths=selected_paths
            ))
            rich.print(f"‧ Label '{label}': queuing {len(schema_to_fetch)} fields for heuristic generation using {k} PDF(s).")
        else:
            rich.print(f"[yellow]! Warning: No PDF found for bad entry label {label}. Skipping.")

    return tasks


def is_entry_good(entry: Entry, heuristics: Heuristics):
    return all(field in heuristics.get(entry.label, {}) for field in entry.extraction_schema)


def get_unknown_label_fields(entries: list[Entry], heuristics: Heuristics) -> dict[str, ExtractionSchema]:
    unknown_label_fields: dict[str, ExtractionSchema] = {}
    combined_label_fields = _get_combined_label_fields(entries)

    for label, fields in combined_label_fields.items():
        cached_label_fields = heuristics.get(label, {})
        missing_fields = {}
        for field_name, field_desc in fields.items():
            if field_name not in cached_label_fields:
                missing_fields[field_name] = field_desc
        if missing_fields:
            unknown_label_fields[label] = missing_fields

    return unknown_label_fields


def load_heuristics_cache() -> Heuristics:
    if not CACHE_FILE.exists():
        rich.print("[yellow]! Heuristics cache file not found. Skipping...")
        heuristics_cache = {}
    else:
        try:
            with open(CACHE_FILE, "r") as f:
                rich.print(f"[green]✓ Loaded heuristics cache")
                heuristics_cache = heuristics_adapter.validate_json(f.read())
        except ValidationError:
            rich.print("[yellow]! Invalid heuristics cache file. Skipping...")
            heuristics_cache = {}

    return heuristics_cache


def save_heuristic_cache(heuristics: Heuristics):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(heuristics, f)
    except IOError as e:
        rich.print(f"[red]✗ Could not write to heuristics cache: {e}")


def _get_combined_label_fields(entries: list[Entry]) -> dict[str, ExtractionSchema]:
    combined_label_fields: dict[str, ExtractionSchema] = {}
    for entry in entries:
        if entry.label not in combined_label_fields:
            combined_label_fields[entry.label] = {}
    for entry in entries:
        combined_label_fields[entry.label].update(entry.extraction_schema)
    return combined_label_fields
