import re
from dataclasses import dataclass
from pdfse.utils import point_to_bbox_squared_distance


@dataclass
class Word:
    text: str
    bbox: tuple[float, float, float, float]


class WordSpace:
    def __init__(self, words: list[Word], max_x: float, max_y: float):
        self.words: list[Word] = words
        self.cursor: tuple[float, float] = (0.0, 0.0)
        self.text: str = ""
        self.max_x: float = max_x
        self.max_y: float = max_y


    def _move_to_word(self, word: Word):
        x0, y0, x1, y1 = word.bbox
        center_x = (x0 + x1) / 2
        center_y = (y0 + y1) / 2
        self.cursor = (center_x, center_y)


    def _move_to_pos(self, words: list[Word], pos: int):
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


    def check_current_word_matches_regex(self, pattern: str) -> bool:
        current_word = self.get_current_word()
        if not current_word:
            return False
        regex = re.compile(pattern, re.IGNORECASE)
        match = bool(regex.search(current_word.text))
        return match


    def check_current_word_does_not_match_regex(self, pattern: str) -> bool:
        return not self.check_current_word_matches_regex(pattern)


    def collect(self):
        text = self.read_cursor()
        if text:
            self.text += text + " "


    def erase_text(self):
        self.text = ""


    def get_text(self) -> str:
        return self.text[:-1]


    def dump_text(self) -> str:
        text = self.get_text()
        self.erase_text()
        return text


    def move_cursor_to_corner_left(self):
        self.cursor = (0.0, self.cursor[1])


    def move_cursor_to_corner_right(self):
        self.cursor = (self.max_x, self.cursor[1])


    def move_cursor_to_corner_top(self):
        self.cursor = (self.cursor[0], 0.0)


    def move_cursor_to_corner_bottom(self):
        self.cursor = (self.cursor[0], self.max_y)


    def anchor_to_regex(self, pattern: str, occurrence: int = 0):
        regex = re.compile(pattern)
        matches = [word for word in self.words if regex.search(word.text)]
        self._move_to_pos(matches, occurrence)


    def anchor_to_text(self, text: str, occurrence: int = 0):
        matches = [word for word in self.words if word.text == text]
        self._move_to_pos(matches, occurrence)


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
        self._move_to_pos(matches, words)


    def move_above(self, words: int = 1):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            x0, _, x1, y1 = word.bbox
            if y1 <= cy and x0 <= cx <= x1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[1], reverse=True)
        self._move_to_pos(matches, words)


    def move_right(self, words: int = 1):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            x0, y0, _, y1 = word.bbox
            if cx <= x0 and y0 <= cy <= y1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[0])
        self._move_to_pos(matches, words)


    def move_below(self, words: int = 1):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            x0, y0, x1, _ = word.bbox
            if cy <= y0 and x0 <= cx <= x1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[1])
        self._move_to_pos(matches, words)


    def move_next(self, words: int = 1):
        cx, cy = self.cursor
        pos = -1
        for idx, word in enumerate(self.words):
            x0, y0, x1, y1 = word.bbox
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                pos = idx
        if pos == -1:
            return
        self._move_to_pos(self.words, pos + words)


    def collect_sentence(self, add_left_words: bool=True):
        for word in self.get_current_sentence(add_left_words):
            text = word.text
            self.text += text + " "


    def get_current_sentence(self, add_left_words: bool=True) -> list[Word]:
        cx, cy = self.cursor
        current_word = None
        for word in self.words:
            x0, y0, x1, y1 = word.bbox
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                current_word = word
                break
        if not current_word:
            return []
        left_words = []
        if add_left_words:
            current = current_word
            while True:
                matches = [w for w in self.words if w.bbox[2] <= current.bbox[0] and w.bbox[1] <= cy <= w.bbox[3]]
                if not matches:
                    break
                next_left = max(matches, key=lambda w: w.bbox[0])
                height_next = next_left.bbox[3] - next_left.bbox[1]
                height_current = current.bbox[3] - current.bbox[1]
                if abs(height_next - height_current) / max(height_next, height_current) > 0.1:
                    break
                gap = current.bbox[0] - next_left.bbox[2]
                if gap > height_current:
                    break
                left_words.append(next_left)
                current = next_left
        left_words.reverse()
        right_words = []
        current = current_word
        while True:
            matches = [w for w in self.words if current.bbox[2] <= w.bbox[0] and w.bbox[1] <= cy <= w.bbox[3]]
            if not matches:
                break
            next_right = min(matches, key=lambda w: w.bbox[0])
            height_next = next_right.bbox[3] - next_right.bbox[1]
            height_current = current.bbox[3] - current.bbox[1]
            if abs(height_next - height_current) / max(height_next, height_current) > 0.1:
                break
            gap = next_right.bbox[0] - current.bbox[2]
            if gap > height_current:
                break
            right_words.append(next_right)
            current = next_right
        return left_words + [current_word] + right_words
