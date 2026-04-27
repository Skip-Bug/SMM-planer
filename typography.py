r"""Модуль преобразователь текста.

Убирает лишние пробелы, меняет (-) на (—)
Вместо " грамотно ставит «...»
Примеры использования в консоли
    python typography.py "Тут \"кто-то\" и - то \"еще кавычки\" - мир!"
    или
    echo '"Тут "кто-то" и - то "еще кавычки" - мир!"' | python typography.py
"""

import re


def replaced_spacing(raw_text):
    """Убирает лишние пробелы."""
    return ' '.join(raw_text.split())


def replaced_dashes(line):
    """Заменяет дефисы на типографские тире.

    Обработанные случаи:
        - Диапазоны: 10-20 → 10–20
        - Инициалы: А. - Б. → А. Б.
        - Обычное тире: слово - слово → слово — слово

    Args:
        line (str): Строка с дефисами.

    Returns:
        str: Строка с правильными тире.
    """
    line = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1–\2', line)
    line = re.sub(r'(\b[А-Яа-я]\.)\s+[-–—]\s+([А-Яа-я]\.\b)', r'\1 \2', line)
    line = re.sub(r'\s+[-–—]\s+', ' — ', line)
    return line


def frag_alt_quotes(fragment, punct_inside=True):
    """Заменяет прямые кавычки " и ' на « и » с учётом вложенности.

    Использует стек для отслеживания уровней цитирования.
    Определяет тип кавычки по прилипанию к буквам:
        - открывающая: перед кавычкой НЕ буква/цифра, после – буква/цифра
        - закрывающая: перед буква/цифра, после НЕ буква/цифра
    В неоднозначных случаях решает стек.

    Args:
        fragment (str): Текст с прямыми кавычками.

    Returns:
        str: Текст с «ёлочками».
    """
    result = []
    stack = []
    n = len(fragment)
    for i, ch in enumerate(fragment):
        if ch not in ('"', "'"):
            result.append(ch)
            continue
        prev_char = fragment[i-1] if i > 0 else ''
        next_char = fragment[i+1] if i+1 < n else ''
        prev_is_word = prev_char.isalnum() or prev_char in ('.', '!', '?')
        next_is_word = next_char.isalnum()

        if not prev_is_word and next_is_word:
            result.append('«')
            stack.append(True)
        elif prev_is_word and not next_is_word:
            # Если перед закрывающей кавычкой стоит знак и хотим его внутрь
            if stack and punct_inside and prev_char in ('.', '!', '?'):
                # Меняем местами: знак препинания и кавычка
                punct = result.pop()
                result.append(f'{punct}»')
            else:
                result.append('»')
            if stack:
                stack.pop()
        else:
            if not stack and (next_char == '' or next_char.isspace()):
                result.append('»')
            elif stack:
                result.append('»')
                stack.pop()
            else:
                result.append('«')
                stack.append(True)
    return ''.join(result)


def format_quoted_line(spaces, body, tail, punct_inside):
    """Оборачивает тело цитаты в «» с учётом пунктуации и добавляет хвост.

    Args:
        spaces (str): Пробелы перед открывающей кавычкой.
        body (str): Содержимое цитаты (без внешних кавычек).
        tail (str): Текст после закрывающей кавычки.
        punct_inside (bool): Если True, знаки .!? остаются внутри кавычек.

    Returns:
        str: Отформатированная строка с кавычками.
    """
    inner = frag_alt_quotes(body, punct_inside)
    end_punct = re.search(r'([.!?]+)$', inner)
    if end_punct and punct_inside:
        punct = end_punct.group(1)
        clean_inner = inner[:-len(punct)]
        return f"{spaces}«{clean_inner}{punct}»{tail}"
    else:
        return f"{spaces}«{inner}»{tail}"


def try_wrap_quotes(line, punct_inside):
    """Обрабатывает строку с прямыми кавычками.

    Если строка начинается с кавычки и имеет парную закрывающую,
        возвращает обработанную строку как внешнюю цитату, иначе None.

    Args:
        line (str): Строка текста.
        punct_inside (bool): Флаг для передачи в format_quoted_line.

    Returns:
        str or None: Обработанная строка или None.
    """
    match = re.match(r'^(\s*)(["\'])(.*)$', line)
    if not match:
        return None
    spaces, quote_char, rest = match.groups()
    last_quote_index = rest.rfind(quote_char)
    if last_quote_index == -1:
        return None
    body_before_last = rest[:last_quote_index]
    tail = rest[last_quote_index + 1:]
    return format_quoted_line(spaces, body_before_last, tail, punct_inside)


def clean_text(raw_text, punct_inside_quotes=True):
    """
    Приводит текст к типографски аккуратному виду для SMM‑постов.

    Аргументы:
        raw_text (str): Исходный текст с прямыми кавычками ("),
            дефисами и лишними пробелами.
        punct_inside_quotes (bool):
            Если True, знаки ., !, ? остаются внутри кавычек («...!»).
            Если False, выносятся наружу («...»!).

    Возвращает:
        str: Текст с «ёлочками», длинным тире (—),
        коротким тире для диапазонов (10–20) и нормализованными пробелами.
    """
    if not raw_text:
        return ""

    processed_lines = []

    for raw_line in raw_text.splitlines():
        without_space = replaced_spacing(raw_line)
        if not without_space:
            continue

        rep_dash = replaced_dashes(without_space)

        wrapped = try_wrap_quotes(rep_dash, punct_inside_quotes)
        if wrapped is not None:
            processed_lines.append(wrapped)
        else:
            processed_lines.append(
                frag_alt_quotes(rep_dash, punct_inside_quotes)
            )

    return '\n'.join(processed_lines).strip()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        raw = ' '.join(sys.argv[1:])
        print(clean_text(raw))
    else:
        raw = sys.stdin.read()
        if raw:
            print(clean_text(raw))
        else:
            print("Usage: python typography.py \"текст с кавычками\"")
            print("   or: echo \"текст\" | python typography.py")
