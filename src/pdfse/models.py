from pathlib import Path
from pydantic import BaseModel
from dataclasses import dataclass

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
