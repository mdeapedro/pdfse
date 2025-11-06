import random
import json
import rich
from pathlib import Path
from pydantic import TypeAdapter, ValidationError
from .models import Heuristics, ExtractionSchema, Entry, LLMTask

CACHE_FILE = Path(__file__).parent / "heuristics.json"

heuristics_adapter = TypeAdapter(Heuristics)

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
            json.dump(heuristics, f, ensure_ascii=False)
    except IOError as e:
        rich.print(f"[red]✗ Could not write to heuristics cache: {e}")

def clear_heuristics_cache(
    all_flag: bool = False,
    labels_to_clear: list[str] | None = None
):
    if not CACHE_FILE.exists():
        rich.print("[yellow]! Heuristics cache file not found. Nothing to clear.")
        return

    if all_flag:
        try:
            CACHE_FILE.unlink()
            rich.print(f"[green]✓ Heuristics cache file deleted: {CACHE_FILE}")
        except Exception as e:
            rich.print(f"[red]✗ Could not delete heuristics cache: {e}")
        return

    if labels_to_clear:
        heuristics = load_heuristics_cache()
        if not heuristics:
            rich.print("[yellow]! Heuristics cache is empty. Nothing to clear.")
            return

        labels_removed_count = 0
        for label in labels_to_clear:
            if label in heuristics:
                heuristics.pop(label)
                rich.print(f"[green]✓ Removed heuristic for label: '{label}'")
                labels_removed_count += 1
            else:
                rich.print(f"[yellow]! Heuristic for label '{label}' not found. Skipping.")

        if labels_removed_count > 0:
            save_heuristic_cache(heuristics)
            rich.print(f"[green]✓ Heuristics cache updated. Removed {labels_removed_count} label(s).")
        else:
            rich.print("‧ No matching heuristics found to remove.")

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

def prepare_llm_tasks(bad_entries: list[Entry], heuristics: Heuristics, samples: int) -> list[LLMTask]:
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

            k = min(len(all_paths_for_label), samples)
            selected_paths = random.sample(all_paths_for_label, k)

            tasks.append(LLMTask(
                label=label,
                schema_to_fetch=schema_to_fetch,
                pdf_paths=selected_paths
            ))
            rich.print(f"→ Label '{label}': queuing {len(schema_to_fetch)} fields for heuristic generation using {k} PDF(s).")
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

def _get_combined_label_fields(entries: list[Entry]) -> dict[str, ExtractionSchema]:
    combined_label_fields: dict[str, ExtractionSchema] = {}
    for entry in entries:
        if entry.label not in combined_label_fields:
            combined_label_fields[entry.label] = {}
    for entry in entries:
        combined_label_fields[entry.label].update(entry.extraction_schema)
    return combined_label_fields
