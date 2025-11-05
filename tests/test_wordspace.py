import pytest
from pdfse.wordspace import Word, WordSpace

@pytest.fixture
def sample_words():
    # A predictable 3x3 grid-like layout
    # (10,10) "Word"   (30,10) "1"      (50,10) "Two"
    # (10,30) "Line"   (30,30) "2"      (50,30) "Three"
    # (10,50) "Inscrição" (30,50) "123" (50,50) "End"
    return [
        Word("Word", (10, 10, 20, 20)),      # 0
        Word("1", (30, 10, 40, 20)),         # 1
        Word("Two", (50, 10, 60, 20)),       # 2
        Word("Line", (10, 30, 20, 40)),      # 3
        Word("2", (30, 30, 40, 40)),         # 4
        Word("Three", (50, 30, 60, 40)),     # 5
        Word("Inscrição", (10, 50, 25, 60)), # 6
        Word("123", (30, 50, 40, 60)),       # 7
        Word("End", (50, 50, 60, 60)),       # 8
    ]

@pytest.fixture
def sample_wordspace(sample_words):
    ws = WordSpace(sample_words, 100, 100)
    return ws

def _get_word_at_cursor(ws: WordSpace) -> Word | None:
    return ws._get_current_word()

def test_initial_state(sample_wordspace):
    assert sample_wordspace.cursor == (0.0, 0.0)
    assert sample_wordspace.text == ""
    assert _get_word_at_cursor(sample_wordspace) is None

def test_reset_cursor(sample_wordspace):
    ws = sample_wordspace
    ws.move_first()
    assert ws.cursor != (0.0, 0.0)
    ws.reset_cursor()
    assert ws.cursor == (0.0, 0.0)

def test_collect_and_clear(sample_wordspace):
    ws = sample_wordspace
    ws.move_first()
    ws.collect()
    assert ws.text == "Word "
    ws.move_next()
    ws.collect()
    assert ws.text == "Word 1 "
    ws.clear_text_buffer()
    assert ws.text == ""

def test_move_first_last(sample_wordspace):
    ws = sample_wordspace
    ws.move_first()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Word"
    assert word == ws.words[0]

    ws.move_last()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "End"
    assert word == ws.words[-1]

def test_move_next_previous(sample_wordspace):
    ws = sample_wordspace
    ws.move_first()
    ws.move_next()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "1"

    ws.move_next(jump=1)
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Line"

    ws.move_previous()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Two"

def test_navigation_moves(sample_wordspace):
    ws = sample_wordspace
    ws.move_first()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Word"

    ws.move_right()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "1"

    ws.move_down()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "2"

    ws.move_down()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "123"

    ws.move_up()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "2"

    ws.move_left()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Line"

    ws.move_left()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Line"

def test_navigation_jump(sample_wordspace):
    ws = sample_wordspace
    ws.move_first()

    ws.move_right(jump=1)
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Two"

    ws.move_down(jump=1)
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "End"

def test_anchor_to_text(sample_wordspace):
    ws = sample_wordspace
    ws.anchor_to_text("Line")
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Line"

    ws.anchor_to_text("inscricao")
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Inscrição"

    ws.reset_cursor()
    ws.anchor_to_text("inscricao", include_normalized=False)
    word = _get_word_at_cursor(ws)
    assert word is None

    ws.anchor_to_text("Inscrição", include_normalized=False)
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Inscrição"


def test_anchor_to_text_multi_word(sample_wordspace):
    ws = sample_wordspace
    ws.anchor_to_text("Line 2")
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Line"

    ws.move_next()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "2"

def test_anchor_to_regex(sample_wordspace):
    ws = sample_wordspace
    ws.anchor_to_regex(r"Th.ee")
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Three"

    ws.anchor_to_regex(r"\d+")
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "1"

    ws.anchor_to_regex(r"\d+", occurrence=1)
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "2"

    ws.anchor_to_regex(r"\d+", occurrence=2)
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "123"

    ws.anchor_to_regex(r"inscricao")
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Inscrição"

def test_anchor_to_nearest(sample_wordspace):
    ws = sample_wordspace
    ws.reset_cursor()

    # Test 1: From (0,0), nearest is "Word"
    ws.anchor_to_nearest()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Word"

    # Test 2: From "Inscrição", nearest is "123"
    ws.anchor_to_text("Inscrição")
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Inscrição"

    ws.anchor_to_nearest() # Nearest to "Inscrição" is "123"
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "123"

def test_check_current_word_matches_regex(sample_wordspace):
    ws = sample_wordspace
    assert ws.check_current_word_matches_regex(r"Word") is False

    ws.move_first()
    assert ws.check_current_word_matches_regex(r"Word") is True
    assert ws.check_current_word_matches_regex(r"ord") is True
    assert ws.check_current_word_matches_regex(r"^W.rd$") is True
    assert ws.check_current_word_matches_regex(r"Fail") is False

    ws.anchor_to_text("Inscrição")
    assert ws.check_current_word_matches_regex(r"inscricao") is True
    assert ws.check_current_word_matches_regex(r"inscricao", fallback=False) is False

def test_sentence_collection(sample_wordspace):
    ws = sample_wordspace
    ws.anchor_to_text("2")

    ws.collect_trailing_sentence()
    assert ws.text == "2 Three "

    ws.clear_text_buffer()
    ws.collect_leading_sentence()
    assert ws.text == "Line 2 "

    ws.clear_text_buffer()
    ws.collect_whole_sentence()
    assert ws.text == "Line 2 Three "

def test_sentence_moves(sample_wordspace):
    ws = sample_wordspace
    ws.anchor_to_text("2")

    ws.move_to_sentence_begin()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Line"

    ws.anchor_to_text("2")
    ws.move_to_sentence_end()
    word = _get_word_at_cursor(ws)
    assert word is not None
    assert word.text == "Three"

def test_dump_text(sample_wordspace):
    ws = sample_wordspace
    ws.move_first()
    ws.collect()
    ws.move_next()
    ws.collect()
    assert ws.text == "Word 1 "

    dumped = ws._dump_text()
    assert dumped == "Word 1"
    assert ws.text == ""
