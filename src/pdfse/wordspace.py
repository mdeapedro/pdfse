import re
from dataclasses import dataclass
from pdfse.utils import point_to_bbox_squared_distance, normalize_text


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


    def _get_current_word(self) -> Word | None:
        cx, cy = self.cursor
        for word in self.words:
            x0, y0, x1, y1 = word.bbox
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                return word


    def _read_cursor(self) -> str | None:
        current_word = self._get_current_word()
        if current_word:
            return current_word.text


    def _get_text(self) -> str:
        return self.text[:-1]


    def _dump_text(self) -> str:
        text = self._get_text()
        self.clear_text_buffer()
        return text


    def _get_sentence_left(self) -> list[Word]:
        current_word = self._get_current_word()
        if not current_word:
            return []
        left_words = []
        while True:
            matches = [w for w in self.words if w.bbox[2] <= current_word.bbox[0] and w.bbox[1] <= self.cursor[1] <= w.bbox[3]]
            if not matches:
                break
            next_left = max(matches, key=lambda w: w.bbox[0])
            height_next = next_left.bbox[3] - next_left.bbox[1]
            height_current = current_word.bbox[3] - current_word.bbox[1]
            if abs(height_next - height_current) / max(height_next, height_current) > 0.1:
                break
            gap = current_word.bbox[0] - next_left.bbox[2]
            if gap > height_current:
                break
            left_words.append(next_left)
            current_word = next_left
        left_words.reverse()
        return left_words


    def _get_sentence_right(self) -> list[Word]:
        current_word = self._get_current_word()
        if not current_word:
            return []
        right_words = []
        while True:
            matches = [w for w in self.words if current_word.bbox[2] <= w.bbox[0] and w.bbox[1] <= self.cursor[1] <= w.bbox[3]]
            if not matches:
                break
            next_right = min(matches, key=lambda w: w.bbox[0])
            height_next = next_right.bbox[3] - next_right.bbox[1]
            height_current = current_word.bbox[3] - current_word.bbox[1]
            if abs(height_next - height_current) / max(height_next, height_current) > 0.1:
                break
            gap = next_right.bbox[0] - current_word.bbox[2]
            if gap > height_current:
                break
            right_words.append(next_right)
            current_word = next_right
        return right_words


    def check_current_word_matches_regex(self, pattern: str, fallback: bool = True) -> bool:
        current_word = self._get_current_word()
        if not current_word:
            return False
        regex = re.compile(pattern, re.IGNORECASE)
        match = bool(regex.search(current_word.text))
        if match or not fallback:
            return match
        regex = re.compile(normalize_text(pattern), re.IGNORECASE)
        match = bool(regex.search(normalize_text(current_word.text)))
        return match


    def collect(self):
        text = self._read_cursor()
        if text:
            self.text += text + " "


    def clear_text_buffer(self):
        self.text = ""


    def move_cursor_to_corner_left(self):
        self.cursor = (0.0, self.cursor[1])


    def move_cursor_to_corner_right(self):
        self.cursor = (self.max_x, self.cursor[1])


    def move_cursor_to_corner_top(self):
        self.cursor = (self.cursor[0], 0.0)


    def move_cursor_to_corner_bottom(self):
        self.cursor = (self.cursor[0], self.max_y)


    def anchor_to_regex(self, pattern: str, occurrence: int = 0, include_normalized: bool = True):
        if include_normalized:
            regex = re.compile(normalize_text(pattern))
            matches = [word for word in self.words if regex.search(normalize_text(word.text))]
        else:
            regex = re.compile(pattern)
            matches = [word for word in self.words if regex.search(word.text)]
        self._move_to_pos(matches, occurrence)


    def anchor_to_text(self, text: str, occurrence: int = 0, include_normalized: bool = True):
        if include_normalized:
            matches = [word for word in self.words if normalize_text(word.text) == normalize_text(text)]
        else:
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


    def move_left(self, jump: int = 0):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            _, y0, x1, y1 = word.bbox
            if x1 < cx and y0 <= cy <= y1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[0], reverse=True)
        self._move_to_pos(matches, jump)


    def move_up(self, jump: int = 0):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            x0, _, x1, y1 = word.bbox
            if y1 < cy and x0 <= cx <= x1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[1], reverse=True)
        self._move_to_pos(matches, jump)


    def move_right(self, jump: int = 0):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            x0, y0, _, y1 = word.bbox
            if cx < x0 and y0 <= cy <= y1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[0])
        self._move_to_pos(matches, jump)


    def move_down(self, jump: int = 0):
        cx, cy = self.cursor
        matches: list[Word] = []
        for word in self.words:
            x0, y0, x1, _ = word.bbox
            if cy < y0 and x0 <= cx <= x1:
                matches.append(word)
        matches.sort(key=lambda word: word.bbox[1])
        self._move_to_pos(matches, jump)


    def move_first(self):
        if self.words:
            self._move_to_word(self.words[0])


    def move_last(self):
        if self.words:
            self._move_to_word(self.words[-1])


    def move_next(self, jump: int = 0):
        cx, cy = self.cursor
        pos = -1
        for idx, word in enumerate(self.words):
            x0, y0, x1, y1 = word.bbox
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                pos = idx
        if pos == -1:
            return
        self._move_to_pos(self.words, pos + jump + 1)


    def move_previous(self, jump: int = 0):
        cx, cy = self.cursor
        pos = -1
        for idx, word in enumerate(self.words):
            x0, y0, x1, y1 = word.bbox
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                pos = idx
        if pos == -1:
            return
        self._move_to_pos(self.words, pos - jump - 1)


    def move_to_sentence_begin(self):
        sentence_left = self._get_sentence_left()
        if sentence_left:
            self._move_to_word(sentence_left[0])


    def move_to_sentence_end(self):
        sentence_right = self._get_sentence_right()
        if sentence_right:
            self._move_to_word(sentence_right[-1])


    def collect_trailing_sentence(self):
        self.collect()
        sentence_right = self._get_sentence_right()
        for word in sentence_right:
            self.text += word.text + " "


    def collect_leading_sentence(self):
        sentence_left = self._get_sentence_left()
        for word in sentence_left:
            self.text += word.text + " "
        self.collect()


    def collect_whole_sentence(self):
        self.collect_leading_sentence()
        sentence_right = self._get_sentence_right()
        for word in sentence_right:
            self.text += word.text + " "
