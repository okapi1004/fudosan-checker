import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from db.models import Property
from scrapers.base import PlaywrightScraper

logger = logging.getLogger(__name__)


class KenbiyaScraper(PlaywrightScraper):
    """健美家スクレイパー。

    健美家はJSでページ遷移するため、Playwrightを使用。
    検索結果URLをそのまま指定する。
    """

    site_name = "健美家"

    def scrape(self) -> list[Property]:
        if not self.search_url:
            logger.warning(f"[{self.site_name}] search_urlが未設定です")
            return []

        html = self._get_page_html(self.search_url, wait_selector="ul.prop_block")
        if not html:
            return []

        return self._parse(html)

    def _parse(self, html: str) -> list[Property]:
        soup = BeautifulSoup(html, "lxml")
        properties = []

        # 物件リストの親を取得
        container = soup.select_one("#box_property_list")
        if not container:
            logger.warning(f"[{self.site_name}] 物件リストが見つかりません")
            return []

        # 各物件は <a> タグの中に ul.prop_block がある
        for block in container.select("ul.prop_block"):
            try:
                # 詳細リンク: prop_blockの親の<a>タグ
                link_tag = block.find_parent("a")
                url = ""
                if link_tag and link_tag.get("href"):
                    url = urljoin("https://www.kenbiya.com", link_tag["href"])

                # タイトル
                title_tag = block.select_one("li.main h3")
                title = title_tag.get_text(strip=True) if title_tag else ""

                # 価格
                price_tag = block.select_one("li.price ul li:first-child span")
                price = ""
                if price_tag:
                    price = price_tag.get_text(strip=True) + "万円"

                # 利回り
                yield_tag = block.select_one("li.price ul li:nth-child(2) span")
                yield_rate = ""
                if yield_tag:
                    yield_rate = yield_tag.get_text(strip=True) + "%"

                # 住所
                addr_tag = block.select_one("li.main ul li:nth-child(2)")
                address = addr_tag.get_text(strip=True) if addr_tag else ""

                if url and title:
                    properties.append(Property(
                        url=url,
                        title=title,
                        price=price,
                        site=self.site_name,
                        address=address,
                        yield_rate=yield_rate,
                    ))
            except Exception as e:
                logger.error(f"[{self.site_name}] パースエラー: {e}")
                continue

        logger.info(f"[{self.site_name}] {len(properties)}件の物件を取得")
        return properties
