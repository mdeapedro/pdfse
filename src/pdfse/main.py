import json
import asyncio
import random
from pathlib import Path
from dataclasses import dataclass
from pdfse.llm import ask_for_heuristic
from pdfse.pdf import render_pdf_text, get_pdf_wordspace
from pdfse.machine import HeuristicMachine


PROJECT_ROOT = Path(__file__).parent.parent
CACHE_FILE = PROJECT_ROOT / "heuristic_cache.json"


@dataclass
class Entry:
    label: str
    extraction_schema: dict[str, str]
    pdf_path: Path


def load_heuristics_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_heuristic_cache(heuristics: dict):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(heuristics, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Warning: Could not save heuristic cache to {CACHE_FILE}: {e}")


def load_entries(dataset: Path) -> list[Entry]:
    with open(dataset, 'r', encoding='utf-8') as f:
        data: list[dict] = json.load(f)
    entries: list[Entry] = []
    for entry in data:
        label = entry["label"]
        extraction_schema = entry["extraction_schema"]
        pdf_relative = entry["pdf_path"]

        if not isinstance(label, str):
            raise ValueError(f"Invalid type for 'label': expected str, got {type(label).__name__}")
        if not isinstance(extraction_schema, dict):
            raise ValueError(f"Invalid type for 'extraction_schema': expected dict, got {type(extraction_schema).__name__}")
        if not isinstance(pdf_relative, str):
            raise ValueError(f"Invalid type for 'pdf_path': expected str, got {type(pdf_relative).__name__}")

        pdf_path = dataset.parent / pdf_relative

        if not pdf_path.exists():
            raise FileNotFoundError(f"Error: PDF not found at {pdf_path}")

        entries.append(Entry(label, extraction_schema, pdf_path))
    return entries


def get_combined_fields(entries: list[Entry]) -> dict[str, dict]:
    label_fields: dict[str, dict] = {}
    for entry in entries:
        if entry.label not in label_fields:
            label_fields[entry.label] = {}
    for entry in entries:
        label_fields[entry.label].update(entry.extraction_schema)
    return label_fields


def get_unknown_fields(entries: list[Entry], heuristics: dict) -> dict[str, dict]:
    unknown_fields_by_label: dict[str, dict] = {}
    combined_fields = get_combined_fields(entries)

    for label, all_fields in combined_fields.items():
        cached_label_fields = heuristics.get(label, {})
        missing_fields = {}
        for field_name, field_desc in all_fields.items():
            if field_name not in cached_label_fields:
                missing_fields[field_name] = field_desc

        if missing_fields:
            unknown_fields_by_label[label] = missing_fields

    return unknown_fields_by_label


def separate_entries(entries: list[Entry], heuristics: dict) -> tuple[list[Entry], list[Entry]]:
    good_entries = []
    bad_entries = []
    for entry in entries:
        is_good = True
        if entry.label not in heuristics:
            is_good = False
        else:
            is_good = all(field in heuristics[entry.label] for field in entry.extraction_schema)

        if is_good:
            good_entries.append(entry)
        else:
            bad_entries.append(entry)
    return good_entries, bad_entries


async def _fetch_heuristic_for_label(label: str, schema_to_fetch: dict, pdf_paths: list[Path]) -> tuple[str, dict]:
    try:
        render_tasks = [asyncio.to_thread(render_pdf_text, pdf_path) for pdf_path in pdf_paths]
        image_bytes_list = await asyncio.gather(*render_tasks)

        new_heuristic_for_label = await ask_for_heuristic(
            schema_to_fetch, image_bytes_list
        )
        return label, new_heuristic_for_label
    except Exception as e:
        print(f"Error fetching heuristic for label {label}: {e}")
        return label, {}


async def fetch_and_save_missing_heuristics(bad_entries: list[Entry], heuristics: dict) -> dict:
    unknown_fields_by_label = get_unknown_fields(bad_entries, heuristics)

    if not unknown_fields_by_label:
        return heuristics

    label_to_entries_map: dict[str, list[Entry]] = {}
    for entry in bad_entries:
        if entry.label not in label_to_entries_map:
            label_to_entries_map[entry.label] = []
        label_to_entries_map[entry.label].append(entry)

    tasks = []
    for label, schema_to_fetch in unknown_fields_by_label.items():
        if label in label_to_entries_map:
            all_paths_for_label = list(set(entry.pdf_path for entry in label_to_entries_map[label]))

            k = min(len(all_paths_for_label), 3)
            selected_paths = random.sample(all_paths_for_label, k)

            print(f"Label '{label}': selecting {k} PDF(s) as examples.")

            tasks.append(_fetch_heuristic_for_label(label, schema_to_fetch, selected_paths))
        else:
            print(f"Warning: No PDF found for bad entry label {label}. Skipping.")


    print(f"Fetching {len(tasks)} new heuristics from LLM...")
    results = await asyncio.gather(*tasks)

    updated_heuristics = heuristics.copy()
    has_new_data = False
    for label, new_heuristic in results:
        if new_heuristic:
            if label not in updated_heuristics:
                updated_heuristics[label] = {}
            updated_heuristics[label].update(new_heuristic)
            has_new_data = True

    if has_new_data:
        save_heuristic_cache(updated_heuristics)
        print("Heuristic cache updated.")

    return updated_heuristics


def process_entry(entry: Entry, heuristics: dict) -> dict[str, str | None]:
    try:
        wordspace = get_pdf_wordspace(entry.pdf_path)
        machine = HeuristicMachine(wordspace)

        label_heuristic = heuristics.get(entry.label, {})

        schema_fields = set(entry.extraction_schema.keys())

        heuristic_for_entry = {
            field: commands
            for field, commands in label_heuristic.items()
            if field in schema_fields
        }

        missing_fields = schema_fields - set(heuristic_for_entry.keys())

        extracted_data = machine.run(heuristic_for_entry)

        for field in missing_fields:
            extracted_data[field] = None

        return extracted_data

    except Exception as e:
        print(f"Error processing {entry.pdf_path.name}: {e}")
        return {field: None for field in entry.extraction_schema}
