# Маппинг требований и тестов в Confluence — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Скрипт, который берёт один или несколько URL'ов сьютов в Allure TestOps, в каждом сьюте парсит кейсы (вытягивает из имени тэг типа `O1`/`3A`/`5X`, остаток имени = название требования, фичу — из линков кейса), и обновляет тело страницы Confluence по `--parent_id` таблицей маппинга требований→кейсов.

**Architecture:** Полностью повторяет структуру и стиль `launch_analyzer-master/`: пакеты `api/allure/`, `api/confluence/`, `common/helpers/`, `scripts/confluence/`, файл-агрегатор `config.py`, единый `.env` в корне, запуск через `PYTHONPATH=корень`. Один argparse-скрипт; класс `AllureSuite` (аналог `AllureLaunch`) тянет данные из Allure; класс `MappingConfluencePage` (аналог `ConfluencePage`) обновляет тело страницы. Сетевой слой — `requests.Session` с Bearer-токеном (как в launch.py). Без тестов на сетевые классы — только на чистые функции (парсер тэга, парсер URL сьюта), в стилистике существующего проекта (там тестов нет вовсе, поэтому минимально).

**Tech Stack:** Python 3.10+, `requests`, `beautifulsoup4`, `atlassian-python-api`, `python-dotenv`.

**Project root:** `C:\Users\Andrey\PycharmProjects\mapping\` (структура кладётся прямо в корень, рядом с уже существующим `launch_analyzer-master/` — это сосед, а не родитель).

---

## Известные эндпоинты

- **Список кейсов в сьюте:** `GET /api/rs/testcasetree/leaf?projectId={pid}&path={path}&treeId={tid}&sort=name,asc&size=100&page={n}` → `{content: [{id, name, automated, statusName, statusColor, createdDate}], totalPages, last, ...}`.
- **Детали кейса:** `GET /api/rs/testcase/{id}/overview` → JSON с полями `name`, `tags[]`, `links[]`, `issues[]`, `status`, `members[]`, `customFields[]`. Образец JSON приложил пользователь (кейс `920311`). **Используем оттуда только `name`, `links[]`, `status.name`, `members[]` — поле `tags[]` игнорируем (тэг парсим из `name` регуляркой).**

## Поведение при «чужом» HTML страницы

Если по `--parent_id` страница не находится / отдаёт пустое body — кидаем `ConfluencePageNotFoundException` с понятным сообщением. **Никакой валидации старого HTML не делаем** — мы тело **полностью заменяем** нашим сгенерированным. (Юзер: «Если HTML другой — выдай ошибку просто» — но без структурного парсинга существующей таблицы делать тут нечего; единственная реалистичная ошибка — страница недоступна.)

---

## Task 1: Создать каркас проекта в `mapping/`

**Files:**
- Create: `C:\Users\Andrey\PycharmProjects\mapping\.gitignore`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\requirements.txt`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\.env.example`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\config.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\api\__init__.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\api\exceptions.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\api\allure\__init__.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\api\confluence\__init__.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\common\__init__.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\common\helpers\__init__.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\scripts\__init__.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\scripts\confluence\__init__.py`

**Step 1: Скопировать `.gitignore` из `launch_analyzer-master/.gitignore` дословно**

```gitignore
# Секреты и окружение
.env

# Виртуальное окружение
.venv/
venv/
env/

# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.mypy_cache/
.pytest_cache/
*.egg-info/
.eggs/
dist/
build/

# IDE
.idea/
.vscode/
*.swp
*.swo
```

**Step 2: `requirements.txt` — те же зависимости, без `python-gitlab` (не используется)**

```
beautifulsoup4>=4.12.0
atlassian-python-api>=3.41.2
requests>=2.32.0
python-dotenv>=1.0.0
```

**Step 3: `.env.example`**

```
ALLURE_URL=https://allure.nexign.com
ALLURE_TOKEN=<твой API-токен Allure>
CONFLUENCE_URL=https://confluence.nexign.com
CONFLUENCE_USERNAME=<доменный логин>
CONFLUENCE_PASSWORD=<пароль>
```

Заметка: `CONFLUENCE_PAGE_ID` сюда **не** кладём — в этом скрипте парент подаётся через `--parent_id`. `ALLURE_PROJECT_ID` тоже не кладём — он парсится из URL сьюта.

**Step 4: `config.py` — реэкспорт хелперов в той же стилистике, что у соседа**

```python
"""Реэкспорт get_var_from_env и timestamp_to_datetime_string из common.helpers."""
from common.helpers.env_helper import get_var_from_env, get_var_from_env_optional
from common.helpers.time_helpers import timestamp_to_datetime_string

__all__ = ["get_var_from_env", "get_var_from_env_optional", "timestamp_to_datetime_string"]
```

**Step 5: `api/__init__.py` — копия из соседа**

```python
"""
Корневой пакет API.

Содержит небольшие изолированные клиенты, которые эмулируют внешние
системы, используемые скриптами отчётности (Allure, Confluence).
"""
```

**Step 6: `api/exceptions.py`**

```python
"""Исключения при работе с Allure и Confluence."""


class AllureSuiteNotFoundException(Exception):
    """Сьют в Allure по этому URL не найден или пуст."""
    pass


class AllureTestCaseNotFoundException(Exception):
    """Тест-кейс в Allure не найден."""
    pass


class ConfluencePageNotFoundException(Exception):
    """Страница Confluence по этому ID не найдена."""
    pass
```

**Step 7: Все `__init__.py` остальных пакетов — пустые файлы**

`api/allure/__init__.py`, `api/confluence/__init__.py`, `common/__init__.py`, `common/helpers/__init__.py`, `scripts/__init__.py`, `scripts/confluence/__init__.py` — каждый создать как пустой файл (одна пустая строка).

**Step 8: Проверить структуру**

Run (PowerShell):
```powershell
Get-ChildItem -Recurse -Path "C:\Users\Andrey\PycharmProjects\mapping" -Exclude launch_analyzer-master,docs | Select-Object FullName
```
Expected: видно все созданные файлы, ни одного лишнего.

**Step 9: Коммита нет (репо не git).** Просто переходи к следующей задаче.

---

## Task 2: Перенести `env_helper.py` и `time_helpers.py` дословно

**Files:**
- Create: `C:\Users\Andrey\PycharmProjects\mapping\common\helpers\env_helper.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\common\helpers\time_helpers.py`

**Step 1: `env_helper.py` — копия из launch_analyzer-master**

```python
"""Переменные окружения из .env и os.environ."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_var_from_env(name: str) -> str:
    """Берёт переменную из окружения; если пусто — ValueError."""
    value = os.getenv(name)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise ValueError(f"Переменная окружения {name} не задана или пуста.")
    return value.strip()


def get_var_from_env_optional(name: str) -> str | None:
    """Берёт переменную из окружения или None."""
    value = os.getenv(name)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    return value.strip()
```

**Step 2: `time_helpers.py` — копия из launch_analyzer-master**

```python
"""Дата/время для отчётов (МСК +03:00)."""
from datetime import datetime, timezone, timedelta


def timestamp_to_datetime_string(ms_timestamp: int | None) -> str:
    """Переводит timestamp в миллисекундах в строку ДД.ММ.ГГГГ ЧЧ:ММ:СС."""
    if ms_timestamp is None:
        return "—"
    tz = timezone(timedelta(hours=3))
    dt = datetime.fromtimestamp(ms_timestamp / 1000.0, tz=tz)
    return dt.strftime("%d.%m.%Y %H:%M:%S")
```

**Step 3: Smoke-check, что импорты работают**

Run (PowerShell, в корне проекта):
```powershell
$env:PYTHONPATH = (Get-Location).Path
python -c "from common.helpers.env_helper import get_var_from_env_optional; print('ok')"
```
Expected: `ok` (без трейсбэка).

---

## Task 3: Парсер URL сьюта — чистая функция

**Files:**
- Create: `C:\Users\Andrey\PycharmProjects\mapping\api\allure\suite_url.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\tests\test_suite_url.py`

**Step 1: Написать failing-тест**

```python
"""Тесты парсера URL сьюта Allure."""
import pytest

from api.allure.suite_url import parse_suite_url, SuiteRef


def test_parse_full_suite_url():
    url = "https://allure.nexign.com/project/313/test-cases/836208?treeId=811&from=WzExNTUyN10%3D"
    ref = parse_suite_url(url)
    assert ref == SuiteRef(project_id=313, tree_id=811, path=115527)


def test_parse_suite_url_without_from():
    url = "https://allure.nexign.com/project/313/test-cases/836208?treeId=811"
    with pytest.raises(ValueError, match="from"):
        parse_suite_url(url)


def test_parse_suite_url_bad_base64():
    url = "https://allure.nexign.com/project/313/test-cases/836208?treeId=811&from=not_base64!!!"
    with pytest.raises(ValueError):
        parse_suite_url(url)


def test_parse_suite_url_missing_project():
    url = "https://allure.nexign.com/test-cases/836208?treeId=811&from=WzExNTUyN10%3D"
    with pytest.raises(ValueError, match="project"):
        parse_suite_url(url)
```

**Step 2: Прогнать тест — упадёт, модуля нет**

Run:
```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m pytest tests/test_suite_url.py -v
```
Expected: FAIL с `ModuleNotFoundError: No module named 'api.allure.suite_url'`.

**Step 3: Реализовать минимум**

```python
"""Парсер URL сьюта Allure TestOps в (project_id, tree_id, path)."""
import base64
import json
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs


@dataclass(frozen=True)
class SuiteRef:
    project_id: int
    tree_id: int
    path: int


_PROJECT_RE = re.compile(r"/project/(\d+)/")


def parse_suite_url(url: str) -> SuiteRef:
    """URL сьюта вида https://.../project/313/test-cases/836208?treeId=811&from=Wzxxx → SuiteRef."""
    parsed = urlparse(url)
    project_match = _PROJECT_RE.search(parsed.path)
    if not project_match:
        raise ValueError(f"В URL не найден /project/<id>/: {url}")
    project_id = int(project_match.group(1))

    qs = parse_qs(parsed.query)
    tree_id_raw = qs.get("treeId", [None])[0]
    from_raw = qs.get("from", [None])[0]
    if tree_id_raw is None:
        raise ValueError(f"В URL нет treeId: {url}")
    if from_raw is None:
        raise ValueError(f"В URL нет from (нужен для path сьюта): {url}")

    try:
        decoded = base64.b64decode(from_raw).decode("utf-8")
        path_list = json.loads(decoded)
    except Exception as exc:
        raise ValueError(f"Не получилось декодировать from='{from_raw}': {exc}") from exc

    if not isinstance(path_list, list) or not path_list:
        raise ValueError(f"from декодирован не в список с элементами: {path_list}")

    path = int(path_list[-1])
    return SuiteRef(project_id=project_id, tree_id=int(tree_id_raw), path=path)
```

Пояснение: берём **последний** элемент массива в `from` — это id ближайшего родителя (того самого сьюта). Пример: `WzExNTUyN10=` → `[115527]`, одиночный элемент. Если будут вложенные `[1, 2, 3]` — нужен последний.

**Step 4: Прогнать тест — должен пройти**

Run:
```powershell
python -m pytest tests/test_suite_url.py -v
```
Expected: 4 passed.

---

## Task 4: Парсер тэга в имени кейса — чистая функция

**Files:**
- Create: `C:\Users\Andrey\PycharmProjects\mapping\api\allure\name_parser.py`
- Create: `C:\Users\Andrey\PycharmProjects\mapping\tests\test_name_parser.py`

Тэг парсим **исключительно из имени кейса**. Поле `tags[]` из API-ответа игнорируем.

Допустимые формы тэга (по словам юзера: «O1, 02 … 06, 1A…6A, 1X…6X», + пример `(О)` из реальных данных):
- `O1..O6` / `О1..О6` — латинская O или Cyrillic О + цифра 1–6
- `1A..6A` — цифра 1–6 + латинская A
- `1X..6X` — цифра 1–6 + латинская X
- Опционально может быть обёрнут в скобки: `(О1)`, `(1A)` и т.д.

Тэг **один на имя** (юзер: «в единичном экземпляре»). Может стоять где угодно. Если не нашли — `tag=""`.

**Step 1: Написать failing-тест**

```python
"""Тесты парсера тэга в имени кейса (O1..O6 / О1..О6 / 1A..6A / 1X..6X, может быть в скобках)."""
import pytest

from api.allure.name_parser import split_tag_and_requirement


@pytest.mark.parametrize(
    "name,expected_tag,expected_req",
    [
        ("O1 Ручное закрытие лицевого счёта", "O1", "Ручное закрытие лицевого счёта"),
        ("Ручное закрытие O3", "O3", "Ручное закрытие"),
        ("Подготовка списка 1A", "1A", "Подготовка списка"),
        ("4X Создание массовой операции", "4X", "Создание массовой операции"),
        ("Создание 6A заявки", "6A", "Создание заявки"),
        ("Foo 2X bar baz", "2X", "Foo bar baz"),
        # Cyrillic О + digit
        ("О1 Закрытие ЛС", "О1", "Закрытие ЛС"),
        ("Закрытие ЛС О6", "О6", "Закрытие ЛС"),
        # В скобках
        ("Создание заявки (1A)", "1A", "Создание заявки"),
        ("(О2) Закрытие", "О2", "Закрытие"),
        ("02. Разблокировка продукта с APN (О1)", "О1", "02. Разблокировка продукта с APN"),
    ],
)
def test_parses_known_tags(name, expected_tag, expected_req):
    tag, req = split_tag_and_requirement(name)
    assert tag == expected_tag
    assert req == expected_req


def test_no_tag_returns_empty_tag_and_full_name():
    tag, req = split_tag_and_requirement("Просто кейс без тэга")
    assert tag == ""
    assert req == "Просто кейс без тэга"


def test_collapses_internal_double_spaces():
    tag, req = split_tag_and_requirement("Создание   2A   заявки")
    assert tag == "2A"
    assert req == "Создание заявки"


def test_does_not_match_inside_word():
    # O1 внутри слова не считается тэгом
    tag, req = split_tag_and_requirement("foo_O1_bar test")
    assert tag == ""
    assert req == "foo_O1_bar test"


def test_does_not_match_bare_cyrillic_O():
    # Одиночная "О" без цифры — НЕ тэг (юзер перечислил только O1..O6, 1A..6A, 1X..6X).
    # Если такие кейсы реально есть — расширим регулярку, но сейчас YAGNI.
    tag, req = split_tag_and_requirement("Разблокировка продукта (О)")
    assert tag == ""
```

**Step 2: Прогнать — упадёт**

Run:
```powershell
python -m pytest tests/test_name_parser.py -v
```
Expected: FAIL (модуля нет).

**Step 3: Реализация**

```python
"""Парсер тэга в имени кейса.

Допустимые формы (одна на имя): O1..O6 / О1..О6 / 1A..6A / 1X..6X.
Опционально в скобках: (1A), (О2) и т.п.
"""
import re
from typing import Tuple

# Группа 1 = чистый тэг (без возможных скобок вокруг).
# Не матчим внутри \w, чтобы "foo_O1_bar" не отдавался за тэг.
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
```

**Step 4: Прогнать — pass**

Run:
```powershell
python -m pytest tests/test_name_parser.py -v
```
Expected: все тесты зелёные.

---

## Task 5: `AllureSuite` — авторизация и базовый клиент

**Files:**
- Create: `C:\Users\Andrey\PycharmProjects\mapping\api\allure\suite.py`

**Step 1: Скелет класса + JWT (1-в-1 как в launch.py)**

```python
"""Работа со сьютом в Allure TestOps: список кейсов, детали кейсов, сборка маппинга."""
from typing import Any, Dict, List, Optional

import requests

from api.allure.name_parser import split_tag_and_requirement
from api.allure.suite_url import SuiteRef, parse_suite_url
from api.exceptions import AllureSuiteNotFoundException, AllureTestCaseNotFoundException
from common.helpers.env_helper import get_var_from_env


class AllureSuite:
    ALLURE_URL = get_var_from_env("ALLURE_URL")
    TOKEN = get_var_from_env("ALLURE_TOKEN")

    def __init__(self, suite_url: str) -> None:
        self.suite_url = suite_url
        self.ref: SuiteRef = parse_suite_url(suite_url)
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self._get_jwt_token()}"})

    def _get_jwt_token(self) -> str:
        data = {"grant_type": "apitoken", "scope": "openid", "token": self.TOKEN}
        response = self.session.post(
            self.ALLURE_URL + "/api/uaa/oauth/token", data=data
        )
        assert response.status_code == 200, (
            f"Не удалось авторизоваться в Allure.\n"
            f"Статус: {response.status_code}\nОшибка: {response.text}"
        )
        return response.json().get("access_token")
```

**Step 2: Sanity-check — конструктор не падает при правильном .env**

Run (вручную, требуется заполненный `.env`):
```powershell
$env:PYTHONPATH = (Get-Location).Path
python -c "from api.allure.suite import AllureSuite; s = AllureSuite('https://allure.nexign.com/project/313/test-cases/836208?treeId=811&from=WzExNTUyN10%3D'); print(s.ref)"
```
Expected: `SuiteRef(project_id=313, tree_id=811, path=115527)`. Если 401/403 — проверь токен в `.env`.

---

## Task 6: `AllureSuite.list_test_cases()` — пагинированный обход `testcasetree/leaf`

**Files:**
- Modify: `C:\Users\Andrey\PycharmProjects\mapping\api\allure\suite.py`

Endpoint известен из ответа пользователя:
```
GET /api/rs/testcasetree/leaf?projectId={project_id}&path={path}&treeId={tree_id}&sort=name,asc&size=100&page=N
```
Ответ:
```json
{
  "content": [{"id": 656652, "name": "...", "automated": false, "statusName": "Draft", ...}],
  "totalPages": 1,
  "totalElements": 3,
  "last": true,
  ...
}
```

**Step 1: Добавить метод в класс `AllureSuite`**

```python
    def list_test_cases(self) -> List[Dict[str, Any]]:
        """Все кейсы в сьюте через testcasetree/leaf (с пагинацией)."""
        all_cases: List[Dict[str, Any]] = []
        page = 0
        size = 100
        while True:
            url = (
                self.ALLURE_URL
                + "/api/rs/testcasetree/leaf"
                + f"?projectId={self.ref.project_id}"
                + f"&path={self.ref.path}"
                + f"&treeId={self.ref.tree_id}"
                + f"&sort=name%2Casc"
                + f"&size={size}"
                + f"&page={page}"
            )
            response = self.session.get(url)
            assert response.status_code == 200, (
                f"Не удалось получить кейсы сьюта.\n"
                f"URL: {url}\nСтатус: {response.status_code}\nОшибка: {response.text}"
            )
            data = response.json()
            content = data.get("content") or []
            all_cases.extend(content)
            if data.get("last", True) or page + 1 >= data.get("totalPages", 1):
                break
            page += 1
        if not all_cases:
            raise AllureSuiteNotFoundException(
                f"В сьюте {self.suite_url} нет кейсов (или path={self.ref.path} неверный)."
            )
        return all_cases
```

**Step 2: Проверить вручную на реальном сьюте**

Run:
```powershell
$env:PYTHONPATH = (Get-Location).Path
python -c "from api.allure.suite import AllureSuite; s = AllureSuite('https://allure.nexign.com/project/313/test-cases/836208?treeId=811&from=WzExNTUyN10%3D'); cases = s.list_test_cases(); print(len(cases), cases[0])"
```
Expected: распечатает число кейсов и первый объект с полями `id`, `name`, `automated`.

---

## Task 7: `AllureSuite.get_test_case_overview()` — детали кейса

**Files:**
- Modify: `C:\Users\Andrey\PycharmProjects\mapping\api\allure\suite.py`

Endpoint от пользователя:
```
GET /api/rs/testcase/{id}/overview
```
Релевантные поля JSON:
- `name` — имя кейса (например, `"02. Разблокировка продукта с APN (О)"`).
- `tags[]` — `[{"id": 269449, "name": "О"}]`. Канонический источник тэга.
- `links[]` — `[{"name": "CLM-488937. ГФС. ...", "url": "https://confluence.nexign.com/pages/viewpage.action?pageId=875728720"}]`. Отсюда тянем фичу — ключ парсим из `name`.
- `status.name` — статус кейса (`"Draft"`, `"Ready"`, …).
- `members[]` — `[{"name": "Lidiya.Dubovets", "role": {"name": "Owner"}}]`. Автор кейса = `Owner`.

**Step 1: Метод-обёртка**

```python
    def get_test_case_overview(self, test_case_id: int) -> Dict[str, Any]:
        """Полные данные кейса через /api/rs/testcase/{id}/overview."""
        url = self.ALLURE_URL + f"/api/rs/testcase/{test_case_id}/overview"
        response = self.session.get(url)
        if response.status_code == 404:
            raise AllureTestCaseNotFoundException(
                f"Кейс {test_case_id} не найден в Allure."
            )
        assert response.status_code == 200, (
            f"Не удалось получить overview кейса {test_case_id}.\n"
            f"Статус: {response.status_code}\nОшибка: {response.text}"
        )
        return response.json()
```

**Step 2: Проверить вручную**

Run:
```powershell
$env:PYTHONPATH = (Get-Location).Path
python -c "
from api.allure.suite import AllureSuite
s = AllureSuite('https://allure.nexign.com/project/313/test-cases/836208?treeId=811&from=WzExNTUyN10%3D')
ov = s.get_test_case_overview(920311)
print('name:', ov['name'])
print('tags:', ov.get('tags'))
print('links:', ov.get('links'))
print('status:', ov.get('status', {}).get('name'))
"
```
Expected: имя кейса, список тэгов с `{"name": "О"}`, список линков с CLM-… и Confluence URL, статус (`Draft`).

---

## Task 8: `AllureSuite.build_mapping()` — главный сборщик

**Files:**
- Modify: `C:\Users\Andrey\PycharmProjects\mapping\api\allure\suite.py`

**Step 1: Хелперы для выкусывания фичи и автора**

```python
import re

_FEATURE_KEY_RE = re.compile(r"^([A-Z]+-\d+)")


def _feature_from_links(links: List[Dict[str, Any]]) -> Dict[str, str]:
    """Первая запись из links[] → {key, name, url}. Ключ парсим из начала name (PROJ-123)."""
    if not links:
        return {"key": "—", "name": "", "url": ""}
    first = links[0]
    raw_name = first.get("name") or ""
    url = first.get("url") or ""
    match = _FEATURE_KEY_RE.match(raw_name)
    key = match.group(1) if match else raw_name.split(".", 1)[0].strip() or "—"
    return {"key": key, "name": raw_name, "url": url}


def _owner_from_members(members: List[Dict[str, Any]]) -> str:
    """Первый member с role.name == 'Owner'."""
    for m in members or []:
        if (m.get("role") or {}).get("name") == "Owner":
            return m.get("name") or ""
    return ""
```

Положить эти две функции в `api/allure/suite.py` на модульном уровне (выше класса), импорт `re` добавить наверху файла.

**Step 2: Метод-агрегатор внутри `AllureSuite`**

```python
    def build_mapping(self) -> List[Dict[str, Any]]:
        """
        Для каждого кейса — {test_case_id, test_case_url, suite_url, tag, requirement,
        feature, status, owner, doc_links}.
        Тэг парсим из имени кейса; поле tags[] из API игнорируем.
        """
        cases = self.list_test_cases()
        out: List[Dict[str, Any]] = []
        for case in cases:
            tc_id = case.get("id")
            if not tc_id:
                continue
            overview = self.get_test_case_overview(tc_id)
            name = overview.get("name") or ""
            tag, requirement = split_tag_and_requirement(name)
            out.append({
                "test_case_id": tc_id,
                "test_case_name": name,
                "test_case_url": (
                    f"{self.ALLURE_URL}/project/{self.ref.project_id}"
                    f"/test-cases/{tc_id}?treeId={self.ref.tree_id}"
                ),
                "suite_url": self.suite_url,
                "tag": tag,
                "requirement": requirement,
                "feature": _feature_from_links(overview.get("links") or []),
                "status": (overview.get("status") or {}).get("name", ""),
                "owner": _owner_from_members(overview.get("members") or []),
                "doc_links": overview.get("links") or [],
            })
        return out
```

**Step 3: Прогнать на реальном сьюте**

Run:
```powershell
$env:PYTHONPATH = (Get-Location).Path
python -c "
from api.allure.suite import AllureSuite
import json
s = AllureSuite('https://allure.nexign.com/project/313/test-cases/836208?treeId=811&from=WzExNTUyN10%3D')
print(json.dumps(s.build_mapping()[:2], ensure_ascii=False, indent=2))
"
```
Expected: 2 записи с заполненными `tag`, `requirement` (без `(О)` и без `02. `), `feature.key` вида `CLM-488937`, `status`, `owner`.

---

## Task 9: `MappingConfluencePage` — чтение и парсинг текущей страницы

**Files:**
- Create: `C:\Users\Andrey\PycharmProjects\mapping\api\confluence\mapping_page.py`

Аналог `ConfluencePage`, но работает с `parent_id`, переданным в конструктор, **обновляет тело этой самой страницы** (не создаёт ребёнка). Сохраняет шапку существующей таблицы (7 колонок), пересобирает `<tbody>`.

**Step 1: Скелет — auth + получение страницы**

```python
"""Обновление страницы маппинга требований и тестов в Confluence."""
from typing import Any, Dict, List

from atlassian import Confluence
from bs4 import BeautifulSoup

from api.exceptions import ConfluencePageNotFoundException
from common.helpers.env_helper import get_var_from_env


class MappingConfluencePage:
    CONFLUENCE_URL = get_var_from_env("CONFLUENCE_URL")
    CONFLUENCE_USERNAME = get_var_from_env("CONFLUENCE_USERNAME")
    CONFLUENCE_PASSWORD = get_var_from_env("CONFLUENCE_PASSWORD")

    HEADERS = [
        "Фича",
        "Ссылка на документацию КР/ГФС",
        "Автор документации",
        "Ссылка на тест-кейсы в Allure",
        "Автор тест-кейсов",
        "Статус",
        "Маппинг требований и тестов",
    ]

    def __init__(self, parent_id: int) -> None:
        self.page_id = int(parent_id)
        self.conf = Confluence(
            url=self.CONFLUENCE_URL,
            username=self.CONFLUENCE_USERNAME,
            password=self.CONFLUENCE_PASSWORD,
        )
        page = self.conf.get_page_by_id(self.page_id, expand="body.storage")
        if not page:
            raise ConfluencePageNotFoundException(
                f"Не нашёл страницу Confluence по id={self.page_id}"
            )
        self.title = page.get("title", "")
        self.body = str(page["body"]["storage"]["value"])
        self.soup = BeautifulSoup(self.body, "html.parser")
```

**Step 2: Smoke-check на реальной странице**

Run:
```powershell
$env:PYTHONPATH = (Get-Location).Path
python -c "from api.confluence.mapping_page import MappingConfluencePage; p = MappingConfluencePage(860817105); print(p.title, len(p.body))"
```
Expected: заголовок страницы и ненулевой размер тела.

---

## Task 10: `MappingConfluencePage.build_body()` — HTML маппинга

**Files:**
- Modify: `C:\Users\Andrey\PycharmProjects\mapping\api\confluence\mapping_page.py`

**Step 1: Группировка маппинга по фичам**

```python
    @staticmethod
    def _group_by_feature(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """{feature_key: [rows...]} — все строки одной фичи в одну группу."""
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            key = (row.get("feature") or {}).get("key") or "—"
            grouped.setdefault(key, []).append(row)
        return grouped
```

**Step 2: Сборка HTML тела**

```python
    def build_body(self, mapping_rows: List[Dict[str, Any]]) -> str:
        """Собирает HTML с одной таблицей-маппингом (7 колонок, шапка + строки по фичам)."""
        soup = BeautifulSoup("<div></div>", "html.parser")
        root = soup.div

        table = soup.new_tag("table", **{"class": "wrapped confluenceTable"})
        tbody = soup.new_tag("tbody")

        header_tr = soup.new_tag("tr")
        for col in self.HEADERS:
            th = soup.new_tag("th", **{"class": "confluenceTh"})
            th.string = col
            header_tr.append(th)
        tbody.append(header_tr)

        grouped = self._group_by_feature(mapping_rows)
        for feature_key, rows in grouped.items():
            first = rows[0]
            feature = first.get("feature") or {}
            tr = soup.new_tag("tr")

            # 1. Фича — ссылка на link.url с текстом feature.key.
            td_feature = soup.new_tag("td", **{"class": "confluenceTd"})
            if feature.get("url"):
                a = soup.new_tag("a", href=feature["url"])
                a.string = feature.get("key") or feature.get("name") or "—"
                td_feature.append(a)
            else:
                td_feature.string = feature.get("key", "—")
            tr.append(td_feature)

            # 2. Ссылка на документацию КР/ГФС — все doc_links из первого кейса.
            td_doc = soup.new_tag("td", **{"class": "confluenceTd"})
            for i, link in enumerate(first.get("doc_links") or []):
                if i > 0:
                    td_doc.append(soup.new_tag("br"))
                a = soup.new_tag("a", href=link.get("url", ""))
                a.string = link.get("name") or link.get("url") or ""
                td_doc.append(a)
            tr.append(td_doc)

            # 3. Автор документации — пусто (нет в API кейса).
            tr.append(soup.new_tag("td", **{"class": "confluenceTd"}))

            # 4. Ссылка на тест-кейсы в Allure — исходный --suite_url (не per-case).
            td_suite = soup.new_tag("td", **{"class": "confluenceTd"})
            suite_url = first.get("suite_url", "")
            if suite_url:
                a = soup.new_tag("a", href=suite_url)
                a.string = suite_url
                td_suite.append(a)
            tr.append(td_suite)

            # 5. Автор тест-кейсов — owner первого кейса (если у всех одинаков — единственный, иначе склейка).
            td_owner = soup.new_tag("td", **{"class": "confluenceTd"})
            owners = sorted({r.get("owner", "") for r in rows if r.get("owner")})
            td_owner.string = ", ".join(owners) if owners else ""
            tr.append(td_owner)

            # 6. Статус — статус первого кейса (если разные — все через запятую).
            td_status = soup.new_tag("td", **{"class": "confluenceTd"})
            statuses = sorted({r.get("status", "") for r in rows if r.get("status")})
            td_status.string = ", ".join(statuses) if statuses else ""
            tr.append(td_status)

            # 7. Маппинг (вложенная таблица: Требование из ГФС | Ссылка на тест-кейс).
            td_mapping = soup.new_tag("td", **{"class": "confluenceTd"})
            inner_table = soup.new_tag("table", **{"class": "wrapped confluenceTable"})
            inner_tbody = soup.new_tag("tbody")
            inner_header_tr = soup.new_tag("tr")
            for inner_col in ("Требование из ГФС", "Ссылка на тест-кейс"):
                th = soup.new_tag("th", **{"class": "confluenceTh"})
                th.string = inner_col
                inner_header_tr.append(th)
            inner_tbody.append(inner_header_tr)

            for row in rows:
                inner_tr = soup.new_tag("tr")

                td_req = soup.new_tag("td", **{"class": "confluenceTd"})
                req_text = row.get("requirement", "—")
                tag_text = row.get("tag", "")
                # Тэг в скобках перед именем требования, как в исходной странице ("(О)").
                td_req.string = f"({tag_text}) {req_text}" if tag_text else req_text
                inner_tr.append(td_req)

                td_case = soup.new_tag("td", **{"class": "confluenceTd"})
                tc_url = row.get("test_case_url")
                if tc_url:
                    a = soup.new_tag("a", href=tc_url)
                    a.string = str(row.get("test_case_id", ""))
                    td_case.append(a)
                else:
                    td_case.string = str(row.get("test_case_id", ""))
                inner_tr.append(td_case)
                inner_tbody.append(inner_tr)
            inner_table.append(inner_tbody)
            td_mapping.append(inner_table)
            tr.append(td_mapping)

            tbody.append(tr)

        table.append(tbody)
        root.append(table)
        return str(root)
```

**Step 3: Прогнать в холостую (на mock-данных)**

Run:
```powershell
$env:PYTHONPATH = (Get-Location).Path
python -c "
from api.confluence.mapping_page import MappingConfluencePage
p = MappingConfluencePage(860817105)
rows = [
    {'feature': {'key': 'CLM-488937', 'name': 'CLM-488937. ГФС. Динамическое формирование имён счётчиков', 'url': 'https://confluence.nexign.com/pages/viewpage.action?pageId=875728720'},
     'requirement': 'Разблокировка продукта с APN', 'tag': 'О', 'status': 'Draft', 'owner': 'Lidiya.Dubovets',
     'test_case_id': 920311, 'test_case_url': 'https://allure.nexign.com/project/313/test-cases/920311?treeId=811',
     'suite_url': 'https://allure.nexign.com/project/313/test-cases/836208?treeId=811&from=WzExNTUyN10%3D',
     'doc_links': [{'name': 'CLM-488937. ГФС. Динамическое формирование имён счётчиков', 'url': 'https://confluence.nexign.com/pages/viewpage.action?pageId=875728720'}]},
]
print(p.build_body(rows)[:800])
"
```
Expected: HTML-фрагмент с `<table>`, фичей `CLM-488937` как ссылкой на Confluence, требованием `(О) Разблокировка продукта с APN`.

---

## Task 11: `MappingConfluencePage.update()` — заливка тела

**Files:**
- Modify: `C:\Users\Andrey\PycharmProjects\mapping\api\confluence\mapping_page.py`

**Step 1: Метод update**

```python
    def update(self, new_body_html: str) -> Dict[str, Any]:
        """Заменяет тело страницы на new_body_html (заголовок не трогаем)."""
        return self.conf.update_page(
            self.page_id,
            self.title,
            new_body_html,
            always_update=True,
        )
```

**Step 2: Проверить на TEST-странице (НЕ на проде!)**

Перед запуском попросить пользователя:
> «Дай ID тестовой страницы Confluence, на которой можно безопасно перетереть тело. На прод-страницу `860817105` запускаем только после твоего OK.»

Run (с тестовым ID):
```powershell
$env:PYTHONPATH = (Get-Location).Path
python -c "
from api.confluence.mapping_page import MappingConfluencePage
p = MappingConfluencePage(<TEST_ID>)
res = p.update('<p>smoke test</p>')
print(res.get('id'), res.get('title'))
"
```
Expected: страница теперь содержит «smoke test»; визуально проверить через браузер.

После проверки — **вернуть исходное тело** (`p.update(p.body)` до перезаписи, либо сделать копию `original_body = p.body` заранее).

---

## Task 12: Главный скрипт `mapping_to_confluence.py`

**Files:**
- Create: `C:\Users\Andrey\PycharmProjects\mapping\scripts\confluence\mapping_to_confluence.py`

**Step 1: argparse + оркестрация (повторяет стиль `report_to_confluence.py`)**

```python
"""Гоняет маппинг требований и тест-кейсов из Allure в страницу Confluence по parent_id."""
import argparse
from typing import List

from api.allure.suite import AllureSuite
from api.confluence.mapping_page import MappingConfluencePage


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Обновить страницу маппинга требований и тестов в Confluence по сьюту(ам) Allure."
    )
    parser.add_argument(
        "--parent_id",
        type=int,
        required=True,
        help="ID страницы Confluence, тело которой будем перезаписывать.",
    )
    parser.add_argument(
        "--suite_url",
        type=str,
        action="append",
        required=True,
        help="URL сьюта Allure. Можно передать несколько раз (--suite_url ... --suite_url ...).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    all_rows: List[dict] = []
    for url in args.suite_url:
        suite = AllureSuite(suite_url=url)
        all_rows.extend(suite.build_mapping())

    page = MappingConfluencePage(parent_id=args.parent_id)
    html_body = page.build_body(all_rows)
    result = page.update(html_body)
    page_id = result.get("id")
    if page_id:
        print(f"https://confluence.nexign.com/pages/viewpage.action?pageId={page_id}")


if __name__ == "__main__":
    main()
```

**Step 2: Сухой прогон с одним сьютом на TEST-странице**

Run (PowerShell):
```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/confluence/mapping_to_confluence.py `
    --parent_id <TEST_ID> `
    --suite_url "https://allure.nexign.com/project/313/test-cases/836208?treeId=811&from=WzExNTUyN10%3D"
```
Expected: распечатан URL обновлённой страницы; в браузере — таблица с фичей `RMBSS-14303`, требованиями и кейсами.

**Step 3: Прогон с двумя сьютами**

```powershell
python scripts/confluence/mapping_to_confluence.py `
    --parent_id <TEST_ID> `
    --suite_url "<URL_1>" `
    --suite_url "<URL_2>"
```
Expected: две группы фич в одной таблице.

---

## Task 13: README

**Files:**
- Create: `C:\Users\Andrey\PycharmProjects\mapping\README.md`

**Step 1: Содержимое — копия стилистики launch_analyzer-master/README.md**

```markdown
# Маппинг требований и тестов в Confluence

Скрипт берёт сьюты Allure TestOps по URL, тянет кейсы, из имени каждого вытаскивает тэг (`O1..O6` / `1A..6A` / `1X..6X`) и название требования, по линкам кейса находит фичу (Jira-ключ), и обновляет тело страницы Confluence по `--parent_id`.

## Что нужно перед запуском

1. В корне проекта должен быть файл **.env** с переменными (образец — `.env.example`): Allure (URL, токен), Confluence (URL, логин, пароль).
2. Запуск из **корня проекта** и с **PYTHONPATH = корень проекта**, иначе скрипт не найдёт модули.

## Как запустить

**Один сьют:**

```bash
# Windows (PowerShell)
cd C:\Users\...\mapping
$env:PYTHONPATH = (Get-Location).Path
python scripts/confluence/mapping_to_confluence.py --parent_id 860817105 --suite_url "https://allure.nexign.com/project/313/test-cases/836208?treeId=811&from=WzExNTUyN10%3D"
```

```bash
# Linux / macOS
cd /path/to/mapping
export PYTHONPATH=$PWD
python scripts/confluence/mapping_to_confluence.py --parent_id 860817105 --suite_url "https://allure.nexign.com/project/313/test-cases/836208?treeId=811&from=WzExNTUyN10%3D"
```

**Несколько сьютов в одной таблице:**

```bash
python scripts/confluence/mapping_to_confluence.py \
    --parent_id 860817105 \
    --suite_url "URL_сьюта_1" \
    --suite_url "URL_сьюта_2"
```

После успешного запуска тело страницы Confluence заменяется, в браузере ничего нажимать не нужно.
```

---

## Task 14: Финальная сверка с прод-страницей

**Files:** нет.

**Step 1: Перед запуском на прод (`860817105`) — показать пользователю результат на TEST-странице.**

> «Готово, на TEST-странице (ID=...) маппинг отрисован вот так: [скриншот / прямой URL]. Можно ли пускать на прод (`pageId=860817105`)?»

**Step 2: Только после `да` — прогон на прод-странице с реальными сьютами.**

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/confluence/mapping_to_confluence.py `
    --parent_id 860817105 `
    --suite_url "<реальный URL сьюта>"
```

**Step 3: Проверить в браузере, что таблица обновилась корректно.**

---

## DRY / YAGNI заметки

- **Не реализуем** автоматический парсинг авторов документации/тест-кейсов, КР/ГФС-ссылок и статуса — TZ их не упоминает, оставляем пустыми колонками. Если позже понадобится — добавим отдельной задачей.
- **Не реализуем** возврат к старому телу страницы из коробки. Если нужен rollback — заведём отдельный флаг `--dry_run` (печатать тело в stdout без update). Сейчас YAGNI.
- **Не реализуем** кеширование запросов к Allure — на типичной сьюте несколько десятков кейсов, нет смысла усложнять.
- **Не добавляем** GitLab-зависимость из соседа — она не нужна.
- Тесты — только на чистые функции (`parse_suite_url`, `split_tag_and_requirement`). Сетевые классы тестируем ручным прогоном, как в соседнем скрипте.
