import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from db.models import Property
from scrapers.base import PlaywrightScraper

logger = logging.getLogger(__name__)


class FudosanJapanScraper(PlaywrightScraper):
    """不動産ジャパンスクレイパー。

    不動産ジャパン (fudousan.or.jp) は国交省系のポータル。
    requestsでは403になるため、Playwrightを使用。
    """

    site_name = "不動産ジャパン"

    def scrape(self) -> list[Property]:
        if not self.search_url:
            logger.warning(f"[{self.site_name}] search_urlが未設定です")
            return []

        html = self._get_page_html(self.search_url)
        if not html:
            return []

        return self._parse(html)

    def _parse(self, html: str) -> list[Property]:
        soup = BeautifulSoup(html, "lxml")
        properties = []

        # 不動産ジャパンの物件リスト
        selectors = [
            "div.property-cassette",
            "div.property-item",
            "div.bukken-item",
            "article.result-item",
            "li.result-list-item",
        ]

        items = []
        for sel in selectors:
            items = soup.select(sel)
            if items:
                break

        for block in items:
            try:
                link_tag = block.select_one("a[href]")
                url = ""
                if link_tag and link_tag.get("href"):
                    url = urljoin("https://www.fudousan.or.jp", link_tag["href"])

                title_tag = block.select_one("h2, h3, .property-name, .bukken-name")
                title = title_tag.get_text(strip=True) if title_tag else ""

                price_tag = block.select_one(".property-price, .bukken-price, .price")
                price = price_tag.get_text(strip=True) if price_tag else ""

                addr_tag = block.select_one(".property-address, .bukken-address, .address")
                address = addr_tag.get_text(strip=True) if addr_tag else ""

                if url and title:
                    properties.append(Property(
                        url=url,
                        title=title,
                        price=price,
                        site=self.site_name,
                        address=address,
                    ))
            except Exception as e:
                logger.error(f"[{self.site_name}] パースエラー: {e}")
                continue

        logger.info(f"[{self.site_name}] {len(properties)}件の物件を取得")
        return properties
