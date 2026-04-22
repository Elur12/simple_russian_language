"""
Prompt stack for Yandex AI Studio-based plain-language analysis.

Design principles (from Sberbank's plain-language guide):
- Target audience: non-native Russian speakers, elderly, children, readers
  with limited literacy. Active vocabulary ≈ top-1000 Russian words.
- The goal is CLARITY, not literary beauty. Rewrites should preserve meaning
  exactly, not add, remove, or reinterpret information.
- Severity reflects the SIZE of the problem, not the rule type. The same
  rule can produce "green" (minor), "orange" (moderate), or "red" (critical)
  violations depending on how much understanding is harmed.
"""

from .rubric import get_rubric_for_prompt


def get_system_prompt() -> str:
    return """Ты — редактор, который проверяет русский текст по правилам Простого языка
(методика Сбербанка для пожилых, иностранцев, детей и людей с ограниченной грамотностью).

ТВОЯ ЦЕЛЬ: найти места, которые мешают пониманию, и предложить замену, сохраняющую смысл.

ГЛАВНЫЕ ПРИНЦИПЫ:
1. Активный словарь аудитории ≈ топ-1000 самых частых слов русского языка. Всё, что книжнее, — кандидат на замену.
2. Исправление НЕ меняет смысл. Нельзя добавлять свои пояснения или выдумывать факты.
3. Severity = СИЛА нарушения, а не тип правила:
   - red — читатель почти наверняка не поймёт или поймёт неправильно
   - orange — читатель споткнётся, но разберётся
   - green — стилистически лучше заменить, но и без замены понятно
4. Лучше пропустить сомнительное нарушение, чем придумать его. Если текст уже хороший — верни пустой список violations.
5. Отвечай ТОЛЬКО валидным JSON, без пояснений вне JSON.
"""


def get_policy_prompt() -> str:
    rubric = get_rubric_for_prompt()
    return f"""{rubric}

## Как назначать severity

severity зависит от того, насколько сильно страдает понимание, а не от номера правила:

- **red** — в исходнике есть что-то, что типичный читатель из ЦА почти наверняка
  НЕ поймёт или поймёт неправильно: сложное иностранное слово без объяснения,
  канцелярит-кирпич («произведите адаптацию»), метафора, нерасшифрованная
  аббревиатура из профессионального жаргона, предложение длиной 30+ слов
  с несколькими придаточными.

- **orange** — читатель споткнётся, но с усилием разберётся: умеренно книжное
  слово, общеупотребительное сокращение («ул.», «г.»), длинное предложение
  на 2 придаточных, сложные числа/даты в формате «05.12.2022».

- **green** — норма понятна, но можно лучше: лёгкая замена синонима, короткое
  сокращение («и т.д.»), одна второстепенная многозначность.

## Как писать suggested_rewrite

- suggested_rewrite должен заменять problematic_text и БЫТЬ ДРУГИМ текстом.
  Если ты не можешь придумать замену лучше — НЕ создавай violation вообще.
- Не добавляй в замену новую информацию, которой нет в оригинале.
- Не удаляй значимую информацию: числа, названия, имена, условия.
- Замена должна грамматически вставать на место problematic_text в абзаце.
- Длина замены — сопоставима с problematic_text (±100%). Не переписывай
  полабзаца в одном violation — лучше разбей на несколько точечных.

## Как писать paragraph_rewrite

- Это полный текст абзаца с применёнными всеми исправлениями.
- Если в абзаце нет нарушений — paragraph_rewrite = source_text (буква в букву).
- Смысл абзаца должен остаться прежним. Факты, числа, имена — сохраняются.

## Чего НЕ делать

- НЕ придумывай нарушения «ради галочки». Пустой violations — нормально.
- НЕ применяй правила R10/R11 (про новые строки) к обычному связному тексту.
  Эти правила — только для пошаговых инструкций и чек-листов.
- НЕ комментируй стиль, грамотность, запятые, опечатки — только нарушения Простого языка.
- НЕ добавляй в замену пояснения «в скобках» — это отдельный вопрос, не для этого правила.
"""


FEW_SHOT_EXAMPLES = """## Примеры правильного разбора

### Пример 1 — текст с тяжёлым канцеляритом
source_text:
"Уведомляем вас о том, что 05.12.2022 в период с 09:00 до 18:00 будет произведено отключение ГВС и ЦО в связи с реконструкцией ЦТП."

Правильный разбор:
- R1 «Уведомляем вас о том, что» → «Сообщаем, что» (severity: orange — канцелярит, но читатель поймёт)
- R5 «05.12.2022 в период с 09:00 до 18:00» → «в четверг с 9 утра до 6 вечера» (severity: orange)
- R1 «будет произведено отключение» → «отключат» (severity: red — отглагольное существительное в пассиве, очень тяжело)
- R3 «ГВС и ЦО» → «горячую воду и отопление» (severity: red — специальные сокращения)
- R3 «ЦТП» → «теплового пункта» (severity: red — неизвестная аббревиатура)
- R1 «в связи с реконструкцией» → «из-за ремонта» (severity: orange — книжное слово)

### Пример 2 — текст уже в порядке
source_text:
"Позвоните нам в рабочее время. Мы поможем разобраться."

Правильный разбор:
- violations: [] (нарушений нет; текст короткий, слова простые)
- severity: green
- paragraph_rewrite: "Позвоните нам в рабочее время. Мы поможем разобраться."

### Пример 3 — одно несильное нарушение
source_text:
"Иван пошёл в магазин. Он купил хлеб. Молодой человек вернулся домой."

Правильный разбор:
- R4 «Он» → «Иван» (severity: green — понятно, но лучше повторить имя)
- R4 «Молодой человек» → «Иван» (severity: orange — синоним, который может сбить с толку)
"""


def get_json_schema_instructions() -> str:
    return """{
  "items": [
    {
      "unit_index": 0,
      "unit_type": "paragraph",
      "source_text": "Уведомляем вас о проведении ремонтных работ.",
      "severity": "red",
      "violations": [
        {
          "rule_id": "R1",
          "rule_name": "Выбирайте часто употребляемые слова",
          "severity": "orange",
          "problematic_text": "Уведомляем вас о",
          "comment": "Канцелярит: «уведомляем вас о» — тяжёлая официальная формулировка.",
          "suggested_rewrite": "Сообщаем, что будет"
        },
        {
          "rule_id": "R1",
          "rule_name": "Выбирайте часто употребляемые слова",
          "severity": "red",
          "problematic_text": "проведении ремонтных работ",
          "comment": "Отглагольное существительное «проведение» — замените на глагол.",
          "suggested_rewrite": "ремонт"
        }
      ],
      "overall_comment": "Два случая канцелярита затрудняют чтение.",
      "paragraph_rewrite": "Сообщаем, что будет ремонт."
    },
    {
      "unit_index": 1,
      "unit_type": "paragraph",
      "source_text": "Позвоните нам в рабочее время.",
      "severity": "green",
      "violations": [],
      "overall_comment": "Нарушений не обнаружено.",
      "paragraph_rewrite": "Позвоните нам в рабочее время."
    }
  ],
  "summary": {
    "green_count": 1,
    "orange_count": 0,
    "red_count": 1,
    "total_violations": 2,
    "overall_severity": "red"
  }
}"""


def _looks_like_instruction(text: str) -> bool:
    """Heuristic: does the text look like a step-by-step instruction/checklist?"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    # Count lines that start with digit+dot/bracket, bullet, or imperative marker
    markers = 0
    for ln in lines:
        if (ln[:2] in ("- ", "• ", "* ", "— ") or
            (ln[0].isdigit() and len(ln) > 1 and ln[1] in ".)") or
            ln.lower().startswith(("шаг ", "этап "))):
            markers += 1
    return markers >= max(2, len(lines) // 2)


def _format_mode_hint(text: str) -> str:
    if _looks_like_instruction(text):
        return ("Этот текст выглядит как инструкция/чек-лист — правила R10/R11 "
                "про новые строки ПРИМЕНИМЫ.")
    return ("Этот текст — связный текст (не инструкция). Правила R10/R11 "
            "про новые строки НЕ применяй.")


def build_full_prompt(text: str, mode: str = "paragraph") -> tuple[str, str]:
    system = get_system_prompt()
    policy = get_policy_prompt()
    schema = get_json_schema_instructions()
    format_hint = _format_mode_hint(text)

    user_prompt = f"""{policy}

{FEW_SHOT_EXAMPLES}

## Подсказка по формату текста
{format_hint}

## Текст для анализа
```
{text}
```

Проанализируй каждый абзац (отделены пустой строкой). Для каждого верни
объект в массиве items с полями unit_index, unit_type, source_text,
severity, violations, overall_comment, paragraph_rewrite.

## Схема ответа
{schema}

Верни ТОЛЬКО JSON."""

    return system, user_prompt


def build_window_prompt(
    current_paragraph: str,
    current_index: int,
    total_paragraphs: int,
    prev_paragraph: str = "",
    next_paragraph: str = "",
) -> tuple[str, str]:
    system = get_system_prompt()
    policy = get_policy_prompt()
    schema = get_json_schema_instructions()
    format_hint = _format_mode_hint(current_paragraph)

    prev_block = prev_paragraph or "(начало текста)"
    next_block = next_paragraph or "(конец текста)"

    user_prompt = f"""{policy}

{FEW_SHOT_EXAMPLES}

## Подсказка по формату текста
{format_hint}

## Задача: анализ одного абзаца с контекстом

Соседние абзацы даны только для понимания контекста.
Анализируй ТОЛЬКО целевой абзац.

Позиция: {current_index + 1} из {total_paragraphs}.

Предыдущий абзац (НЕ анализировать):
```
{prev_block}
```

ЦЕЛЕВОЙ АБЗАЦ (анализируй ТОЛЬКО его):
```
{current_paragraph}
```

Следующий абзац (НЕ анализировать):
```
{next_block}
```

Верни JSON ровно с одним элементом в "items":
- unit_index = {current_index}
- unit_type = "paragraph"
- source_text — скопируй целевой абзац дословно
- severity — по силе самого серьёзного нарушения; если нарушений нет — "green"
- violations — может быть пустым

## Схема ответа
{schema}

Верни ТОЛЬКО JSON."""

    return system, user_prompt
