import asyncio
import json
import rich
import rich.progress as rp
from pathlib import Path

from .models import Entry, Heuristics, ExtractionSchema, LLMTask
from .dataset import load_dataset
from .extract import (
    load_heuristics_cache,
    separate_good_bad_entries,
    prepare_llm_tasks,
    save_heuristic_cache
)
from .pdf import render_pdf_text, get_pdf_wordspace
from .llm import fetch_heuristic
from .machine import HeuristicMachine


async def _fetch_heuristic_for_task(label: str, schema_to_fetch: ExtractionSchema, pdf_paths: list[Path]) -> tuple[str, dict]:
    try:
        render_tasks = [asyncio.to_thread(render_pdf_text, pdf_path) for pdf_path in pdf_paths]
        image_bytes_list = await asyncio.gather(*render_tasks)

        new_heuristic_for_label = await fetch_heuristic(
            schema_to_fetch, image_bytes_list
        )
        return label, new_heuristic_for_label
    except Exception as e:
        rich.print(f"[red]✗ Error fetching heuristic for label {label}: {e}")
        return label, {}

async def fetch_and_save_missing_heuristics(
    bad_entries: list[Entry],
    heuristics: Heuristics
) -> Heuristics:

    llm_tasks: list[LLMTask] = prepare_llm_tasks(bad_entries, heuristics)

    if not llm_tasks:
        return heuristics

    tasks = []
    for task in llm_tasks:
        tasks.append(
            _fetch_heuristic_for_task(task.label, task.schema_to_fetch, task.pdf_paths)
        )

    with rp.Progress(
        rp.SpinnerColumn(),
        rp.TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description=f"Fetching {len(tasks)} new heuristics from LLM...", total=None)
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
        rich.print("[green]✓ Heuristic cache updated.")

    return updated_heuristics

def process_entry(entry: Entry, heuristics: Heuristics) -> dict[str, str | None]:
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
        rich.print(f"[red]✗ Error processing {entry.pdf_path.name}: {e}")
        return {field: None for field in entry.extraction_schema}


async def run_extraction(dataset: Path, output: Path) -> None:
    entries = load_dataset(dataset)
    heuristics = load_heuristics_cache()

    good_entries, bad_entries = separate_good_bad_entries(entries, heuristics)

    results: list[dict | None] = [None] * len(entries)

    llm_task = asyncio.create_task(
        fetch_and_save_missing_heuristics(bad_entries, heuristics)
    )

    for entry in good_entries:
        extracted_data = await asyncio.to_thread(process_entry, entry, heuristics)
        results[entry.id - 1] = {
            "label": entry.label,
            "pdf_path": str(entry.pdf_path.relative_to(dataset.parent)),
            "extraction": extracted_data
        }
        rich.print(f"[green]✓ Entry #{entry.id} executed (cache)")

    updated_heuristics = await llm_task

    for entry in bad_entries:
        extracted_data = await asyncio.to_thread(process_entry, entry, updated_heuristics)
        results[entry.id - 1] = {
            "label": entry.label,
            "pdf_path": str(entry.pdf_path.relative_to(dataset.parent)),
            "extraction": extracted_data
        }
        rich.print(f"[green]✓ Entry #{entry.id} executed")

    with open(output, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    rich.print(f"[green]✓ Extraction complete. Results saved to {output}")
