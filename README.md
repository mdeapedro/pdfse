# pdfse: PDF Schema Extractor

This is a solution for the Enter AI Fellowship Take Home Project. The main goal is to extract structured data from PDFs quickly (< 10s), accurately (> 80%), and at the lowest possible cost, even when dealing with variable layouts and unknown schemas.

This solution's core architecture does not use an LLM to extract data. Instead, it uses the LLM to generate an execution plan (a "heuristic") that can be saved, cached, and executed locally at high speed.

## Architecture Overview: The Heuristic Generator

The solution divides the problem into two parts:

- **The Heuristic Generator (Slow, Expensive, One-time)**: When a document with a label (or a new field for an existing label) is encountered for the first time, the system calls the LLM (gpt-5-mini). It sends the extraction schema and a few sample PDFs (in text or image mode). The LLM is instructed to act as a "programmer" and generate a JSON containing a set of navigation commands (e.g., "find the text 'Name:'", "move down", "collect the entire line").

- **The Heuristic Executor (Fast, Free, Repeatable)**: This JSON command set is saved in a local cache (heuristics.json). For all future requests for that same label and schema, the system- simply loads this heuristic and executes it locally using a finite state machine (HeuristicMachine) that navigates a "word space" (WordSpace) of the PDF.

This approach directly addresses the project's main challenges:

- **Cost**: The LLM cost is amortized. A single expensive call generates a heuristic that can be used for free thousands of times.
- **Speed**: The local execution of the heuristic (PDF parsing + JSON plan execution) is extremely fast, often under 0.1 seconds, easily beating the < 10-second requirement.
- **Adaptability**: The system "learns" (accumulates knowledge) by saving new heuristics to its cache whenever a new label or schema is introduced.

## Challenges and Solutions

| Challenge                  | Proposed Solution |
|----------------------------|-------------------|
| Minimize Cost and LLM Calls | Heuristic Caching. The LLM is only called to generate the heuristic (the "plan"), not to perform the extraction. The generated heuristic is saved in heuristics.json and reused. |
| Response Time (< 10s)      | Local Execution. The data extraction itself is done by a local executor (HeuristicMachine + WordSpace) that just follows the pre-generated plan. This eliminates network and LLM latency for the vast majority of requests. |
| Accuracy with Variable Layouts | Robust Prompts and Anchoring. The LLM prompt (llm.py) is instructed not to use fixed coordinates. Instead, it is trained to use textual anchors (anchor_to_text, anchor_to_regex) and control logic (loop, if) to create heuristics that survive layout variations, as long as the text labels (e.g., "CPF:", "Name:") are present. |
| Adaptive System (New Labels) | Just-in-Time Heuristic Generation. core.py identifies which dataset entries do not have a cached heuristic (the "bad_entries"). It then groups these entries by label and requests the LLM to generate the missing heuristics, saving them to the cache for future use. |
| Balancing Accuracy vs. Cost | Amortized Cost. The balance is simple: the cost is 1 LLM call per new schema and 0 for all others. Accuracy is delegated to the LLM, which is instructed to create the most robust plan possible. |

## Core Components

- **WordSpace (wordspace.py)**: A class that represents the PDF as a 2D space of words. It has a "cursor" and methods for relative navigation (e.g., move_down, move_right) and anchoring (anchor_to_text).
- **HeuristicMachine (machine.py)**: A state machine that receives the heuristic (JSON command list) and executes it on the WordSpace to extract the data.
- **llm.py**: Responsible for formatting the system prompt (instructing the LLM to generate the JSON commands) and making the call to the OpenAI API.
- **core.py**: The main orchestrator. It identifies cached vs. non-cached entries, processes the cached ones immediately, and triggers new heuristic generation for the non-cached ones.
- **extract.py**: Manages the heuristics.json cache file (reading, writing, clearing).
- **cli.py**: The command-line interface for interacting with the solution.

## How to Use

### 1. Prerequisites

- Python 3.13+
- Poetry
- An OpenAI API Key

### 2. Installation

Clone the repository:

```bash
git clone https://github.com/mdeapedro/pdfse.git
cd pdfse
```

Install dependencies using Poetry:

```bash
poetry install
```

Create a .env file in the project root with your OpenAI key:

```
OPENAI_API_KEY="sk-..."
```

### 3. Running the Extraction

The main script is run via poetry run.

```bash
poetry run pdfse extract --dataset /path/to/your/dataset.json --output /path/to/save/results.json
```

Options:

- `--dataset` (or `-d`): Required. Path to the dataset.json file listing the PDFs to process.
- `--output` (or `-o`): Required. Path where the results JSON will be saved.
- `--samples` (or `-s`): Optional. (Default: 3). The number of sample PDFs to send to the LLM when generating a new heuristic.
- `--image-mode`: Optional. If set, sends image (PNG) cutouts of the PDFs to the LLM instead of plain text. This can be more accurate for complex layouts but is slower and more expensive during generation.

### 4. Managing the Cache

You can clear the heuristic cache at any time.

Clear all:

```bash
poetry run pdfse clear --all
```

Clear a specific label:

```bash
poetry run pdfse clear --label carteira_oab
```
