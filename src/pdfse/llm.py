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

1.  **Independence:** Each command list for a field (e.g., `"name"`) is executed independently. **Assume the cursor is at (0, 0) at the start of EACH field's execution.**
2.  **Efficiency:** Use the fewest commands possible.
3.  **Robustness (Use Anchors):**
    * **Prefer anchors!** Start by using `anchor_to_text` or `anchor_to_regex` to lock onto a fixed *label* in the PDF (e.g., anchor to "Name:", "CPF:", "Inscription").
    * From the anchor, use relative navigation (e.g., `move_right`, `move_down`) to reach the *value*.
    * Avoid using many `move_next` or `move_down` calls from (0, 0), as this is fragile to layout changes.
4.  **Precise Collection:** Use `collect` methods *only* on the words that make up the final value. Do not collect the labels.
5.  **Graceful Failure:** If a schema field (e.g., "phone") is not found in the PDF layout, its command sequence should simply result in no `collect` calls (or a `clear_text_buffer` call), returning `null` or `""`.

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
Use *exclusively* these methods.

**What is Normalization?**
When `include_normalized: true` (the default), the search ignores accents and case.
(e.g., "Inscrição" matches "inscricao", "NOME" matches "nome").
Use `include_normalized: false` if the distinction is crucial.

**1. Anchoring Methods (Your Preferred Starting Point)**
* `anchor_to_regex(pattern: str, occurrence: int = 0, include_normalized: bool = True)`: Moves the cursor to the Nth word matching the regex.
* `anchor_to_text(text: str, occurrence: int = 0, include_normalized: bool = True)`: Moves the cursor to the Nth word matching the exact text.
* `anchor_to_nearest()`: Moves to the word closest to the current cursor.
* `move_first()`: Moves to the first word of the document (top-left).

**2. Relative Navigation (Fine Movement)**
* `move_right(jump: int = 0)`: Moves to the next word to the right on the same line. Skips N words.
* `move_left(jump: int = 0)`: Moves to the next word to the left on the same line.
* `move_down(jump: int = 0)`: Moves to the next word below in the same column.
* `move_up(jump: int = 0)`: Moves to the next word above in the same column.
* `move_next(jump: int = 0)`: Moves to the next word in reading order (ignores layout).
* `move_previous(jump: int = 0)`: Moves to the previous word in reading order.
* `move_to_sentence_begin()`: Moves to the first word of the current sentence (on the same line).
* `move_to_sentence_end()`: Moves to the last word of the current sentence (on the same line).

**3. Collection Methods (Text Capture)**
* `collect()`: Collects the text of the word currently under the cursor.
* `collect_trailing_sentence()`: Collects the current word and the rest of the sentence to its right.
* `collect_leading_sentence()`: Collects the start of the sentence and the current word.
* `collect_whole_sentence()`: Collects the entire sentence on the line.
* `clear_text_buffer()`: Clears the collected text (use to reset if needed).

**4. Check Methods (For 'condition' in Loops/Ifs)**
* `check_current_word_matches_regex(pattern: str, fallback: bool = True) -> bool`: Checks if the current word matches the regex.

**5. Corner Methods (Rarely useful, avoid if possible)**
* `move_cursor_to_corner_left()`
* `move_cursor_to_corner_right()`
* `move_cursor_to_corner_top()`
* `move_cursor_to_corner_bottom()`
* `move_last()`: Moves to the last word in the document.
"""
