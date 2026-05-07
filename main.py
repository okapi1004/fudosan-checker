#!/usr/bin/env python3
"""不動産物件自動巡回・通知システム。

使い方:
  1. config.yaml に検索条件を設定
  2. .env に DISCORD_WEBHOOK_URL を設定
  3. python main.py          # 1回だけ実行
  4. python main.py --daemon  # スケジューラで定期実行
"""
import argparse
import logging
import os
import socket
import sys

import yaml
from dotenv import load_dotenv

# グローバルなソケットタイムアウト（DNS解決・TCP接続のハング防止）
socket.setdefaulttimeout(60)

from db.models import init_db, upsert_properties, mark_notified
from notifiers.discord import send_new_properties, send_price_changes
from scrapers.kenbiya import KenbiyaScraper
from scrapers.rakumachi import RakumachiScraper
from scrapers.suumo import SuumoScraper
from scrapers.athome import AthomeScraper
from scrapers.fudosan_japan import FudosanJapanScraper
from scrapers.custom import CustomScraper

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("fudosan-checker.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# 設定ファイルパス
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

# ポータルサイトとスクレイパーの対応
SITE_SCRAPERS = {
    "kenbiya": KenbiyaScraper,
    "rakumachi": RakumachiScraper,
    "suumo": SuumoScraper,
    "athome": AthomeScraper,
    "fudosan_japan": FudosanJapanScraper,
}


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _run_with_timeout(func, timeout_sec=120):
    """関数をタイムアウト付きで実行する。

    注意: ThreadPoolExecutor の `with` 文は終了時にスレッド完了を待つため、
    タイムアウト時に hung thread をリーク（無視）して即座に戻る形にしている。
    リークしたスレッドは Python プロセスに残るが、次の巡回をブロックしない。
    """
    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(func)
        return future.result(timeout=timeout_sec)
    finally:
        # hung thread を待たずに executor を捨てる（リークするが ok）
        executor.shutdown(wait=False)


def run_once(config: dict):
    """全サイトを1回巡回し、新着物件を通知する。"""
    logger.info("===== 巡回開始 =====")
    sites = config.get("sites", {})
    all_new = []
    all_price_changed = []

    # ポータルサイトの巡回
    for site_key, scraper_class in SITE_SCRAPERS.items():
        site_config = sites.get(site_key, {})
        if not site_config.get("enabled", False):
            continue

        search_url = site_config.get("search_url", "")
        if not search_url:
            logger.info(f"[{site_key}] search_urlが未設定のためスキップ")
            continue

        logger.info(f"[{site_key}] 巡回開始...")
        try:
            scraper = scraper_class(search_url)
            properties = _run_with_timeout(scraper.scrape, timeout_sec=120)
            if properties:
                new_props, price_changed = upsert_properties(properties)
                all_new.extend(new_props)
                all_price_changed.extend(price_changed)
                logger.info(f"[{site_key}] 新着: {len(new_props)}件, 価格変更: {len(price_changed)}件")
        except TimeoutError:
            logger.error(f"[{site_key}] タイムアウト（120秒）でスキップ")
        except Exception as e:
            logger.error(f"[{site_key}] エラー: {e}", exc_info=True)

    # カスタムサイトの巡回
    custom_sites = config.get("custom_sites", []) or []
    for custom_config in custom_sites:
        if not custom_config.get("enabled", False):
            continue

        name = custom_config.get("name", "カスタムサイト")
        logger.info(f"[{name}] 巡回開始...")
        try:
            scraper = CustomScraper(custom_config)
            properties = _run_with_timeout(scraper.scrape, timeout_sec=120)
            if properties:
                new_props, price_changed = upsert_properties(properties)
                all_new.extend(new_props)
                all_price_changed.extend(price_changed)
                logger.info(f"[{name}] 新着: {len(new_props)}件, 価格変更: {len(price_changed)}件")
        except TimeoutError:
            logger.error(f"[{name}] タイムアウト（120秒）でスキップ")
        except Exception as e:
            logger.error(f"[{name}] エラー: {e}", exc_info=True)

    # Discord通知
    notification = config.get("notification", {})
    discord_config = notification.get("discord", {})
    if discord_config.get("enabled", False) and (all_new or all_price_changed):
        logger.info(f"Discord通知: 新着{len(all_new)}件, 価格変更{len(all_price_changed)}件")
        if all_new:
            send_new_properties(all_new)
            mark_notified([p.url for p in all_new])
        if all_price_changed:
            send_price_changes(all_price_changed)

    total = len(all_new) + len(all_price_changed)
    if total == 0:
        logger.info("新着・変更なし")
    else:
        logger.info(f"巡回完了: 新着{len(all_new)}件, 価格変更{len(all_price_changed)}件")


def run_once_with_timeout(config: dict):
    """run_once を全体タイムアウト付きで実行する（10分）。

    1サイトのタイムアウトに加えて、全体のセーフティネット。
    ハングした場合も次の巡回が動くようにする。
    """
    try:
        _run_with_timeout(lambda: run_once(config), timeout_sec=600)
    except TimeoutError:
        logger.error("===== 巡回全体がタイムアウト（10分）。次回に持ち越します =====")
    except Exception as e:
        logger.error(f"巡回エラー: {e}", exc_info=True)


def run_daemon(config: dict):
    """APSchedulerで定期実行する。"""
    from apscheduler.schedulers.background import BackgroundScheduler
    import threading

    interval = config.get("schedule", {}).get("interval_minutes", 60)

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_once_with_timeout, "interval", minutes=interval, args=[config], id="fudosan_check",
        max_instances=1, replace_existing=True,
        misfire_grace_time=300,
    )

    logger.info(f"スケジューラ起動: {interval}分間隔で巡回します")
    logger.info("初回巡回を実行します...")
    # 初回巡回をバックグラウンドで実行
    threading.Thread(target=run_once_with_timeout, args=[config], daemon=True).start()

    scheduler.start()

    # Webサーバー起動（メインスレッド）
    from web import app
    logger.info("Web管理画面を起動: http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080, use_reloader=False)


def main():
    parser = argparse.ArgumentParser(description="不動産物件自動巡回・通知システム")
    parser.add_argument("--daemon", action="store_true", help="デーモンモード（定期実行）")
    args = parser.parse_args()

    load_dotenv()
    init_db()
    config = load_config()

    if args.daemon:
        run_daemon(config)
    else:
        run_once(config)


if __name__ == "__main__":
    main()
