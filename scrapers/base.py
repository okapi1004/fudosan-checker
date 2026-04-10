import logging
import time
from abc import ABC, abstractmethod

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Browser, Page

from db.models import Property

logger = logging.getLogger(__name__)

# 共通ヘッダー
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# リクエスト間の最低待機時間（秒）
REQUEST_DELAY = 3


class BaseScraper(ABC):
    """スクレイパーの基底クラス。"""

    site_name: str = ""

    def __init__(self, search_url: str):
        self.search_url = search_url

    @abstractmethod
    def scrape(self) -> list[Property]:
        """検索結果ページから物件リストを取得する。"""
        ...

    def _delay(self):
        time.sleep(REQUEST_DELAY)


class PlaywrightScraper(BaseScraper):
    """Playwrightを使用するスクレイパーの基底クラス。"""

    def _get_page_html(self, url: str, wait_selector: str | None = None) -> str:
        """Playwrightでページを取得し、HTMLを返す。"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="ja-JP",
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=15000)
                html = page.content()
            except Exception as e:
                logger.error(f"[{self.site_name}] ページ取得エラー: {url} - {e}")
                html = ""
            finally:
                browser.close()
            self._delay()
            return html


class RequestsScraper(BaseScraper):
    """requestsを使用するスクレイパーの基底クラス。"""

    def _get_page_html(self, url: str) -> str:
        import requests
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            self._delay()
            return resp.text
        except Exception as e:
            logger.error(f"[{self.site_name}] ページ取得エラー: {url} - {e}")
            self._delay()
            return ""
