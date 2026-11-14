import flet as ft

from frontend.api.client import ApiClient
from frontend.config import Settings
from frontend.ui.app import LibraryApp


def main(page: ft.Page) -> None:
    settings = Settings.from_environment()
    LibraryApp(page, ApiClient(settings.api_url)).run()


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER)
