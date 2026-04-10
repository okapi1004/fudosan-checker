import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from db.models import Property
from scrapers.base import RequestsScraper

logger = logging.getLogger(__name__)


class RakumachiScraper(RequestsScraper):
    """楽待スクレイパー。

    楽待は静的HTMLで取得可能。
    URL例: https://www.rakumachi.jp/syuuekibukken/area/prefecture/dimAll/?area=11
    ※ syuuekibukken (uが2つ) に注意
    """

    site_name = "楽待"

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

        for block in soup.select("div.propertyBlock"):
            try:
                # 詳細リンク
                link_tag = block.select_one("a.propertyBlock__content")
                url = ""
                if link_tag and link_tag.get("href"):
                    url = urljoin("https://www.rakumachi.jp", link_tag["href"])

                # タイトル
                title_tag = block.select_one("p.propertyBlock__name")
                title = title_tag.get_text(strip=True) if title_tag else ""

                # 物件種別
                dim_tag = block.select_one("p.propertyBlock__dimension")
                dim = dim_tag.get_text(strip=True) if dim_tag else ""
                if dim and title:
                    title = f"[{dim}] {title}"

                # 価格
                price_tag = block.select_one("b.price")
                price = price_tag.get_text(strip=True) if price_tag else ""

                # 利回り
                yield_tag = block.select_one("b.gross")
                yield_rate = yield_tag.get_text(strip=True) if yield_tag else ""

                # 住所
                addr_tag = block.select_one("span.propertyBlock__address")
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
