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
