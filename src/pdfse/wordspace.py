from dataclasses import dataclass
import re

@dataclass
class Word:
    text: str
    bbox: tuple[float, float, float, float]

class WordSpace:

    def __init__(self):
        self.words: list[Word] = []
        self.cursor: tuple[float, float] = (0.0, 0.0)
        self.text: str = ""

    def _move_to_word(self, word: Word):
        x0, y0, x1, y1 = word.bbox
        center_x = (x0 + x1) / 2
        center_y = (y0 + y1) / 2
        self.cursor = (center_x, center_y)

    def _move_to_next(self, words: list[Word], pos: int):
        if not words:
            return
        pos = max(0, min(pos, len(words) - 1))
        word = words[pos]
        self._move_to_word(word)

    def collect(self):
        cx, cy = self.cursor
        for word in self.words:
            x0, y0, x1, y1 = word.bbox
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                self.text += word.text + " "
                return

    def anchor_to_regex(self, pattern: str, occurrence: int = 0):
        regex = re.compile(pattern)
        matches = [word for word in self.words if regex.search(word.text)]
        self._move_to_next(matches, occurrence)

    def anchor_to_text(self, text: str, occurrence: int = 0):
        matches = [word for word in self.words if word == text]
        self._move_to_next(matches, occurrence)

    def move_right(self, words: int = 1):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            x0, y0, _, y1 = word.bbox
            if x0 <= cx and y0 <= cy <= y1:
                matches.append(word)
        self._move_to_next(matches, words)
