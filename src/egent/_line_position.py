"""文本行/列位置计算。"""


def position_after_characters(
    file_lines: list[str],
    start_line: int,
    start_column: int,
    character_count: int,
) -> tuple[int, int]:
    """从起始行列开始消耗指定字符数，返回新的行列位置。"""
    line_index = max(start_line - 1, 0)
    column_index = max(start_column - 1, 0)
    remaining_characters = character_count

    while line_index < len(file_lines):
        current_line = file_lines[line_index]
        available_characters = len(current_line) - column_index
        if remaining_characters < available_characters:
            return line_index + 1, column_index + remaining_characters + 1
        remaining_characters -= available_characters
        line_index += 1
        column_index = 0

    last_line_number = len(file_lines) if file_lines else 1
    return last_line_number, 1
