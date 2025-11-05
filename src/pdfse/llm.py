import json
import base64
import openai
from dotenv import load_dotenv


load_dotenv()


_client: openai.AsyncOpenAI | None = None
def get_client() -> openai.AsyncOpenAI:
    global _client
    if not _client:
        _client = openai.AsyncOpenAI(timeout=300.0)
    return _client


def _encode_image_to_base64(imageb: bytes) -> str:
    base64_string = base64.b64encode(imageb).decode('utf-8')
    return f"data:image/png;base64,{base64_string}"


async def ask_for_heuristic(
    extraction_schema: dict,
    imagesb: list[bytes]
) -> dict[str, list]:
    client = get_client()
    user_content: list[dict] = [
        {
            "type": "text",
            "text": f"""
            Here is the extraction schema for this task. Please generate the JSON heuristic based on this schema and the provided images:

            {json.dumps(extraction_schema, indent=2, ensure_ascii=False)}
            """
        }
    ]
    for imageb in imagesb:
        base64_image_url = _encode_image_to_base64(imageb)
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": base64_image_url,
                "detail": "high"
            }
        })

    response = await client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content} # type: ignore
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=4096
    )
    response_content = response.choices[0].message.content
    if not response_content:
        raise ValueError("LLM response was empty")

    heuristic = json.loads(response_content)
    return heuristic


SYSTEM_PROMPT = """You are an expert AI assistant specializing in PDF data extraction. Your task is to act as a 'heuristic generator' for a navigation robot.

**GOLDEN RULE: PURE JSON**
Your response *must* be **exclusively a valid JSON object**. No text, explanations, or markdown (like ```json ... ```) should be used. Only pure JSON.

---

**MAIN TASK**

You will receive an `extraction_schema` (JSON) and PNG images of a PDF (showing only the positioned text).

Your mission is to generate a **JSON command plan** that uses the `WordSpace` class API to extract the values for each field in the schema.

**PROVIDED CONTEXT (INPUTS)**

1.  **Images (Visual Context):** PNG images of the text-only rendered PDF. Use these to understand the *layout*, *proximity*, and *relative positioning* of words.
2.  **Schema (Objective):** A JSON `extraction_schema` (e.g., `{"name": "Name of the person", "cpf": "Tax ID number"}`).

**OUTPUT FORMAT (FIXED JSON)**

Your output *must* follow this structure:
{
  "schema_field_1": [command_list_for_field_1],
  "schema_field_2": [command_list_for_field_2]
}

**STRATEGIC PRINCIPLES (HOW TO THINK)**

1.  **CRITICAL: Handle Layout Variability.**
    * Documents with the same `label` can have **radically different layouts**. You might receive multiple images (e.g., 3 examples) that look different but share the same *label*.
    * Your task is to find the **common, constant elements** (i.e., text labels) that exist across all examples and use them as your starting point.
    * **ALWAYS** start with an anchor (`anchor_to_text` or `anchor_to_regex`) to lock onto a fixed *label* (e.g., "Name:", "CPF:", "Inscrição").
    * **NEVER** use fragile navigation from the top-left (e.g., `move_first() -> move_down() -> move_down()`). This will fail 100% of the time if the layout changes.
    * All navigation *must* be relative to a strong, constant text anchor.

2.  **CRITICAL: Use Control Flow (If/Loop) for Precision & Robustness.**
    * Simple navigation (e.g., `anchor -> move_right -> collect`) can fail. Use `if` and `loop` to build robust heuristics that can handle variations.
    * **Use `loop` for Multi-Line or Repeated Data:** When data spans multiple lines (like an address) or you need to collect items until a "stop" word.
    * **Loop Example:** To collect all lines of an address *until* you hit the next label (e.g., "Phone:"):
        ```json
        [
          {"type": "command", "name": "anchor_to_text", "args": {"text": "Address:"}},
          {"type": "command", "name": "move_down", "args": {}},
          {
            "type": "loop",
            "condition": {
              "name": "check_current_word_matches_regex",
              "args": {"pattern": "Phone:"},
              "check": false
            },
            "body": [
              {"type": "command", "name": "collect_whole_sentence", "args": {}},
              {"type": "command", "name": "move_down", "args": {}}
            ]
          }
        ]
        ```
    * **Use `if` for Conditional Logic:** When a value might be missing, optional, or have a specific state (e.g., 'N/A', 'Pending').
    * **If Example:** To avoid collecting 'N/A' for an optional field:
        ```json
        [
          {"type": "command", "name": "anchor_to_text", "args": {"text": "Spouse Name:"}},
          {"type": "command", "name": "move_right", "args": {}},
          {
            "type": "if",
            "condition": {
              "name": "check_current_word_matches_regex",
              "args": {"pattern": "(N/A|Not Applicable)"},
              "check": false
            },
            "then": [
              {"type": "command", "name": "collect_trailing_sentence", "args": {}}
            ],
            "else": [
              {"type": "command", "name": "clear_text_buffer", "args": {}}
            ]
          }
        ]
        ```

3.  **Independence:** Each command list for a field (e.g., `"name"`) is executed independently. **Assume the cursor is at (0, 0) at the start of EACH field's execution.**

4. **Accuracy Over Efficiency:** Prioritize accuracy above all—do not economize on the number of commands or actions. Use as many commands, loops, and ifs as necessary to ensure robust extraction, even if it results in longer sequences. The goal is 100% precision across variable layouts, not minimalism.

5.  **Precise Collection:** Use `collect` methods *only* on the words that make up the final value. Do not collect the labels.

6.  **Graceful Failure:** If a schema field (e.g., "phone") is not found in the PDF layout, its command sequence should simply result in no `collect` calls (or a `clear_text_buffer` call), returning `null` or `""`.

---

**EXAMPLE (ONE-SHOT)**

* **Received Schema:**
    ```json
    {
      "name": "Professional's name",
      "inscription": "Inscription number"
    }
    ```
* **Visual Context:** An image showing "SON GOKU" at the top, and further down, the label "Inscrição" with the number "101943" directly below it.

* **Expected JSON Output (Your Response):**
    ```json
    {
      "name": [
        {
          "type": "command",
          "name": "move_first",
          "args": {}
        },
        {
          "type": "command",
          "name": "collect_trailing_sentence",
          "args": {}
        }
      ],
      "inscription": [
        {
          "type": "command",
          "name": "anchor_to_text",
          "args": {
            "text": "Inscrição"
          }
        },
        {
          "type": "command",
          "name": "move_down",
          "args": {
            "jump": 0
          }
        },
        {
          "type": "command",
          "name": "collect",
          "args": {}
        }
      ]
    }
    ```

---

**COMMAND STRUCTURE**

There are 3 types of commands you can use in the lists:

1.  **Standard Command (Action):**
    {
        "type": "command",
        "name": "wordspace_method_name",
        "args": {"arg1": "value1", ...}
    }

2.  **Loop (Conditional Repetition):**
    * **Use Case:** Collect multi-line data or iterate until a condition is met.
    {
        "type": "loop",
        "condition": {
            "name": "check_method",
            "args": {"arg1": "value1", ...},
            "check": true  // Repeats WHILE method_check() == true
        },
        "body": [list of inner commands]
    }

3.  **If (Conditional):**
    * **Use Case:** Handle optional data or avoid collecting "placeholder" text.
    {
        "type": "if",
        "condition": {
            "name": "check_method",
            "args": {"arg1": "value1", ...},
            "check": true // Executes 'then' IF method_check() == true
        },
        "then": [command list if 'check' is true],
        "else": [command list if 'check' is false]
    }

---

**WORDSPACE API (ALLOWED METHODS)**
Use *exclusively* this focused set of methods.

**API CAPABILITY (IMPORTANT):**
Both `anchor_to_text` and `anchor_to_regex` **support multi-word patterns**.
* `anchor_to_text("Data Vencimento")` will find the words "Data" and "Vencimento" side-by-side.
* `anchor_to_regex("Data.*Vencimento")` will also work.

**Strategy:** You should *prefer* multi-word anchors when possible (e.g., "Tipo Operação", "Data Vencimento") as they are more specific and robust than single-word anchors (e.g., "Tipo", "Data").

**What is Normalization?**
When `include_normalized: true` (the default), the search ignores accents and case.
(e.g., "Inscrição" matches "inscricao", "NOME" matches "nome").
Use `include_normalized: false` if the distinction is crucial.

**1. Anchoring Methods (Your Preferred Starting Point)**
* `anchor_to_regex(pattern: str, occurrence: int = 0, include_normalized: bool = True)`: Moves the cursor to the Nth word matching the regex.
* `anchor_to_text(text: str, occurrence: int = 0, include_normalized: bool = True)`: Moves the cursor to the Nth word matching the exact text.
* `anchor_to_nearest()`: Moves to the word physically closest to the current cursor, **ignoring the word the cursor is currently on**. Extremely useful if the value is close to its label but its relative position may vary.
* `move_first()`: Moves to the first word of the document (top-left).
* `move_last()`: Moves to the last word of the document.

**2. Relative Navigation (Fine Movement)**
* `move_right(jump: int = 0)`: Moves to the next word to the right on the same line. Skips N words.
* `move_left(jump: int = 0)`: Moves to the next word to the left on the same line.
* `move_down(jump: int = 0)`: Moves to the next word below in the same column.
* `move_up(jump: int = 0)`: Moves to the next word above in the same column.
* `move_to_sentence_begin()`: Moves to the first word of the current sentence (on the same line).
* `move_to_sentence_end()`: Moves to the last word of the current sentence (on the same line).
* `move_next(jump: int = 0)`: Moves to the (N+1)th word immediately following in the document's internal word order.
* `move_previous(jump: int = 0)`: Moves to the (N+1)th word immediately preceding in the document's internal word order.

**3. Collection Methods (Text Capture)**
* `collect()`: Collects the text of the word currently under the cursor.
* `collect_trailing_sentence()`: Collects the current word and the rest of the sentence to its right.
* `collect_leading_sentence()`: Collects the start of the sentence and the current word.
* `collect_whole_sentence()`: Collects the entire sentence on the line.
* `clear_text_buffer()`: Clears the collected text (use to reset if needed).

**4. Check Methods (For 'condition' in Loops/Ifs)**
* `check_current_word_matches_regex(pattern: str, fallback: bool = True) -> bool`: Checks if the current word matches the regex.
"""
