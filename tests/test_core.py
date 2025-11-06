import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open, AsyncMock

import pytest
import pytest_asyncio

from pdfse.models import Entry, LLMTask
from pdfse.core import (
    _fetch_heuristic_for_task,
    fetch_and_save_missing_heuristics,
    process_entry,
    run_extraction
)

# Mark all tests in this module as asyncio
# pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_entry():
    return Entry(
        id=1,
        label="test_label",
        pdf_path=Path("dummy/test.pdf"),
        extraction_schema={"field1": "description1", "field2": "description2"}
    )

@pytest.fixture
def mock_heuristics():
    return {
        "test_label": {
            "field1": [{"type": "command", "name": "move_first", "args": {}}]
        }
    }

@pytest.mark.asyncio
@patch("pdfse.core.fetch_heuristic", new_callable=AsyncMock)
@patch("pdfse.core.get_pdf_text_layout", new_callable=MagicMock)
@patch("pdfse.core.render_pdf_text", new_callable=MagicMock)
async def test_fetch_heuristic_for_task_text_mode(
    mock_render, mock_layout, mock_fetch
):
    mock_layout.return_value = "dummy text layout"
    mock_fetch.return_value = {"field1": []}
    schema = {"field1": "desc"}
    pdf_paths = [Path("dummy.pdf")]
    label = "test_label"

    result_label, result_heuristic = await _fetch_heuristic_for_task(
        label, schema, pdf_paths, image_mode=False
    )

    mock_layout.assert_called_once_with(pdf_paths[0])
    mock_render.assert_not_called()
    mock_fetch.assert_called_once_with(schema, ["dummy text layout"], False)
    assert result_label == label
    assert result_heuristic == {"field1": []}

@pytest.mark.asyncio
@patch("pdfse.core.fetch_heuristic", new_callable=AsyncMock)
@patch("pdfse.core.get_pdf_text_layout", new_callable=MagicMock)
@patch("pdfse.core.render_pdf_text", new_callable=MagicMock)
async def test_fetch_heuristic_for_task_image_mode(
    mock_render, mock_layout, mock_fetch
):
    mock_render.return_value = b"dummy image bytes"
    mock_fetch.return_value = {"field1": []}
    schema = {"field1": "desc"}
    pdf_paths = [Path("dummy.pdf")]
    label = "test_label"

    result_label, result_heuristic = await _fetch_heuristic_for_task(
        label, schema, pdf_paths, image_mode=True
    )

    mock_layout.assert_not_called()
    mock_render.assert_called_once_with(pdf_paths[0])
    mock_fetch.assert_called_once_with(schema, [b"dummy image bytes"], True)
    assert result_label == label
    assert result_heuristic == {"field1": []}

@pytest.mark.asyncio
@patch("rich.print")
@patch("pdfse.core.fetch_heuristic", new_callable=AsyncMock)
@patch("pdfse.core.get_pdf_text_layout", new_callable=MagicMock)
async def test_fetch_heuristic_for_task_exception(
    mock_layout, mock_fetch, mock_rich_print
):
    mock_layout.side_effect = Exception("PDF render error")
    schema = {"field1": "desc"}
    pdf_paths = [Path("dummy.pdf")]
    label = "error_label"

    result_label, result_heuristic = await _fetch_heuristic_for_task(
        label, schema, pdf_paths, image_mode=False
    )

    mock_rich_print.assert_called_once()
    assert result_label == label
    assert result_heuristic == {}

@pytest.mark.asyncio
@patch("pdfse.core.prepare_llm_tasks")
async def test_fetch_and_save_missing_heuristics_no_tasks(
    mock_prepare_llm
):
    mock_prepare_llm.return_value = []
    initial_heuristics = {"cached": {}}

    result = await fetch_and_save_missing_heuristics(
        [], initial_heuristics, 3, False
    )

    assert result == initial_heuristics

@pytest.mark.asyncio
@patch("rich.print")
@patch("pdfse.core.save_heuristic_cache")
@patch("asyncio.gather", new_callable=AsyncMock)
@patch("pdfse.core.prepare_llm_tasks")
async def test_fetch_and_save_missing_heuristics_with_tasks(
    mock_prepare_llm, mock_gather, mock_save_cache, mock_rich_print
):
    mock_task = LLMTask(
        label="new_label",
        schema_to_fetch={"new_field": "desc"},
        pdf_paths=[Path("new.pdf")]
    )
    mock_prepare_llm.return_value = [mock_task]
    mock_gather.return_value = [("new_label", {"new_field": []})]

    initial_heuristics = {"old_label": {"field1": []}}

    result = await fetch_and_save_missing_heuristics(
        [MagicMock()], initial_heuristics, 3, False
    )

    mock_gather.assert_called_once()
    mock_save_cache.assert_called_once_with({
        "old_label": {"field1": []},
        "new_label": {"new_field": []}
    })
    assert "new_label" in result
    assert result["new_label"] == {"new_field": []}

@patch("pdfse.core.HeuristicMachine")
@patch("pdfse.core.get_pdf_wordspace")
def test_process_entry_success(mock_get_ws, mock_machine_cls, mock_entry):
    mock_ws = MagicMock()
    mock_get_ws.return_value = mock_ws

    mock_machine_instance = MagicMock()
    mock_machine_instance.run.return_value = {"field1": "data1"}
    mock_machine_cls.return_value = mock_machine_instance

    heuristics = {
        "test_label": {
            "field1": [{"type": "command", "name": "move_first", "args": {}}]
        }
    }

    result = process_entry(mock_entry, heuristics)

    mock_get_ws.assert_called_once_with(mock_entry.pdf_path)
    mock_machine_cls.assert_called_once_with(mock_ws)

    expected_heuristic_for_entry = {
        "field1": heuristics["test_label"]["field1"]
    }
    mock_machine_instance.run.assert_called_once_with(expected_heuristic_for_entry)

    assert result == {"field1": "data1", "field2": None}

@patch("rich.print")
@patch("pdfse.core.get_pdf_wordspace")
def test_process_entry_exception(mock_get_ws, mock_rich_print, mock_entry):
    mock_get_ws.side_effect = Exception("Wordspace error")

    result = process_entry(mock_entry, {})

    mock_rich_print.assert_called_once()
    assert result == {"field1": None, "field2": None}

@pytest.mark.asyncio
@patch("json.dump")
@patch("builtins.open", new_callable=mock_open)
@patch("pdfse.core.process_entry")
@patch("pdfse.core.fetch_and_save_missing_heuristics", new_callable=AsyncMock)
@patch("pdfse.core.separate_good_bad_entries")
@patch("pdfse.core.load_heuristics_cache")
@patch("pdfse.core.load_dataset")
async def test_run_extraction(
    mock_load_dataset,
    mock_load_cache,
    mock_separate,
    mock_fetch_save,
    mock_process,
    mock_file_open,
    mock_json_dump,
    mock_entry
):
    mock_entry_good = Entry(
        id=1,
        label="good_label",
        pdf_path=Path("dummy/good.pdf"),
        extraction_schema={"field1": "desc1"}
    )
    mock_entry_bad = Entry(
        id=2,
        label="bad_label",
        pdf_path=Path("dummy/bad.pdf"),
        extraction_schema={"field2": "desc2"}
    )

    mock_load_dataset.return_value = [mock_entry_good, mock_entry_bad]

    initial_heuristics = {"good_label": {"field1": []}}
    mock_load_cache.return_value = initial_heuristics

    mock_separate.return_value = ([mock_entry_good], [mock_entry_bad])

    updated_heuristics = {
        "good_label": {"field1": []},
        "bad_label": {"field2": []}
    }
    mock_fetch_save.return_value = updated_heuristics

    def process_side_effect(entry, heuristics):
        if entry.label == "good_label":
            return {"field1": "data1"}
        if entry.label == "bad_label":
            return {"field2": "data2"}
        return {}

    mock_process.side_effect = process_side_effect

    dataset_path = Path("dummy/dataset.json")
    output_path = Path("dummy/output.json")

    # with patch("asyncio.to_thread", new_callable=MagicMock) as mock_to_thread:
    #     # Make asyncio.to_thread execute the function immediately
    #     mock_to_thread.side_effect = lambda func, *args: func(*args)

    await run_extraction(dataset_path, output_path, 3, False)

    assert mock_process.call_count == 2
    mock_process.assert_any_call(mock_entry_good, initial_heuristics)
    mock_process.assert_any_call(mock_entry_bad, updated_heuristics)

    mock_fetch_save.assert_called_once_with(
        [mock_entry_bad], initial_heuristics, 3, False
    )

    mock_file_open.assert_called_once_with(output_path, "w")

    expected_results = [
        {
            "label": "good_label",
            "pdf_path": "good.pdf",
            "extraction": {"field1": "data1"}
        },
        {
            "label": "bad_label",
            "pdf_path": "bad.pdf",
            "extraction": {"field2": "data2"}
        }
    ]
    mock_json_dump.assert_called_once_with(
        expected_results, mock_file_open(), indent=2, ensure_ascii=False
    )
