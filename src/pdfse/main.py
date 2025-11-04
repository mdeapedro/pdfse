import json
from pathlib import Path
from dataclasses import dataclass


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


def save_heuristic_cache(heuristics: list[dict]):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(heuristics, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Warning: Could not save heuristic cache to {CACHE_FILE}: {e}")


def load_entries(dataset: Path) -> list[Entry]:
    with open(dataset, 'r', encoding='utf-8') as f:
        data: list[dict] = json.load(f)  # List of dicts: [{"label": str, "extraction_schema": dict, "pdf": str}, ...]
    entries: list[Entry] = []
    for entry in data:
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
            raise FileNotFoundError(f"Error: PDF not found at {pdf_path}")

        entries.append(Entry(label, extraction_schema, pdf_path))
    return entries


def get_combined_fields(entries: list[Entry]):
    label_fields: dict[str, dict] = {}
    for entry in entries:
        label_fields[entry.label] = {}
    for entry in entries:
        label_fields[entry.label].update(entry.extraction_schema)
    return label_fields


def get_unknown_fields(entries: list[Entry]):
    label_fields = get_combined_fields(entries)
    heuristics = load_heuristics_cache()
    for label in list(label_fields):
        if heuristics.get(label):
            del label_fields[label]
    return label_fields

