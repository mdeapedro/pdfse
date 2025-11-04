from typing import Any, Callable
from pdfse.wordspace import WordSpace

class HeuristicMachine:
    def __init__(self, wordspace: WordSpace):
        self.wordspace = wordspace
        self.methods: dict[str, Callable[..., None]] = {
            "anchor_to_regex": wordspace.anchor_to_regex,
            "anchor_to_text": wordspace.anchor_to_text,
            "anchor_to_nearest": wordspace.anchor_to_nearest,
            "move_first": wordspace.move_first,
            "move_right": wordspace.move_right,
            "move_left": wordspace.move_left,
            "move_down": wordspace.move_down,
            "move_up": wordspace.move_up,
            "move_next": wordspace.move_next,
            "move_previous": wordspace.move_previous,
            "move_to_sentence_begin": wordspace.move_to_sentence_begin,
            "move_to_sentence_end": wordspace.move_to_sentence_end,
            "collect": wordspace.collect,
            "collect_trailing_sentence": wordspace.collect_trailing_sentence,
            "collect_leading_sentence": wordspace.collect_leading_sentence,
            "collect_whole_sentence": wordspace.collect_whole_sentence,
            "clear_text_buffer": wordspace.clear_text_buffer,
            "move_cursor_to_corner_left": wordspace.move_cursor_to_corner_left,
            "move_cursor_to_corner_right": wordspace.move_cursor_to_corner_right,
            "move_cursor_to_corner_top": wordspace.move_cursor_to_corner_top,
            "move_cursor_to_corner_bottom": wordspace.move_cursor_to_corner_bottom,
            "move_last": wordspace.move_last,
        }
        self.checks: dict[str, Callable[..., bool]] = {
            "check_current_word_matches_regex": self.wordspace.check_current_word_matches_regex,
        }


    def _check_condition(self, condition: dict[str, Any]) -> bool:
        check_name = condition.get("name")
        check_args = condition.get("args", {})
        expected_result = condition.get("check", True)

        if not check_name or check_name not in self.checks:
            return False

        check_func = self.checks[check_name]
        try:
            result = check_func(**check_args)
            return result == expected_result
        except Exception:
            return False

    def _execute_command(self, command: dict[str, Any]):
        cmd_type = command.get("type")

        if cmd_type == "command":
            cmd_name = command.get("name")
            cmd_args = command.get("args", {})

            if not cmd_name or cmd_name not in self.methods:
                return

            cmd_func = self.methods[cmd_name]
            try:
                cmd_func(**cmd_args)
            except Exception:
                return

        elif cmd_type == "loop":
            condition = command.get("condition")
            body = command.get("body")
            if not condition or not body:
                return

            max_iterations = 100
            count = 0
            while self._check_condition(condition) and count < max_iterations:
                self._execute_command_list(body)
                count += 1

        elif cmd_type == "if":
            condition = command.get("condition")
            then_branch = command.get("then")
            else_branch = command.get("else")

            if not condition or not then_branch:
                return

            if self._check_condition(condition):
                self._execute_command_list(then_branch)
            elif else_branch:
                self._execute_command_list(else_branch)

    def _execute_command_list(self, commands: list[dict[str, Any]]):
        if not isinstance(commands, list):
            return
        for command in commands:
            if isinstance(command, dict):
                self._execute_command(command)

    def run(self, heuristic: dict[str, list[dict[str, Any]]]) -> dict[str, str | None]:
        extracted_schema: dict[str, str | None] = {}

        if not isinstance(heuristic, dict):
            return extracted_schema

        for field, commands in heuristic.items():
            self.wordspace.move_cursor_to_corner_top()
            self.wordspace.move_cursor_to_corner_left()
            self.wordspace.clear_text_buffer()

            try:
                self._execute_command_list(commands)
                extracted_text = self.wordspace._dump_text()

                if not extracted_text:
                    extracted_schema[field] = None
                else:
                    extracted_schema[field] = extracted_text.strip()

            except Exception:
                extracted_schema[field] = None

        return extracted_schema
