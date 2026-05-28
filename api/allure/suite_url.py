"""Парсер URL сьюта Allure TestOps в (project_id, tree_id, path)."""
import base64
import json
import re
from dataclasses import dataclass
from typing import Tuple
from urllib.parse import urlparse, parse_qs


@dataclass(frozen=True)
class SuiteRef:
    project_id: int
    tree_id: int
    path: Tuple[int, ...]


_PROJECT_RE = re.compile(r"/project/(\d+)(?:/|$)")


def parse_suite_url(url: str) -> SuiteRef:
    """URL сьюта вида https://.../project/313/test-cases/...?treeId=811&from=Wzxxx → SuiteRef.

    from опционален — без него path=() и обходим корень treeId рекурсивно.
    """
    parsed = urlparse(url)
    project_match = _PROJECT_RE.search(parsed.path)
    if not project_match:
        raise ValueError(
            f"В URL не найден /project/<id>: {url}. "
            f"Ожидается ссылка из адресной строки UI Allure TestOps."
        )
    project_id = int(project_match.group(1))

    qs = parse_qs(parsed.query)
    tree_id_raw = qs.get("treeId", [None])[0]
    from_raw = qs.get("from", [None])[0]
    if tree_id_raw is None:
        raise ValueError(
            f"В URL нет treeId: {url}. "
            f"Открой сьют через дерево слева в Allure TestOps и скопируй URL — "
            f"тогда в адресной строке появится treeId."
        )

    if from_raw is None:
        path: Tuple[int, ...] = ()
    else:
        try:
            decoded = base64.b64decode(from_raw, validate=True).decode("utf-8")
            path_list = json.loads(decoded)
        except Exception as exc:
            raise ValueError(f"Не получилось декодировать from='{from_raw}': {exc}") from exc

        if not isinstance(path_list, list):
            raise ValueError(f"from декодирован не в список: {path_list}")
        path = tuple(int(p) for p in path_list)

    return SuiteRef(project_id=project_id, tree_id=int(tree_id_raw), path=path)
