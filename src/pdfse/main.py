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


def load_heuristics_cache():
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
