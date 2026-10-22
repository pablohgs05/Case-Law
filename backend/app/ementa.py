"""
The four sections a structured ementa is written in.

Since 2024 the national court council asks for a fixed shape — the case, the
question, the reasoning, the ruling — and 73,7% of the collection follows it.
The rest is free prose, so nothing here may assume the shape is there.
"""

import re
from dataclasses import dataclass

# What the courts actually write, measured over 107.828 ementas:
# singular and plural, "DISPOSITIVO" alone and "DISPOSITIVO E TESE", any case,
# and sometimes glued to the sentence before it with no line break at all.
NAMES = (
    r"CASO\s+EM\s+EXAME",
    r"QUEST(?:[ÃA]O|[ÕO]ES)\s+EM\s+DISCUSS[ÃA]O",
    r"RAZ[ÕO]ES\s+DE\s+DECIDIR",
    r"DISPOSITIVO(?:\s+E\s+TESE)?",
)

# The roman numeral is required. Without it "Dispositivos relevantes citados",
# which appears inside the fourth section, would open a fifth one.
# Not followed by a letter, rather than a word boundary: a boundary would also
# refuse "CASO EM EXAME1.", which is how a glued ementa writes it, while the
# point was only to refuse "DISPOSITIVOS relevantes citados".
MARKERS = tuple(
    re.compile(
        rf"\b(?P<numeral>I{{1,3}}V?|IV)\s*[.–-]?\s*(?:{name})(?![^\W\d_])[.:–-]?",
        re.IGNORECASE,
    )
    for name in NAMES
)


@dataclass(frozen=True)
class Section:
    """One section, and the label that opened it."""

    label: str
    text: str


@dataclass(frozen=True)
class StructuredEmenta:
    """
    An ementa split into its parts.

    `headnote` is the keyword block every ementa opens with, before the first
    section. It is not one of the four, and dropping it would lose text the
    court wrote.
    """

    headnote: str
    case: Section
    question: Section
    reasoning: Section
    ruling: Section

    def rebuild(self) -> str:
        """The original text, exactly. What the split must never change."""
        parts = [self.headnote]
        for section in (self.case, self.question, self.reasoning, self.ruling):
            parts.append(section.label)
            parts.append(section.text)
        return "".join(parts)


def split(ementa: str | None) -> StructuredEmenta | None:
    """
    The four sections, or `None` when the ementa is not written in them.

    A partial shape counts as no shape: three sections out of four would leave
    the reader guessing which one is missing, and the whole text says more.
    """
    text = ementa or ""
    if not text:
        return None

    found: list[re.Match[str]] = []
    position = 0
    for marker in MARKERS:
        match = marker.search(text, position)
        if match is None:
            return None
        found.append(match)
        position = match.end()

    sections = [
        Section(
            label=text[match.start() : match.end()],
            text=text[match.end() : next_start],
        )
        for match, next_start in zip(
            found,
            [m.start() for m in found[1:]] + [len(text)],
            strict=True,
        )
    ]

    return StructuredEmenta(
        headnote=text[: found[0].start()],
        case=sections[0],
        question=sections[1],
        reasoning=sections[2],
        ruling=sections[3],
    )
