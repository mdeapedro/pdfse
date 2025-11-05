import json
import asyncio
from pathlib import Path
from pdfse.main import (
    load_entries,
    load_heuristics_cache,
    fetch_and_save_missing_heuristics,
    process_entry
)


async def async_extract(dataset: Path, output: Path):
    entries = load_entries(dataset)

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

    llm_task = asyncio.create_task(
        fetch_and_save_missing_heuristics(bad_entries_for_llm, heuristics)
    )

    for index, entry in good_indexed_entries:
        extracted_data = await asyncio.to_thread(process_entry, entry, heuristics)
        results[index] = {
            "label": entry.label,
            "pdf_path": str(entry.pdf_path.relative_to(dataset.parent)),
            "extraction": extracted_data
        }

    updated_heuristics = await llm_task

    for index, entry in bad_indexed_entries:
        extracted_data = await asyncio.to_thread(process_entry, entry, updated_heuristics)
        results[index] = {
            "label": entry.label,
            "pdf_path": str(entry.pdf_path.relative_to(dataset.parent)),
            "extraction": extracted_data
        }

    with open(output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
