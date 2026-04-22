"""
Static plain-language rubric derived from Sberbank's guide:
https://www.sberbank.com/promo/plain_language_guide/creation

Two language levels exist:
- "Ясный" (clear) — for people with cognitive disabilities, active vocabulary
  as small as 50–500 words.
- "Простой" (plain) — for non-native speakers, elderly, children with broader
  but still limited vocabulary; avoids jargon, bureaucratese, long sentences.

Our default target is "простой язык". Rules are grouped into:
- CONTENT rules (R1–R5): word choice, clarity, concreteness — apply to ANY text.
- FORMAT rules (R10–R11): line/paragraph layout — apply ONLY to procedural
  texts (step-by-step instructions, checklists). They must NOT be raised
  for normal narrative prose.
- OUT-OF-SCOPE rules (R6–R9, R12): typography (fonts, sizes, CAPS LOCK,
  paragraph spacing) — cannot be judged from plain text alone and are
  excluded from the AI's task.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class Rule:
    id: str
    name: str
    category: str  # "content" | "format" | "out_of_scope"
    description: str
    examples_bad: List[str]
    examples_good: List[str]
    severity_weight: int
    in_scope: bool = True


PLAIN_LANGUAGE_RULES = [
    # ================== CONTENT RULES (R1–R5) ==================
    Rule(
        id="R1",
        name="Выбирайте часто употребляемые слова",
        category="content",
        description=(
            "Пишите словами из активного словарного запаса аудитории "
            "(примерно топ-1000 частотных слов русского языка). "
            "Заменяйте книжные, канцелярские, профессиональные, иноязычные "
            "слова на повседневные синонимы. "
            "Канцелярит («произведите», «осуществить», «уведомляем», "
            "«в целях», «в рамках») и отглагольные существительные "
            "(«проведение», «адаптация», «реконструкция», «отключение») — "
            "типичные случаи нарушения."
        ),
        examples_bad=[
            "Произведите адаптацию документации.",
            "Нужна интеграция с внешними системами.",
            "Уведомляем о проведении ремонтных работ.",
            "В целях оптимизации процесса рекомендуется актуализировать данные.",
            "Расхождение между моделью и реальностью.",
        ],
        examples_good=[
            "Измените документ.",
            "Нужно подключение к другим программам.",
            "Сообщаем, что будет ремонт.",
            "Чтобы работать быстрее, обновите данные.",
            "Разница между тем, что мы думали, и тем, что получилось.",
        ],
        severity_weight=3,
    ),
    Rule(
        id="R2",
        name="Используйте слова в прямом значении",
        category="content",
        description=(
            "Не используйте метафоры, гиперболы, идиомы, образные выражения. "
            "Если слово многозначно — уточните, что имеется в виду. "
            "Образные выражения читатель может понять буквально и "
            "запутаться."
        ),
        examples_bad=[
            "У него золотые руки.",
            "Кот наплакал денег.",
            "Съел две тарелки супа.",
            "Сто раз говорил.",
            "Царь зверей живёт в саванне.",
        ],
        examples_good=[
            "Он хороший мастер.",
            "Денег очень мало.",
            "Съел две тарелки супа.",  # можно оставить, если из контекста понятно
            "Много раз говорил.",
            "Лев живёт в саванне.",
        ],
        severity_weight=3,
    ),
    Rule(
        id="R3",
        name="Раскрывайте сокращения и аббревиатуры",
        category="content",
        description=(
            "Пишите слова полностью: «улица», «год», «таблетка» вместо "
            "«ул.», «г.», «т.». Если аббревиатуру нельзя обойти "
            "(ЗАГС, СНИЛС), при первом упоминании давайте расшифровку."
        ),
        examples_bad=[
            "ул. Ленина, д. 25",
            "Принимайте 2 р/д по 1 т.",
            "Отключение ГВС и ЦО в связи с реконструкцией ЦТП.",
            "Подайте заявку в МФЦ.",
        ],
        examples_good=[
            "улица Ленина, дом 25",
            "Пейте два раза в день по одной таблетке.",
            "Отключат горячую воду и отопление из-за ремонта.",
            "Подайте заявку в МФЦ — это центр, где оформляют документы.",
        ],
        severity_weight=2,
    ),
    Rule(
        id="R4",
        name="Повторяйте ключевые слова, не заменяйте синонимами",
        category="content",
        description=(
            "В ясном/простом языке лучше повторить одно и то же ключевое "
            "слово, чем менять его на синоним или местоимение. Синонимы "
            "и местоимения («он», «она», «данный», «указанный», «юноша», "
            "«программа» вместо «система») могут запутать читателя: "
            "он решит, что речь о другом объекте."
        ),
        examples_bad=[
            "Иван пошёл в магазин. Он купил хлеб. Юноша вернулся домой.",
            "Мы разработали систему. Эта программа помогает считать расходы. "
            "Приложение работает на всех устройствах.",
        ],
        examples_good=[
            "Иван пошёл в магазин. Иван купил хлеб. Иван вернулся домой.",
            "Мы разработали систему. Система помогает считать расходы. "
            "Система работает на всех устройствах.",
        ],
        severity_weight=2,
    ),
    Rule(
        id="R5",
        name="Упрощайте числа, даты и время",
        category="content",
        description=(
            "Большие точные числа округляйте или заменяйте словами "
            "«много», «мало», «больше миллиона». "
            "Даты пишите словами («в четверг», «в июле»), а не цифрами "
            "формата «05.12.2022». Время — «в 12 часов 45 минут», не «12:45». "
            "Единицы измерения — полностью («килограмм», не «кг»). "
            "Только арабские цифры, не римские."
        ),
        examples_bad=[
            "В коллекции зоопарка 1267 видов животных, 10 531 особь.",
            "Отключение будет 05.12.2022 в 09:00–18:00.",
            "Зарплата CCCLXV рублей.",
            "Купи 3 кг картошки к 12:45.",
        ],
        examples_good=[
            "В зоопарке много разных животных.",
            "В четверг весь день не будет отопления и горячей воды.",
            "Зарплата 365 рублей.",
            "Купи 3 килограмма картошки к часу дня.",
        ],
        severity_weight=2,
    ),

    # ================== FORMAT RULES (R10–R11) ==================
    Rule(
        id="R10",
        name="Каждое предложение — с новой строки (для инструкций)",
        category="format",
        description=(
            "Применяется ТОЛЬКО к пошаговым инструкциям, рецептам, "
            "чек-листам, спискам действий. В обычном связном тексте "
            "(статья, пост, описание) НЕ нужно разбивать каждое "
            "предложение на новую строку — это правило НЕ про такой текст."
        ),
        examples_bad=[
            "Помойте мясо и овощи. Очистите чеснок. Нарежьте овощи.",
        ],
        examples_good=[
            "Помойте мясо и овощи.\nОчистите чеснок.\nНарежьте овощи.",
        ],
        severity_weight=1,
    ),
    Rule(
        id="R11",
        name="Делите длинные предложения на части",
        category="content",  # длина предложения — это не только формат, это читаемость
        description=(
            "Если в предложении больше одного глагольного ядра, несколько "
            "придаточных или длинный перечень — разбейте на 2–3 коротких "
            "предложения. Ориентир: если при чтении вслух приходится делать "
            "паузу, чтобы набрать воздуха, — там нужен новый конец/начало. "
            "Для связного текста — именно РАЗБИТЬ на отдельные предложения "
            "(точкой), а не на строки."
        ),
        examples_bad=[
            "Положите в кастрюлю 1 лавровый лист, 5 горошин чёрного перца "
            "и 1 столовую ложку соли, затем залейте водой и поставьте "
            "на плиту, чтобы вода закипела.",
            "Если вы хотите получить справку, нужно прийти в МФЦ с паспортом "
            "и СНИЛС в рабочее время, где дежурный специалист поможет вам "
            "заполнить заявление и проведёт через процедуру.",
        ],
        examples_good=[
            "Положите в кастрюлю 1 лавровый лист, 5 горошин перца и ложку "
            "соли. Залейте водой. Поставьте на плиту. Дождитесь закипания.",
            "Чтобы получить справку, приходите в МФЦ с паспортом и СНИЛС. "
            "В МФЦ вам помогут заполнить заявление.",
        ],
        severity_weight=2,
    ),

    # ================== OUT-OF-SCOPE RULES (R6–R9, R12) ==================
    # Kept for reference only — not used in AI analysis of plain text.
    Rule(
        id="R6",
        name="Шрифт без засечек",
        category="out_of_scope",
        description="Правило о типографике. Невозможно оценить по plain text.",
        examples_bad=[], examples_good=[], severity_weight=1, in_scope=False,
    ),
    Rule(
        id="R7",
        name="Размер шрифта 14pt и выше",
        category="out_of_scope",
        description="Правило о вёрстке. Невозможно оценить по plain text.",
        examples_bad=[], examples_good=[], severity_weight=1, in_scope=False,
    ),
    Rule(
        id="R8",
        name="Без курсива и подчёркивания",
        category="out_of_scope",
        description=(
            "Применимо только если в тексте явно есть HTML/markdown теги "
            "выделения. В обычном plain text не применяется."
        ),
        examples_bad=[], examples_good=[], severity_weight=1, in_scope=False,
    ),
    Rule(
        id="R9",
        name="Без ПРОПИСНЫХ БУКВ (CapsLock)",
        category="content",  # это мы можем проверить
        description=(
            "Не пишите подряд несколько слов капсом — это воспринимается "
            "как крик и читается хуже. Выделяйте только полужирным."
        ),
        examples_bad=[
            "ОЧЕНЬ ВАЖНАЯ ИНФОРМАЦИЯ",
            "ПРОЧИТАЙТЕ ВНИМАТЕЛЬНО ПЕРЕД ИСПОЛЬЗОВАНИЕМ",
        ],
        examples_good=[
            "Очень важная информация",
            "Прочитайте внимательно перед использованием",
        ],
        severity_weight=2,
    ),
    Rule(
        id="R12",
        name="Разделение абзацев",
        category="out_of_scope",
        description="Правило о межабзацных интервалах. Невозможно оценить по plain text.",
        examples_bad=[], examples_good=[], severity_weight=1, in_scope=False,
    ),
]


def get_rule_by_id(rule_id: str) -> Rule:
    for rule in PLAIN_LANGUAGE_RULES:
        if rule.id == rule_id:
            return rule
    raise ValueError(f"Rule {rule_id} not found in rubric")


def get_all_rules() -> List[Rule]:
    return PLAIN_LANGUAGE_RULES


def get_active_rules() -> List[Rule]:
    """Rules the AI should actually check (excludes typography rules)."""
    return [r for r in PLAIN_LANGUAGE_RULES if r.in_scope]


def _format_rule(rule: Rule) -> str:
    bad = "\n".join(f"    ✗ {ex}" for ex in rule.examples_bad[:3])
    good = "\n".join(f"    ✓ {ex}" for ex in rule.examples_good[:3])
    parts = [f"### {rule.id}. {rule.name}", rule.description]
    if bad and good:
        parts.append("Примеры:")
        parts.append(bad)
        parts.append(good)
    return "\n".join(parts)


def get_rubric_for_prompt() -> str:
    """Get formatted rubric for inclusion in AI prompt."""
    content_rules = [r for r in PLAIN_LANGUAGE_RULES if r.category == "content" and r.in_scope]
    format_rules = [r for r in PLAIN_LANGUAGE_RULES if r.category == "format" and r.in_scope]

    out = ["## Правила простого языка\n"]
    out.append("### Правила про содержание (применяй к любому тексту):\n")
    for rule in content_rules:
        out.append(_format_rule(rule))
        out.append("")
    out.append("### Правила про формат (применяй ТОЛЬКО к инструкциям/чек-листам/пошаговым рецептам; НЕ применяй к обычному связному тексту — статьям, постам, описаниям):\n")
    for rule in format_rules:
        out.append(_format_rule(rule))
        out.append("")
    return "\n".join(out)
