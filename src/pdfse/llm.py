def prompt() -> str:
    return """Você está desenvolvendo uma solução para extrair informações estruturadas de PDFs usando uma abordagem heurística baseada em uma classe chamada WordSpace. Sua tarefa é gerar uma heurística personalizada para um tipo específico de documento, com base em imagens PNG que representam o PDF renderizado apenas com texto (sem elementos gráficos, apenas as palavras posicionadas).

Você receberá:
- Uma ou mais imagens PNG do PDF, mostrando apenas o texto extraído e posicionado como no documento original.
- Um extraction_schema: um dicionário JSON onde as chaves são os nomes dos campos a serem extraídos, e os valores são descrições textuais desses campos (ex.: "nome": "Nome completo da pessoa").

Com base nisso, você deve criar uma heurística que usa métodos da classe WordSpace para navegar pelo espaço de palavras do PDF, posicionar um cursor, coletar textos e extrair os valores dos campos. O cursor começa sempre na posição (0, 0), que é o canto superior-esquerdo da página (coordenadas crescem para a direita em X e para baixo em Y).

Sua resposta deve ser **exclusivamente um JSON válido**, sem texto adicional. A estrutura do JSON deve ser fixa:
{
  "campo1": [lista de comandos para extrair campo1],
  "campo2": [lista de comandos para extrair campo2],
  ...
}

Cada lista de comandos é uma sequência de estruturas JSON que representam ações a serem executadas em ordem. Existem três tipos de comandos:
- **Comandos padrão**: Chamadas a métodos da WordSpace.  Estrutura:
{
    "type": "command",
    "name": "nome_do_metodo",
    "args": {"arg1": valor1, "arg2": valor2, ...} (use apenas métodos válidos da WordSpace; args opcionais conforme o método).
}

- **Comandos de loop**: Para repetições condicionais. Estrutura:
{
    "type": "loop",
    "condition": {
        "name": "nome_do_metodo_check",
        "args": {"arg1": valor1, ...},
        "check": true ou false
    },
    "body": [lista de comandos internos. Repete sequencialmente enquanto metodo_check() == check]
}
- **Comandos de if**: Para condicionais. Estrutura:
{
    "type": "if",
    "condition": {
        "name": "nome_do_metodo_check",
        "args": {"arg1": valor1, ...},
        "check": true ou false
    },
    "then": [lista de comandos se metodo_check == check],
    "else": [lista de comandos caso contrário] (se não precisar de else, deixar lista vazia)
}.

Os comandos devem ser eficientes, minimizar movimentos desnecessários e focar em navegar pelo layout do documento para coletar exatamente o valor de cada campo.  Após a sequência de comandos para um campo, assume-se que o texto coletado (via métodos como collect) representa o valor extraído. Se um campo não existir, a sequência deve levar a uma coleta vazia ou null.

Lembre-se: o JSON deve ser estritamente válido e seguir essa estrutura fixa. Não inclua explicações, apenas o JSON.

Métodos Disponíveis na Classe WordSpace:
Você pode usar apenas os seguintes métodos nas suas sequências de comandos. Cada método manipula a posição do cursor, coleta texto ou verifica condições. O cursor começa em (0, 0) (canto superior-esquerdo). Coordenadas: X aumenta para a direita, Y aumenta para baixo. Todas as bboxes são (x0, y0, x1, y1), onde (x0, y0) é o canto superior-esquerdo, (x1, y1) é o canto inferior-direito da palavra.

-- Métodos Check (Use para condições em loops ou ifs.) --
- check_current_word_matches_regex(pattern: str, fallback: bool = True) -> bool: Verifica se a palavra na posição atual do cursor corresponde ao padrão regex. Se fallback=True, também tenta texto normalizado (removendo acentos, tornando tudo minúsculo etc.).

-- Métodos Collect (Use para incrementar a resposta) --
collect(): Anexa o texto da palavra atual (no cursor) ao buffer de texto interno, seguido de um espaço.
collect_trailing_sentence(): Coleta a palavra atual e todas as palavras seguintes na sentença (à direita).
collect_leading_sentence(): Coleta todas as palavras anteriores na sentença (à esquerda) e a palavra atual.
collect_whole_sentence(): Coleta a sentença inteira.
clear_text_buffer(): Limpa o buffer de texto interno. Use, se necessário, para resetar e retornar caso o campo não tenha sido encontrado. Não é necessário chamar no início de cada extração.

-- Métodos de navegação (Use para posicionar o cursor) --
move_cursor_to_corner_left(): Move o cursor para a borda esquerda (x=0, mantém y).
move_cursor_to_corner_right(): Move o cursor para a borda direita (x=max_x, mantém y).
move_cursor_to_corner_top(): Move o cursor para a borda superior (y=0, mantém x).
move_cursor_to_corner_bottom(): Move o cursor para a borda inferior (y=max_y, mantém x).
anchor_to_regex(pattern: str, occurrence: int = 0, include_normalized: bool = True): Move o cursor para o centro da palavra que corresponde ao regex. Se include_normalized=True, inclui textos normalizados. occurrence seleciona a n-ésima correspondência (0-based, ordenado por ordem de leitura).
anchor_to_text(text: str, occurrence: int = 0, include_normalized: bool = True): Move o cursor para o centro da palavra que corresponde exatamente ao texto. Se include_normalized=True, inclui textos normalizados. occurrence seleciona a n-ésima correspondência.
anchor_to_nearest(): Move o cursor para a palavra mais próxima do cursor.
move_left(jump: int = 0): Move o cursor para a próxima palavra à esquerda. Pula 'jump' palavras.
move_up(jump: int = 0): Move o cursor para a próxima palavra acima.
move_right(jump: int = 0): Move o cursor para a próxima palavra à direita.
move_down(jump: int = 0): Move o cursor para a próxima palavra abaixo.
move_first(): Move o cursor para a primeira palavra na ordem de leitra (superior-esquerda).
move_last(): Move o cursor para a última palavra na ordem de leitura (inferior-direita).
move_next(jump: int = 0): Move o cursor para a próxima palavra na ordem de leitura. Pula 'jump' palavras.
move_previous(jump: int = 0): Move o cursor para a palavra anterior na ordem de leitura. Pula 'jump' palavras.
move_to_sentence_begin(): Move o cursor para o início da sentença atual (palavras à esquerda na linha, altura/gap semelhantes).
move_to_sentence_end(): Move o cursor para o fim da sentença atual (palavras à direita na linha).

Após executar a sequência para um campo, o sistema automaticamente descarregará o buffer de texto para obter o valor extraído (trimado). Se não houver chamadas de collect, o valor é null. Foque em passos mínimos; evite loops/ifs a menos que o layout varie."""
