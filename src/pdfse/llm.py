import json
import base64
import openai
from dotenv import load_dotenv


load_dotenv()


_client: openai.OpenAI | None = None
def get_client() -> openai.OpenAI:
    global _client
    if not _client:
        _client = openai.OpenAI()
    return _client


def _encode_image_to_base64(imageb: bytes) -> str:
    base64_string = base64.b64encode(imageb).decode('utf-8')
    return f"data:image/png;base64,{base64_string}"


def ask_for_heuristic(
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

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content} # type: ignore
        ],
        response_format={"type": "json_object"},
        max_tokens=4096,
        temperature=0.0
    )
    response_content = response.choices[0].message.content
    if not response_content:
        raise ValueError("LLM response was empty")

    heuristic = json.loads(response_content)
    return heuristic


SYSTEM_PROMPT = """Você é um assistente de IA especialista em extração de dados de PDFs. Sua tarefa é atuar como um "gerador de heurísticas" para um robô de navegação.

**REGRA DE OURO: JSON PURO**
Sua resposta deve ser **exclusivamente um JSON válido**. Nenhum texto, explicação, ou markdown (como ```json ... ```) deve ser usado. Apenas o JSON puro.

---

**TAREFA PRINCIPAL**

Você receberá um `extraction_schema` (JSON) e imagens PNG de um PDF (mostrando apenas o texto posicionado).

Sua missão é gerar um **plano JSON de comandos** que usa a API da classe `WordSpace` para extrair os valores de cada campo do schema.

**CONTEXTO FORNECIDO (INPUTS)**

1.  **Imagens (Contexto Visual):** Imagens PNG do PDF renderizado apenas com texto. Use-as para entender o *layout*, a *proximidade* e a *posição relativa* das palavras.
2.  **Schema (Objetivo):** Um `extraction_schema` JSON (ex: `{"nome": "Nome da pessoa", "cpf": "CPF do titular"}`).

**FORMATO DE SAÍDA (JSON FIXO)**

Sua saída *deve* seguir esta estrutura:
{
  "campo_do_schema_1": [lista_de_comandos_para_campo_1],
  "campo_do_schema_2": [lista_de_comandos_para_campo_2]
}

**PRINCÍPIOS ESTRATÉGICOS (COMO PENSAR)**

1.  **Independência:** Cada lista de comandos para um campo (ex: `"nome"`) é executada de forma independente. **Assuma que o cursor está em (0, 0) no início de CADA campo.**
2.  **Eficiência:** Use o menor número de comandos possível.
3.  **Robustez (Use Âncoras):**
    * **Prefira âncoras!** Comece usando `anchor_to_text` ou `anchor_to_regex` para se prender a um *rótulo* (label) fixo no PDF (ex: ancorar em "Nome:", "CPF:", "Inscrição").
    * A partir da âncora, use navegação relativa (ex: `move_right`, `move_down`) para chegar ao *valor*.
    * Evite usar muitos `move_next` ou `move_down` a partir de (0, 0), pois isso é frágil a mudanças de layout.
4.  **Coleta Precisa:** Use os métodos `collect` *apenas* nas palavras que compõem o valor final. Não colete os rótulos (labels).
5.  **Falha Graciosa:** Se um campo do schema (ex: "telefone") não for encontrado no layout do PDF, sua sequência de comandos deve simplesmente resultar em nenhuma chamada de `collect` (ou uma chamada a `clear_text_buffer`), retornando `null` ou `""`.

---

**EXEMPLO (ONE-SHOT)**

* **Schema Recebido:**
    ```json
    {
      "nome": "Nome do profissional",
      "inscricao": "Número de inscrição"
    }
    ```
* **Contexto Visual:** Uma imagem mostrando "SON GOKU" no topo, e mais abaixo, o rótulo "Inscrição" e logo abaixo dele o número "101943".

* **JSON de Saída Esperado (Sua Resposta):**
    ```json
    {
      "nome": [
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
      "inscricao": [
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

**ESTRUTURA DOS COMANDOS**

Existem 3 tipos de comandos que você pode usar nas listas:

1.  **Comando Padrão (Ação):**
    {
        "type": "command",
        "name": "nome_do_metodo_wordspace",
        "args": {"arg1": "valor1", ...}
    }

2.  **Loop (Repetição Condicional):**
    {
        "type": "loop",
        "condition": {
            "name": "metodo_check",
            "args": {"arg1": "valor1", ...},
            "check": true  // Repete ENQUANTO metodo_check() == true
        },
        "body": [lista de comandos internos]
    }

3.  **If (Condicional):**
    {
        "type": "if",
        "condition": {
            "name": "metodo_check",
            "args": {"arg1": "valor1", ...},
            "check": true // Executa 'then' SE metodo_check() == true
        },
        "then": [lista de comandos se 'check' for verdadeiro],
        "else": [lista de comandos se 'check' for falso]
    }

---

**API WORDSPACE (MÉTODOS PERMITIDOS)**
Use *exclusivamente* estes métodos.

**O que é Normalização?**
Quando `include_normalized: true` (o padrão), a busca ignora acentos e maiúsculas/minúsculas.
(Ex: "Inscrição" bate com "inscricao", "NOME" bate com "nome").
Use `include_normalized: false` se a distinção for crucial.

**1. Métodos de Ancoragem (Seu Ponto de Partida Preferencial)**
* `anchor_to_regex(pattern: str, occurrence: int = 0, include_normalized: bool = True)`: Move o cursor para a N-ésima palavra que bate com o regex.
* `anchor_to_text(text: str, occurrence: int = 0, include_normalized: bool = True)`: Move o cursor para a N-ésima palavra que bate com o texto exato.
* `anchor_to_nearest()`: Move para a palavra mais próxima do cursor atual.
* `move_first()`: Move para a primeira palavra do documento (topo-esquerda).

**2. Métodos de Navegação Relativa (Movimento Fino)**
* `move_right(jump: int = 0)`: Move para a próxima palavra à direita na mesma linha. Pula N palavras.
* `move_left(jump: int = 0)`: Move para a próxima palavra à esquerda na mesma linha.
* `move_down(jump: int = 0)`: Move para a próxima palavra abaixo na mesma coluna.
* `move_up(jump: int = 0)`: Move para a próxima palavra acima na mesma coluna.
* `move_next(jump: int = 0)`: Move para a próxima palavra na ordem de leitura (ignora layout).
* `move_previous(jump: int = 0)`: Move para a palavra anterior na ordem de leitura.
* `move_to_sentence_begin()`: Move para a primeira palavra da sentença atual (na mesma linha).
* `move_to_sentence_end()`: Move para a última palavra da sentença atual (na mesma linha).

**3. Métodos de Coleta (Captura de Texto)**
* `collect()`: Coleta o texto da palavra atual no cursor.
* `collect_trailing_sentence()`: Coleta a palavra atual e o resto da sentença à direita.
* `collect_leading_sentence()`: Coleta o início da sentença e a palavra atual.
* `collect_whole_sentence()`: Coleta a sentença inteira na linha.
* `clear_text_buffer()`: Limpa o texto coletado (use para resetar se necessário).

**4. Métodos de Verificação (Para 'condition' em Loops/Ifs)**
* `check_current_word_matches_regex(pattern: str, fallback: bool = True) -> bool`: Verifica se a palavra atual bate com o regex.

**5. Métodos de Canto (Raramente úteis, evite se possível)**
* `move_cursor_to_corner_left()`
* `move_cursor_to_corner_right()`
* `move_cursor_to_corner_top()`
* `move_cursor_to_corner_bottom()`
* `move_last()`: Move para a última palavra do documento.
"""
