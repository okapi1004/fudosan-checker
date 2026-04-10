import logging
import os
import time

import requests

from db.models import Property

logger = logging.getLogger(__name__)

# サイトごとの色（Discordの embed color は10進数整数）
SITE_COLORS = {
    "健美家": 0x2ECC71,      # 緑
    "楽待": 0x3498DB,        # 青
    "SUUMO": 0xE74C3C,       # 赤
    "アットホーム": 0xF39C12, # オレンジ
    "不動産ジャパン": 0x9B59B6, # 紫
}
DEFAULT_COLOR = 0x95A5A6      # グレー


def send_new_properties(properties: list[Property], webhook_url: str | None = None):
    """新着物件をDiscordに通知する。"""
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
    if not url:
        logger.error("DISCORD_WEBHOOK_URLが設定されていません")
        return

    for prop in properties:
        embed = _build_embed(prop, is_new=True)
        _send_webhook(url, embed)
        time.sleep(0.5)  # レート制限対策


def send_price_changes(changes: list[tuple[Property, str]], webhook_url: str | None = None):
    """価格変更をDiscordに通知する。"""
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
    if not url:
        logger.error("DISCORD_WEBHOOK_URLが設定されていません")
        return

    for prop, old_price in changes:
        embed = _build_price_change_embed(prop, old_price)
        _send_webhook(url, embed)
        time.sleep(0.5)


def _build_embed(prop: Property, is_new: bool = True) -> dict:
    color = SITE_COLORS.get(prop.site, DEFAULT_COLOR)

    fields = []
    if prop.price:
        fields.append({"name": "価格", "value": prop.price, "inline": True})
    if prop.yield_rate:
        fields.append({"name": "利回り", "value": prop.yield_rate, "inline": True})
    if prop.address:
        fields.append({"name": "所在地", "value": prop.address, "inline": False})
    if prop.area:
        fields.append({"name": "面積", "value": prop.area, "inline": True})

    return {
        "embeds": [{
            "title": f"{'🆕 ' if is_new else ''}{prop.title}",
            "url": prop.url,
            "color": color,
            "fields": fields,
            "footer": {"text": prop.site},
        }]
    }


def _build_price_change_embed(prop: Property, old_price: str) -> dict:
    color = SITE_COLORS.get(prop.site, DEFAULT_COLOR)

    return {
        "embeds": [{
            "title": f"💰 価格変更: {prop.title}",
            "url": prop.url,
            "color": color,
            "fields": [
                {"name": "旧価格", "value": old_price, "inline": True},
                {"name": "新価格", "value": prop.price, "inline": True},
                {"name": "所在地", "value": prop.address or "不明", "inline": False},
            ],
            "footer": {"text": prop.site},
        }]
    }


def _send_webhook(url: str, payload: dict):
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", 1)
            logger.warning(f"Discord レート制限。{retry_after}秒待機します")
            time.sleep(retry_after)
            requests.post(url, json=payload, timeout=10)
        elif resp.status_code >= 400:
            logger.error(f"Discord通知エラー: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Discord通知送信失敗: {e}")
