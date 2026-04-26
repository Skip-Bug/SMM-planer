r"""Модуль преобразователь текста.

Убирае лишние пробелы, меняет (-) на (—)
В место " грамотно ставит «...»
Примеры использования в консоли
    python typography.py "Тут \"кто-то\" и - то \"еще кавычки\" - мир!"
    или
    echo '"Тут "кто-то" и - то "еще кавычки" - мир!"' | python typography.py
"""

import re


def replaced_spacing(raw_text: str) -> str:
    """Убирает лишние пробелы."""
    return ' '.join(raw_text.split())


def replaced_dashes(line: str) -> str:
    """Заменяет дефисы на типографские тире."""
    line = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1–\2', line)
    line = re.sub(r'\s+[-–—]\s+', ' — ', line)
    return line


def frag_alt_quotes(fragment: str) -> str:
    """Заменяет прямые кавычки " и ' на « и » с чередованием."""
    chars = list(fragment)
    is_opening = True
    for i, ch in enumerate(chars):
        if ch in ('"', "'"):
            chars[i] = '«' if is_opening else '»'
            is_opening = not is_opening
    return ''.join(chars)


def format_quoted_line(
    spaces: str,
    body: str,
    tail: str,
    punct_inside: bool
) -> str:
    """Оборачивает тело цитаты в «» с учётом пунктуации и добавляет хвост."""
    inner = frag_alt_quotes(body)
    end_punct = re.search(r'([.!?]+)$', inner)
    if end_punct and punct_inside:
        punct = end_punct.group(1)
        clean_inner = inner[:-len(punct)]
        return f"{spaces}«{clean_inner}{punct}»{tail}"
    else:
        return f"{spaces}«{inner}»{tail}"


def try_wrap_quotes(line: str, punct_inside: bool):
    """Ищит кавычки в начале и в конце строк.

    Если строка начинается с кавычки и имеет парную закрывающую,
    возвращает строку, обработанную как внешняя цитата.
    Иначе возвращает None.
    """
    match = re.match(r'^(\s*)(["\'])(.*)$', line)
    if not match:
        return None
    spaces, quote_char, rest = match.groups()
    body_before_last, closing, tail = rest.rpartition(quote_char)
    if not closing:
        return None
    return format_quoted_line(spaces, body_before_last, tail, punct_inside)


def clean_text(raw_text: str, punct_inside_quotes: bool = True) -> str:
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
            processed_lines.append(frag_alt_quotes(rep_dash))

    return '\n'.join(processed_lines).strip()


if __name__ == "__main__":
    import sys
    # Если передан аргумент командной строки, берём его как текст
    if len(sys.argv) > 1:
        raw = ' '.join(sys.argv[1:])
        print(clean_text(raw))
    else:
        # Иначе читаем из stdin (полезно для пайпа)
        raw = sys.stdin.read()
        if raw:
            print(clean_text(raw))
        else:
            print("Usage: python typography.py \"текст с кавычками\"")
            print("   or: echo \"текст\" | python typography.py")
