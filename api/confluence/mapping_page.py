"""Точечное обновление колонок «Ссылка на тест-кейсы в Allure» и «Маппинг требований и тестов»."""
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from atlassian import Confluence
from bs4 import BeautifulSoup

from api.exceptions import ConfluencePageNotFoundException
from common.helpers.env_helper import get_var_from_env


_PAGE_ID_RE = re.compile(r"pageId=(\d+)")


class MappingConfluencePage:
    CONFLUENCE_URL = get_var_from_env("CONFLUENCE_URL")
    CONFLUENCE_USERNAME = get_var_from_env("CONFLUENCE_USERNAME")
    CONFLUENCE_PASSWORD = get_var_from_env("CONFLUENCE_PASSWORD")

    # Сколько колонок ожидаем в строке (из шапки страницы):
    # Фича | Док КР/ГФС | Автор док | Ссылка на тест-кейсы в Allure | Автор кейсов | Статус | Маппинг
    EXPECTED_COLUMNS = 7
    SUITE_URL_COLUMN_INDEX = 3   # 4-я колонка
    MAPPING_COLUMN_INDEX = -1    # последняя

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

    def build_body(self, mapping_rows: List[Dict[str, Any]]) -> str:
        """
        В существующем теле страницы для каждого --suite_url найти строку
        по ссылке на документацию КР/ГФС (из case.links[]). В этой строке:
          • записать suite_url в колонку «Ссылка на тест-кейсы в Allure» (4-я);
          • заменить колонку «Маппинг требований и тестов» (последняя) нашей таблицей
            Тэг | Требование из ГФС | Ссылка на тест-кейс.

        Остальные ячейки и остальные строки не трогаем.
        Если по какому-то suite_url строка не нашлась — кидаем ошибку.
        """
        by_suite: Dict[str, List[Dict[str, Any]]] = {}
        for row in mapping_rows:
            by_suite.setdefault(row.get("suite_url", ""), []).append(row)

        problems: List[str] = []
        for suite_url, rows in by_suite.items():
            links = self._collect_doc_links(rows)
            if not links:
                problems.append(
                    f"{suite_url}: у кейсов нет ссылок на документацию (links[] пустой)"
                )
                continue

            tr = None
            for link in links:
                tr = self._find_row_for_link(link.get("url", ""), link.get("name", ""))
                if tr is not None:
                    break
            if tr is None:
                pretty = ", ".join(f"{l.get('name','')}|{l.get('url','')}" for l in links)
                problems.append(
                    f"{suite_url}: ни одна из {len(links)} ссылок на доку не нашлась на странице: {pretty}"
                )
                continue

            tds = tr.find_all("td", recursive=False)
            self._set_suite_url_cell(tds[self.SUITE_URL_COLUMN_INDEX], suite_url)
            mapping_td = tds[self.MAPPING_COLUMN_INDEX]
            mapping_td.clear()
            mapping_td.append(self._build_inner_mapping_table(rows))

        if problems:
            raise ConfluencePageNotFoundException(
                "Не удалось обновить строки на странице:\n"
                + "\n".join(f"  - {p}" for p in problems)
            )

        return str(self.soup)

    def _collect_doc_links(self, rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Все непустые links из всех кейсов группы — без дублей по url, в исходном порядке.
        Оставляем только URL'ы из домена Confluence (см. CONFLUENCE_URL).
        Возвращает [{"url": ..., "name": ...}, ...].
        """
        confluence_host = urlparse(self.CONFLUENCE_URL).netloc.lower()
        seen: set = set()
        out: List[Dict[str, str]] = []
        for r in rows:
            for link in (r.get("doc_links") or []):
                url = (link or {}).get("url") or ""
                name = (link or {}).get("name") or ""
                if not url:
                    continue
                host = urlparse(url).netloc.lower()
                if host and host != confluence_host:
                    continue  # не Confluence — не док
                if url in seen:
                    continue
                seen.add(url)
                out.append({"url": url, "name": name})
        return out

    def _find_row_for_link(self, doc_url: str, doc_name: str):
        """
        Ищет <tr> страницы, содержащий ссылку на ту же доку (любой из способов).
        Возвращает <tr> с EXPECTED_COLUMNS td или None.

        Стратегии:
        1. <a href> совпадает с doc_url по path+query (без фрагмента).
        2. <a href> содержит тот же pageId=X (надёжнее, если есть лишние query-параметры).
        3. <ri:page ri:content-title=NAME> — Confluence-макрос вставки ссылки на страницу по title.
        4. <ri:page ri:content-id=PAGE_ID> — то же по id.
        5. Любой текстовый узел, дословно содержащий doc_name.
        """
        # 1 + 2: <a href>
        target_pq = self._path_with_query(doc_url)
        target_pid = self._extract_page_id(doc_url)
        for a in self.soup.find_all("a", href=True):
            href = a.get("href", "") or ""
            ok = (
                href == doc_url
                or self._path_with_query(href) == target_pq
                or (target_pid is not None and self._extract_page_id(href) == target_pid)
            )
            if not ok:
                continue
            tr = self._outer_tr(a)
            if tr is not None:
                return tr

        # 3 + 4: <ri:page>
        for ri in self.soup.find_all(["ri:page", "ri:Page"]):
            title = ri.get("ri:content-title") or ri.get("content-title")
            cid = ri.get("ri:content-id") or ri.get("content-id")
            if (doc_name and title == doc_name) or (target_pid is not None and str(cid or "") == str(target_pid)):
                tr = self._outer_tr(ri)
                if tr is not None:
                    return tr

        # 5: текст
        if doc_name:
            for node in self.soup.find_all(string=lambda s: bool(s and doc_name in s)):
                tr = self._outer_tr(node)
                if tr is not None:
                    return tr

        return None

    def _outer_tr(self, node):
        """Ближайший родительский <tr>, у которого ≥ EXPECTED_COLUMNS прямых <td>."""
        cur = node
        while cur is not None:
            tr = cur.find_parent("tr")
            if tr is None:
                return None
            tds = tr.find_all("td", recursive=False)
            if len(tds) >= self.EXPECTED_COLUMNS:
                return tr
            cur = tr  # поднимаемся выше, если этот tr — вложенный
        return None

    @staticmethod
    def _path_with_query(url: str) -> str:
        parsed = urlparse(url or "")
        if parsed.query:
            return f"{parsed.path}?{parsed.query}"
        return parsed.path

    @staticmethod
    def _extract_page_id(url: str) -> Optional[str]:
        if not url:
            return None
        m = _PAGE_ID_RE.search(url)
        return m.group(1) if m else None

    def _set_suite_url_cell(self, td, suite_url: str) -> None:
        """Заменяет содержимое td на одну ссылку на suite_url."""
        td.clear()
        a = self.soup.new_tag("a", href=suite_url)
        a.string = suite_url
        td.append(a)

    def _build_inner_mapping_table(self, rows: List[Dict[str, Any]]):
        """Вложенная таблица: Тэг | Требование из ГФС | Ссылка на тест-кейс."""
        soup = self.soup
        inner_table = soup.new_tag("table", **{"class": "wrapped confluenceTable"})
        inner_tbody = soup.new_tag("tbody")

        inner_header_tr = soup.new_tag("tr")
        for inner_col in ("Тэг", "Требование из ГФС", "Ссылка на тест-кейс"):
            th = soup.new_tag("th", **{"class": "confluenceTh"})
            th.string = inner_col
            inner_header_tr.append(th)
        inner_tbody.append(inner_header_tr)

        for row in rows:
            inner_tr = soup.new_tag("tr")

            td_tag = soup.new_tag("td", **{"class": "confluenceTd"})
            td_tag.string = row.get("tag", "")
            inner_tr.append(td_tag)

            td_req = soup.new_tag("td", **{"class": "confluenceTd"})
            td_req.string = row.get("requirement", "—")
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
        return inner_table

    def update(self, new_body_html: str) -> Dict[str, Any]:
        """Заменяет тело страницы на new_body_html (заголовок не трогаем)."""
        return self.conf.update_page(
            self.page_id,
            self.title,
            new_body_html,
            always_update=True,
        )
