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


def replaced_dashes(without_space):
    """Заменяет дефисы на типографские тире.

    Обработанные случаи:
        - Диапазоны: 10-20 → 10–20
        - Инициалы: А. - Б. → А. Б.
        - Обычное тире: слово - слово → слово — слово

    Args:
        without_space (str): Строка с дефисами.

    Returns:
        str: Строка с правильными тире.
    """
    repair_ranges = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1–\2', without_space)
    initials_fixed = re.sub(
        r'(\b[А-Яа-я]\.)\s+[-–—]\s+([А-Яа-я]\.\b)', r'\1 \2', repair_ranges
    )
    repair_dash = re.sub(r'\s+[-–—]\s+', ' — ', initials_fixed)
    return repair_dash


def stackering_quotes(plain_text, punctuation_inside=True):
    """Заменяет прямые кавычки " и ' на « и » с учётом вложенности.

    Использует стек для отслеживания уровней цитирования.
    Определяет тип кавычки по прилипанию к буквам:
        - открывающая: перед кавычкой НЕ буква/цифра, после – буква/цифра
        - закрывающая: перед буква/цифра, после НЕ буква/цифра
    В неоднозначных случаях решает стек.

    Args:
        plain_text(str): текст после нормализации пробелов и замены тире,
            содержащий прямые кавычки.

    Returns:
        str: Текст с «ёлочками».
    """
    formatted_chars = []
    quote_stack = []
    length = len(plain_text)

    for index, char in enumerate(plain_text):
        if char not in ('"', "'"):
            formatted_chars.append(char)
            continue

        left_char = plain_text[index - 1] if index > 0 else ''
        right_char = plain_text[index + 1] if index + 1 < length else ''
        end_sent = left_char in ('.', '!', '?')
        is_left_alnum_or_punct = left_char.isalnum() or end_sent
        is_right_alnum = right_char.isalnum()

        # Открывающая кавычка: перед не буква/цифра, после — буква/цифра
        if not is_left_alnum_or_punct and is_right_alnum:
            formatted_chars.append('«')
            quote_stack.append(True)

        # Закрывающая кавычка: перед буква/цифра, после — не буква/цифра
        elif is_left_alnum_or_punct and not is_right_alnum:
            if quote_stack and punctuation_inside and end_sent:
                # Меняем местами знак препинания и кавычку
                punctuation_mark = formatted_chars.pop()
                formatted_chars.append(f'{punctuation_mark}»')
            else:
                formatted_chars.append('»')
            if quote_stack:
                quote_stack.pop()

        # Неоднозначные случаи (решает стек)
        else:
            if not quote_stack and (right_char == '' or right_char.isspace()):
                formatted_chars.append('»')
            elif quote_stack:
                formatted_chars.append('»')
                quote_stack.pop()
            else:
                formatted_chars.append('«')
                quote_stack.append(True)

    return ''.join(formatted_chars)


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
    inner = stackering_quotes(body, punct_inside)
    end_punct = re.search(r'([.!?]+)$', inner)
    if end_punct and punct_inside:
        punct = end_punct.group(1)
        clean_inner = inner[:-len(punct)]
        return f"{spaces}«{clean_inner}{punct}»{tail}"
    else:
        return f"{spaces}«{inner}»{tail}"


def typography_quotation(repair_dash, punct_inside):
    """Обрабатывает строку с прямыми внешними кавычками.

    Если строка начинается с кавычки и имеет парную закрывающую,
        возвращает обработанную строку как внешнюю цитату, иначе None.

    Args:
        repair_dash (str): Строка текста после замены тире.
        punct_inside (bool): Флаг для передачи в format_quoted_line.

    Returns:
        str or None: Обработанная строка или None.
    """
    match = re.match(r'^(\s*)(["\'])(.*)$', repair_dash)
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

        guillemets = typography_quotation(rep_dash, punct_inside_quotes)
        if guillemets is not None:
            processed_lines.append(guillemets)
        else:
            processed_lines.append(
                stackering_quotes(rep_dash, punct_inside_quotes)
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
