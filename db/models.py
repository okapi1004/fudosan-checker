import sqlite3
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


_base_dir = os.path.dirname(os.path.dirname(__file__))
_data_dir = os.path.join(_base_dir, "data")
os.makedirs(_data_dir, exist_ok=True)
DB_PATH = os.path.join(_data_dir, "properties.db")


@dataclass
class Property:
    url: str
    title: str
    price: str
    site: str
    address: str = ""
    yield_rate: str = ""
    area: str = ""
    image_url: str = ""
    raw_text: str = ""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            price TEXT,
            site TEXT NOT NULL,
            address TEXT,
            yield_rate TEXT,
            area TEXT,
            image_url TEXT,
            raw_text TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            notified INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_url TEXT NOT NULL,
            old_price TEXT,
            new_price TEXT,
            changed_at TEXT NOT NULL,
            FOREIGN KEY (property_url) REFERENCES properties(url)
        )
    """)
    conn.commit()
    conn.close()


def upsert_properties(properties: list[Property]) -> tuple[list[Property], list[tuple[Property, str]]]:
    """物件データを保存し、新着物件と価格変更物件を返す。

    Returns:
        (new_properties, price_changed): 新着物件リストと(物件, 旧価格)のタプルリスト
    """
    conn = get_connection()
    now = datetime.now().isoformat()
    new_properties = []
    price_changed = []

    for prop in properties:
        existing = conn.execute(
            "SELECT price FROM properties WHERE url = ?", (prop.url,)
        ).fetchone()

        if existing is None:
            conn.execute(
                """INSERT INTO properties (url, title, price, site, address, yield_rate, area, image_url, raw_text, first_seen, last_seen, notified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (prop.url, prop.title, prop.price, prop.site, prop.address,
                 prop.yield_rate, prop.area, prop.image_url, prop.raw_text, now, now),
            )
            new_properties.append(prop)
        else:
            conn.execute(
                """UPDATE properties SET title=?, price=?, address=?, yield_rate=?, area=?,
                   image_url=?, raw_text=?, last_seen=? WHERE url=?""",
                (prop.title, prop.price, prop.address, prop.yield_rate, prop.area,
                 prop.image_url, prop.raw_text, now, prop.url),
            )
            old_price = existing["price"]
            if old_price and prop.price and old_price != prop.price:
                conn.execute(
                    "INSERT INTO price_history (property_url, old_price, new_price, changed_at) VALUES (?, ?, ?, ?)",
                    (prop.url, old_price, prop.price, now),
                )
                price_changed.append((prop, old_price))

    conn.commit()
    conn.close()
    return new_properties, price_changed


def mark_notified(urls: list[str]):
    conn = get_connection()
    for url in urls:
        conn.execute("UPDATE properties SET notified = 1 WHERE url = ?", (url,))
    conn.commit()
    conn.close()
