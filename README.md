# pdfse (PDF Schema Extractor)

`pdfse` is a Python-based data extraction tool designed to pull structured data from PDFs.

Its primary strength is handling significant layout variations between documents of the same "type" (e.g., invoices from different vendors). It achieves this by using a Large Language Model (LLM) to generate robust, reusable navigation "heuristics" rather than relying on fixed coordinates or fragile regex.

## The Core Concept

The project operates on a simple but powerful premise: instead of writing custom parsing code for every PDF layout, we use an LLM to write a *plan* for a simple "robot" that navigates the PDF's text.

1.  **WordSpace:** A PDF is first converted into a 2D "WordSpace," which is a map of all text `Word` objects and their `(x0, y0, x1, y1)` bounding boxes.
2.  **LLM as Heuristic Generator:** When `pdfse` encounters a new document `label` (e.g., "invoice-v1") for which it has no plan, it sends text-only images of sample PDFs to an LLM.
3.  **JSON Heuristic Plan:** The LLM's *only* job is to return a JSON-based command plan (a "heuristic"). This plan describes *how* to find each piece of data relative to stable text anchors.
      * *Example Plan for "total":* `[anchor_to_text("Total Due:"), move_right(), collect()]`
4.  **HeuristicMachine:** This JSON plan is fed to the `HeuristicMachine`, a state machine that executes the commands (e.g., `anchor_to_text`, `move_right`) on the `WordSpace` to capture the target text.
5.  **Caching:** This generated heuristic plan is saved to a local `heuristics.json` file. All future documents with the same `label` are processed *instantly* using this cached plan, with no LLM call required.

## Features

  * **Schema-Driven:** Define what you want to extract using a simple JSON schema.
  * **Layout Agnostic:** Handles variations in document layout by relying on relative positioning from text anchors.
  * **Intelligent Caching:** LLM-generated heuristics are cached locally. The LLM is only used to generate heuristics for new, unseen document labels.
  * **Async Processing:** Optimized for performance, fetching new heuristics and processing cached documents concurrently.
  * **Simple CLI:** Easy-to-use command-line interface powered by Typer.

## Installation

The project uses [Poetry](https://python-poetry.org/) for dependency management.

1.  Clone the repository:

    ```bash
    git clone https://github.com/your-username/pdfse.git
    cd pdfse
    ```

2.  Install dependencies using Poetry:

    ```bash
    poetry install
    ```

3.  Activate the virtual environment:

    ```bash
    poetry shell
    ```

## Configuration

`pdfse` requires access to an OpenAI-compatible API to generate heuristics.

1.  Create a `.env` file in the root of the project.

2.  Add your API key:

    ```.env
    OPENAI_API_KEY="sk-..."
    ```

The model (`gpt-5-mini` in `llm.py`) can be changed to any model that supports JSON mode and vision.

## Usage

Using `pdfse` involves three steps: creating a dataset, running the extraction, and reviewing the output.

### 1\. Create a Dataset File

First, you must create a `dataset.json` file that tells `pdfse` which PDFs to process and what data to extract from them.

The `label` is the most important field. It groups similar documents so they can share the same extraction heuristic.

**Example `dataset.json`:**

```json
[
  {
    "label": "invoice-type-a",
    "pdf_path": "pdfs/invoice_001.pdf",
    "extraction_schema": {
      "invoice_number": "The unique invoice identifier",
      "total_amount": "The final total amount"
    }
  },
  {
    "label": "invoice-type-a",
    "pdf_path": "pdfs/invoice_002.pdf",
    "extraction_schema": {
      "invoice_number": "The unique invoice identifier",
      "total_amount": "The final total amount"
    }
  },
  {
    "label": "utility-bill-v1",
    "pdf_path": "pdfs/utility_bill_001.pdf",
    "extraction_schema": {
      "account_id": "The customer account number",
      "due_date": "The payment due date"
    }
  }
]
```

### 2\. Organize Your PDFs

Place your PDFs in a folder relative to the `dataset.json` file, as specified by the `pdf_path` in your dataset. Based on the example above, your folder structure would be:

```
.
├── dataset.json
├── pdfs/
│   ├── invoice_001.pdf
│   ├── invoice_002.pdf
│   └── utility_bill_001.pdf
└── pdfse/
    └── ...
```

### 3\. Run Extraction

Run the main `extract` command. `pdfse` is the module name to run with `poetry run`.

```bash
pdfse extract --dataset dataset.json --output results.json
```

  * `--dataset`: (Required) Path to your dataset file.
  * `--output`: (Required) Path to save the JSON results.
  * `--samples`: (Optional) The number of sample PDFs to send to the LLM when generating a new heuristic. Defaults to 3.

When you run this, `pdfse` will:

1.  See it needs heuristics for `"invoice-type-a"` and `"utility-bill-v1"`.
2.  Call the LLM with 2 samples for `"invoice-type-a"` and 1 sample for `"utility-bill-v1"`.
3.  Save the two new heuristics to `heuristics.json`.
4.  Process all 3 entries using their respective heuristics.
5.  Save the final data to `results.json`.

If you run the *same command* again, it will be instantaneous. `pdfse` will find the heuristics in the cache and skip the LLM generation step entirely.

### 4\. Clear the Heuristic Cache

If you want to force `pdfse` to regenerate all heuristics (e.g., if you changed the LLM prompt or the schemas), you can use the `clear` command.

```bash
pdfse clear
```

This will delete the `heuristics.json` file.

## Project Structure

```
.
├── .env                # OpenAI API Key
├── dataset.json        # Your input dataset file
├── pdfs/               # Your PDF files
├── results.json        # Your output data
├── poetry.lock
├── pyproject.toml
└── src/
    └── pdfse/
        ├── __init__.py
        ├── cli.py            # Typer CLI commands (extract, clear)
        ├── core.py           # Main orchestration logic (run_extraction)
        ├── dataset.py        # Loads and validates dataset.json
        ├── extract.py        # Manages heuristic caching and LLM task prep
        ├── llm.py            # Handles OpenAI API calls and system prompt
        ├── machine.py        # The HeuristicMachine that executes JSON plans
        ├── models.py         # Pydantic and Dataclass models
        ├── pdf.py            # PDF processing utilities (using PyMuPDF/fitz)
        ├── utils.py          # Helper functions (text normalization, math)
        ├── wordspace.py      # Defines the WordSpace class and its API
        └── heuristics.json   # (Generated) The cached LLM plans
```
