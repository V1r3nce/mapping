"""Парсер тэга в имени кейса.

Допустимые формы (одна на имя): O1..O6 / О1..О6 / 1A..6A / 1X..6X.
Опционально в скобках: (1A), (О2) и т.п.
"""
import re
from typing import Tuple

_TAG_RE = re.compile(
    r"(?<![\w])\(?([OО][1-6]|[1-6][AX])\)?(?![\w])"
)


def split_tag_and_requirement(name: str) -> Tuple[str, str]:
    """(tag, requirement) из имени. Если тэга нет — ('', name.strip())."""
    if not name:
        return "", ""
    match = _TAG_RE.search(name)
    if not match:
        return "", name.strip()
    tag = match.group(1)
    requirement = (name[: match.start()] + name[match.end():]).strip()
    requirement = re.sub(r"\s+", " ", requirement)
    return tag, requirement
