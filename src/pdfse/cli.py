import typer
import asyncio
import rich
import json
from pathlib import Path
from typing_extensions import Annotated
from pdfse.extract import (
    load_dataset,
    load_heuristics_cache,
    separate_good_bad_entries,
    prepare_llm_tasks,
    save_heuristic_cache,
    Heuristics,
    Entry,
    ExtractionSchema,
    LLMTask
)
from pdfse.pdf import render_pdf_text, get_pdf_wordspace
from pdfse.llm import fetch_heuristic
from pdfse.machine import HeuristicMachine


app = typer.Typer()

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

    rich.print(f"→ Fetching {len(tasks)} new heuristics from LLM...")
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


async def async_main(dataset: Path, output: Path):
    entries = load_dataset(dataset)
    heuristics = load_heuristics_cache()

    good_entries, bad_entries = separate_good_bad_entries(entries, heuristics)

    results: list[dict | None] = [None] * len(entries)

    llm_task = asyncio.create_task(
        fetch_and_save_missing_heuristics(bad_entries, heuristics)
    )

    rich.print(f"→ Processing {len(good_entries)} entries with cached heuristics...")
    for entry in good_entries:
        extracted_data = await asyncio.to_thread(process_entry, entry, heuristics)
        results[entry.id - 1] = {
            "label": entry.label,
            "pdf_path": str(entry.pdf_path.relative_to(dataset.parent)),
            "extraction": extracted_data
        }

    updated_heuristics = await llm_task

    rich.print(f"→ Processing {len(bad_entries)} entries with new/updated heuristics...")
    for entry in bad_entries:
        extracted_data = await asyncio.to_thread(process_entry, entry, updated_heuristics)
        results[entry.id - 1] = {
            "label": entry.label,
            "pdf_path": str(entry.pdf_path.relative_to(dataset.parent)),
            "extraction": extracted_data
        }

    with open(output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    rich.print(f"\n[green]✓ Extraction complete. Results saved to {output}")


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
    rich.print("Starting extraction")
    asyncio.run(async_main(dataset, output))


if __name__ == "__main__":
    app()
