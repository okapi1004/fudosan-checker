import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from db.models import Property
from scrapers.base import PlaywrightScraper

logger = logging.getLogger(__name__)


class AthomeScraper(PlaywrightScraper):
    """アットホームスクレイパー。

    アットホームは動的コンテンツが多いためPlaywrightを使用。
    検索条件をブラウザで設定し、そのURLをconfig.yamlに貼り付ける。
    """

    site_name = "アットホーム"

    def scrape(self) -> list[Property]:
        if not self.search_url:
            logger.warning(f"[{self.site_name}] search_urlが未設定です")
            return []

        html = self._get_page_html(self.search_url, wait_selector=".property-data, .p-property-list-item")
        if not html:
            return []

        return self._parse(html)

    def _parse(self, html: str) -> list[Property]:
        soup = BeautifulSoup(html, "lxml")
        properties = []

        # アットホームの物件カード
        selectors = [
            "div.p-property-list-item",
            "div.property-data",
            "article.p-article",
        ]

        items = []
        for sel in selectors:
            items = soup.select(sel)
            if items:
                break

        for block in items:
            try:
                # 詳細リンク
                link_tag = block.select_one("a[href*='/chintai/'], a[href*='/kodate/'], a[href*='/mansion/'], a[href*='/tochi/'], a[href*='/invest/']")
                if not link_tag:
                    link_tag = block.select_one("a")
                url = ""
                if link_tag and link_tag.get("href"):
                    url = urljoin("https://www.athome.co.jp", link_tag["href"])

                # タイトル
                title_tag = block.select_one("h2, .p-property-title, .property-data-title, .p-article__title")
                title = title_tag.get_text(strip=True) if title_tag else ""

                # 価格
                price_tag = block.select_one(".p-property-price, .property-data-price, .p-article__price")
                price = price_tag.get_text(strip=True) if price_tag else ""

                # 住所
                addr_tag = block.select_one(".p-property-address, .property-data-address, .p-article__address")
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
