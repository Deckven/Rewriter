"""Prompt templates for style-transfer rewriting."""

REWRITE_SYSTEM = """\
Ты — опытный редактор игрового блога. Твоя задача — переписать предоставленный текст, \
адаптировав его под стиль блога, описанный в style guide ниже.

{style_guide}

---

## Правила перезаписи

### Интенсивность: {intensity}
{intensity_instructions}

### Общие правила
- Сохраняй фактическую точность исходного текста
- Не добавляй информацию, которой нет в оригинале
- Не удаляй важные факты из оригинала
- Результат должен звучать естественно, как если бы автор блога написал его сам
- Пиши на русском языке
"""

INTENSITY_INSTRUCTIONS = {
    "light": """\
**Лёгкая адаптация**: минимальные изменения.
- Скорректируй только тон и отдельные формулировки
- Сохрани структуру и порядок абзацев оригинала
- Замени явно «чужие» обороты на характерные для блога
- НЕ перестраивай предложения кардинально""",

    "medium": """\
**Средняя адаптация**: ощутимая стилизация.
- Перепиши предложения в характерном для блога стиле
- Адаптируй лексику, тон и ритм
- Можно менять порядок информации внутри абзацев
- Сохрани общую структуру (абзацы, секции)""",

    "full": """\
**Полная перезапись**: глубокая стилизация.
- Полностью переработай текст в стиле блога
- Свободно перестраивай структуру, если это улучшает текст
- Добавь характерные для блога элементы (интро, переходы, заключение)
- Используй типичные для блога приёмы форматирования""",
}


REWRITE_USER = """\
## Примеры стиля блога

Вот несколько реальных статей из блога для референса:

{examples_text}

---

## Текст для перезаписи

{input_text}

---

Перепиши текст выше в стиле блога. Верни ТОЛЬКО переписанный текст, без комментариев."""


REWRITE_USER_PRESERVE = """\
## Примеры стиля блога

Вот несколько реальных статей из блога для референса:

{examples_text}

---

## Текст для перезаписи

{input_text}

---

Перепиши текст выше в стиле блога. \
**Сохрани исходную структуру**: заголовки, списки, разделение на секции. \
Верни ТОЛЬКО переписанный текст, без комментариев."""


def build_system_prompt(
    style_guide: str,
    intensity: str = "medium",
) -> str:
    """Build the system prompt with style guide and intensity instructions."""
    return REWRITE_SYSTEM.format(
        style_guide=style_guide,
        intensity=intensity,
        intensity_instructions=INTENSITY_INSTRUCTIONS.get(intensity, INTENSITY_INSTRUCTIONS["medium"]),
    )


def build_user_prompt(
    input_text: str,
    examples: list[str],
    *,
    preserve_structure: bool = False,
) -> str:
    """Build the user prompt with examples and input text."""
    examples_text = "\n\n---\n\n".join(
        f"### Пример {i + 1}\n\n{ex}" for i, ex in enumerate(examples)
    )

    template = REWRITE_USER_PRESERVE if preserve_structure else REWRITE_USER
    return template.format(
        examples_text=examples_text,
        input_text=input_text,
    )
