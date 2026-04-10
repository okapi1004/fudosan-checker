import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from db.models import Property
from scrapers.base import RequestsScraper

logger = logging.getLogger(__name__)


class SuumoScraper(RequestsScraper):
    """SUUMOスクレイパー。

    SUUMOの検索結果ページをスクレイピング。
    検索条件をブラウザで設定し、そのURLをconfig.yamlに貼り付ける。
    """

    site_name = "SUUMO"

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

        # SUUMOの物件リスト: div.property_unit が各物件
        for block in soup.select("div.property_unit"):
            try:
                # 詳細リンク
                link_tag = block.select_one("a.property_unit-title_text, h2 a, .dottable-vm a")
                url = ""
                if link_tag and link_tag.get("href"):
                    url = urljoin("https://suumo.jp", link_tag["href"])

                # タイトル
                title = link_tag.get_text(strip=True) if link_tag else ""

                # 価格
                price_tag = block.select_one(".dottable-vm .detailnote-price, .dottable-line--price .dottable-value")
                price = price_tag.get_text(strip=True) if price_tag else ""

                # 住所
                addr_parts = block.select(".detailbox .detailbox-property--col1 dt")
                address = ""
                for dt in addr_parts:
                    if "所在地" in dt.get_text():
                        dd = dt.find_next_sibling("dd")
                        if dd:
                            address = dd.get_text(strip=True)
                        break

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

        # 代替セレクタ: cassetteitem (賃貸・売買共通の別レイアウト)
        if not properties:
            for block in soup.select(".cassetteitem"):
                try:
                    link_tag = block.select_one(".cassetteitem_content-title a, .cassetteitem_other-linktext a")
                    url = ""
                    if link_tag and link_tag.get("href"):
                        url = urljoin("https://suumo.jp", link_tag["href"])

                    title_tag = block.select_one(".cassetteitem_content-title")
                    title = title_tag.get_text(strip=True) if title_tag else ""

                    price_tag = block.select_one(".cassetteitem_price--accent")
                    price = price_tag.get_text(strip=True) if price_tag else ""

                    addr_tag = block.select_one(".cassetteitem_detail-col1")
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
