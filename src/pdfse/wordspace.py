import re
from dataclasses import dataclass
from pdfse.utils import point_to_bbox_squared_distance


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


    def get_current_word(self) -> Word | None:
        cx, cy = self.cursor
        for word in self.words:
            x0, y0, x1, y1 = word.bbox
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                return word


    def read_cursor(self) -> str | None:
        current_word = self.get_current_word()
        if current_word:
            return current_word.text


    def collect(self):
        text = self.read_cursor()
        if text:
            self.text += text + " "


    def get_text(self) -> str:
        return self.text[:-1]


    def dump_text(self) -> str:
        text = self.get_text()
        self.text = ""
        return text


    def anchor_to_regex(self, pattern: str, occurrence: int = 0):
        regex = re.compile(pattern)
        matches = [word for word in self.words if regex.search(word.text)]
        self._move_to_next(matches, occurrence)


    def anchor_to_text(self, text: str, occurrence: int = 0):
        matches = [word for word in self.words if word.text == text]
        self._move_to_next(matches, occurrence)


    def anchor_to_nearest(self):
        if not self.words:
            return
        nearest_word = self.words[0]
        min_sq_dist = 1e18
        for word in self.words:
            sq_dist = point_to_bbox_squared_distance(self.cursor, word.bbox)
            if (sq_dist < min_sq_dist):
                nearest_word = word
                min_sq_dist = sq_dist
        self._move_to_word(nearest_word)


    def move_left(self, words: int = 1):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            _, y0, x1, y1 = word.bbox
            if x1 <= cx and y0 <= cy <= y1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[0], reverse=True)
        self._move_to_next(matches, words)


    def move_top(self, words: int = 1):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            x0, _, x1, y1 = word.bbox
            if y1 <= cy and x0 <= cx <= x1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[1], reverse=True)
        self._move_to_next(matches, words)


    def move_right(self, words: int = 1):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            x0, y0, _, y1 = word.bbox
            if cx <= x0 and y0 <= cy <= y1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[0])
        self._move_to_next(matches, words)


    def move_bottom(self, words: int = 1):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            x0, y0, x1, _ = word.bbox
            if cy <= y0 and x0 <= cx <= x1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[1])
        self._move_to_next(matches, words)
