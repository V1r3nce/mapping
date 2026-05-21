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
    """Собирает маппинг по всем сьютам и обновляет страницу Confluence."""
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
