import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from db.models import Property
from scrapers.base import PlaywrightScraper, RequestsScraper

logger = logging.getLogger(__name__)


class CustomScraper:
    """汎用スクレイパー。

    config.yamlで設定したCSSセレクタに基づき、
    任意の不動産会社サイトから物件情報を取得する。

    設定例:
      - name: "〇〇不動産"
        url: "https://example.co.jp/bukken/"
        use_playwright: true
        selectors:
          listing: ".bukken-item"
          title: ".bukken-title"
          price: ".bukken-price"
          link: "a"
          address: ".bukken-address"

    ラベルベース抽出（CSSセレクタでは取れない場合）:
      - name: "△△不動産"
        url: "https://example2.co.jp/bukken/"
        selectors:
          listing: ".vk_outer"
          title: "h2 a"
          link: "a"
        labels:
          price: "価　格"
          address: "所在地"
    """

    def __init__(self, config: dict):
        self.name = config.get("name", "カスタムサイト")
        self.url = config.get("url", "")
        self.use_playwright = config.get("use_playwright", False)
        self.selectors = config.get("selectors", {})
        self.labels = config.get("labels", {})

    def scrape(self) -> list[Property]:
        if not self.url:
            logger.warning(f"[{self.name}] URLが未設定です")
            return []

        if not self.selectors.get("listing"):
            logger.warning(f"[{self.name}] listingセレクタが未設定です")
            return []

        html = self._fetch_html()
        if not html:
            return []

        return self._parse(html)

    def _fetch_html(self) -> str:
        if self.use_playwright:
            scraper = _PlaywrightFetcher(self.name)
            return scraper.fetch(self.url, self.selectors.get("listing"))
        else:
            scraper = _RequestsFetcher(self.name)
            return scraper.fetch(self.url)

    def _parse(self, html: str) -> list[Property]:
        soup = BeautifulSoup(html, "lxml")
        properties = []

        listing_sel = self.selectors["listing"]
        title_sel = self.selectors.get("title", "h2, h3, a")
        price_sel = self.selectors.get("price", "")
        link_sel = self.selectors.get("link", "a")
        addr_sel = self.selectors.get("address", "")

        for block in soup.select(listing_sel):
            try:
                # リンク
                url = ""
                if link_sel:
                    link_tag = block.select_one(link_sel)
                    if link_tag and link_tag.get("href"):
                        url = urljoin(self.url, link_tag["href"])
                elif block.name == "a" and block.get("href"):
                    # listing自体が<a>タグの場合
                    url = urljoin(self.url, block["href"])
                else:
                    link_tag = block.select_one("a")
                    if link_tag and link_tag.get("href"):
                        url = urljoin(self.url, link_tag["href"])

                # タイトル
                title_tag = block.select_one(title_sel) if title_sel else None
                title = title_tag.get_text(strip=True) if title_tag else ""

                # 価格
                price = ""
                if price_sel:
                    price_tag = block.select_one(price_sel)
                    price = price_tag.get_text(strip=True) if price_tag else ""
                elif self.labels.get("price"):
                    price = self._extract_by_label(block, self.labels["price"])

                # 住所
                address = ""
                if addr_sel:
                    addr_tag = block.select_one(addr_sel)
                    address = addr_tag.get_text(strip=True) if addr_tag else ""
                elif self.labels.get("address"):
                    address = self._extract_by_label(block, self.labels["address"])

                if url and title:
                    properties.append(Property(
                        url=url,
                        title=title,
                        price=price,
                        site=self.name,
                        address=address,
                    ))
            except Exception as e:
                logger.error(f"[{self.name}] パースエラー: {e}")
                continue

        logger.info(f"[{self.name}] {len(properties)}件の物件を取得")
        return properties

    @staticmethod
    def _extract_by_label(block, label: str) -> str:
        """ラベルに対応する値を抽出する。

        以下のパターンに対応:
        1. <strong>ラベル</strong>テキスト
        2. <td>ラベル</td><td>値</td> (テーブル構造)
        3. <dt>ラベル</dt><dd>値</dd>
        """
        # パターン1: strong/b/span内のラベル → 次の兄弟
        for tag in block.find_all(["strong", "b", "dt", "th", "span"]):
            if label in tag.get_text():
                # テーブル構造: td > strong の場合、隣のtdを取得
                if tag.parent and tag.parent.name == "td":
                    next_td = tag.parent.find_next_sibling("td")
                    if next_td:
                        return next_td.get_text(strip=True)

                # dt/dd構造
                if tag.name == "dt":
                    dd = tag.find_next_sibling("dd")
                    if dd:
                        return dd.get_text(strip=True)

                # 次の兄弟テキストノードまたは次のタグのテキストを取得
                sibling = tag.next_sibling
                while sibling:
                    text = ""
                    if isinstance(sibling, str):
                        text = sibling.strip()
                    elif hasattr(sibling, "get_text"):
                        text = sibling.get_text(strip=True)
                    if text:
                        return text
                    sibling = sibling.next_sibling
        return ""


class _PlaywrightFetcher(PlaywrightScraper):
    def __init__(self, name: str):
        super().__init__("")
        self.site_name = name

    def scrape(self):
        raise NotImplementedError

    def fetch(self, url: str, wait_selector: str | None = None) -> str:
        return self._get_page_html(url, wait_selector)


class _RequestsFetcher(RequestsScraper):
    def __init__(self, name: str):
        super().__init__("")
        self.site_name = name

    def scrape(self):
        raise NotImplementedError

    def fetch(self, url: str) -> str:
        return self._get_page_html(url)
